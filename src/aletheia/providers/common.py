"""Bounded HTTP calls, safe errors, and per-attempt accounting shared by providers."""

import asyncio
import json
import math
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx
from pydantic import SecretStr, ValidationError

from aletheia.budgets import Attempt, CallBudget
from aletheia.config import ProviderSettings
from aletheia.providers.errors import ErrorCode, Operation, Provider, ProviderError


def parse_json(value: str | bytes | bytearray):
    """Reject non-JSON numeric constants and ambiguous duplicate object keys."""

    def reject_constant(_value):
        raise ValueError("Invalid JSON constant.")

    def unique_object(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key.")
            result[key] = item
        return result

    return json.loads(value, parse_constant=reject_constant, object_pairs_hook=unique_object)


def retry_delay(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        delay = float(value)
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            delay = (date - datetime.now(UTC)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return None
    return max(0.0, delay) if math.isfinite(delay) else None


def status_error(provider: Provider, status: int, retry_after: str | None) -> ProviderError:
    if status in (401, 403):
        code = ErrorCode.AUTHENTICATION
    elif status in (402, 432, 433):
        code = ErrorCode.QUOTA
    elif status == 429:
        code = ErrorCode.RATE_LIMIT
    elif status in (408, 504):
        code = ErrorCode.TIMEOUT
    elif status in (500, 502, 503):
        code = ErrorCode.UNAVAILABLE
    else:
        code = ErrorCode.INVALID_REQUEST
    return ProviderError(provider, code, status_code=status, retry_after=retry_delay(retry_after))


class ProviderHTTP:
    def __init__(
        self,
        provider: Provider,
        settings: ProviderSettings,
        *,
        api_key: SecretStr | None,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.provider = provider
        self.settings = settings
        if api_key is None:
            raise ProviderError(provider, ErrorCode.CONFIGURATION)
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key.get_secret_value()}"},
            timeout=settings.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.aclose()

    async def aclose(self):
        await self._client.aclose()

    async def post[T](
        self,
        path: str,
        payload: dict,
        *,
        budget: CallBudget,
        operation: Operation,
        parse: Callable[[dict], T],
        units: int = 1,
    ) -> T:
        try:
            encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (ValueError, TypeError, UnicodeError):
            raise ProviderError(self.provider, ErrorCode.INVALID_REQUEST) from None
        if len(encoded) > self.settings.max_request_bytes:
            raise ProviderError(self.provider, ErrorCode.INVALID_REQUEST)
        for attempt in range(self.settings.max_retries + 1):
            budget.reserve(self.provider, operation, units)
            started = time.monotonic()
            status = None
            outcome = "cancelled"
            error = None
            try:
                timeout = min(self.settings.timeout_seconds, budget.remaining_seconds())
                async with asyncio.timeout(timeout):
                    async with self._client.stream(
                        "POST",
                        path,
                        content=encoded,
                        headers={"Content-Type": "application/json"},
                        timeout=timeout,
                    ) as response:
                        status = response.status_code
                        if status != 200:
                            raise status_error(
                                self.provider, status, response.headers.get("retry-after")
                            )
                        content = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(content) + len(chunk) > self.settings.max_response_bytes:
                                raise ProviderError(self.provider, ErrorCode.RESPONSE_TOO_LARGE)
                            content.extend(chunk)
                        data = parse_json(content)
                        if not isinstance(data, dict):
                            raise ProviderError(self.provider, ErrorCode.INVALID_RESPONSE)
                        result = parse(data)
                        outcome = "success"
                        return result
            except (TimeoutError, httpx.TimeoutException):
                code = ErrorCode.DEADLINE if budget.remaining_seconds() <= 0 else ErrorCode.TIMEOUT
                error = ProviderError(self.provider, code, status_code=status)
            except httpx.DecodingError:
                error = ProviderError(self.provider, ErrorCode.INVALID_RESPONSE, status_code=status)
            except httpx.TransportError:
                error = ProviderError(self.provider, ErrorCode.NETWORK, status_code=status)
            except (ValueError, TypeError, KeyError, IndexError, RecursionError, ValidationError):
                error = ProviderError(self.provider, ErrorCode.INVALID_RESPONSE, status_code=status)
            except ProviderError as exc:
                error = exc
            finally:
                budget.attempts.append(
                    Attempt(
                        self.provider,
                        operation,
                        units,
                        time.monotonic() - started,
                        status,
                        error.code.value if error else outcome,
                    )
                )
            if not error.retryable or attempt == self.settings.max_retries:
                raise error from None
            budget.check(self.provider, operation, units)
            delay = max(0.25 * 2**attempt, error.retry_after or 0)
            # Do not shorten Retry-After, or sleep through the caller's deadline.
            if delay >= budget.remaining_seconds():
                raise error from None
            await asyncio.sleep(delay)
        raise AssertionError("Unreachable retry state")
