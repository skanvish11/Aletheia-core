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
        call_id = budget.trace_id("p")
        for attempt in range(self.settings.max_retries + 1):
            trace = {
                "provider_call_id": call_id,
                "provider": self.provider,
                "operation": operation,
                "attempt": str(attempt + 1),
                "units": str(units),
                "request_bytes": str(len(encoded)),
            }
            try:
                budget.reserve(self.provider, operation, units)
            except ProviderError as exc:
                await budget.observe(
                    "provider_call_rejected",
                    {
                        **trace,
                        "outcome": exc.code.value,
                        "limit_reason": exc.limit_reason,
                    },
                )
                raise
            await budget.observe("provider_attempt_started", trace)
            started = time.monotonic()
            status = None
            outcome = "cancelled"
            error = None
            response_bytes = None
            try:
                timeout = min(self.settings.timeout_seconds, budget.remaining_seconds())
                if timeout <= 0:
                    raise budget.deadline_error(self.provider)
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
                        response_bytes = 0
                        async for chunk in response.aiter_bytes():
                            response_bytes += len(chunk)
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
                error = (
                    budget.deadline_error(self.provider, status_code=status)
                    if budget.remaining_seconds() <= 0
                    else ProviderError(self.provider, ErrorCode.TIMEOUT, status_code=status)
                )
            except httpx.DecodingError:
                error = ProviderError(self.provider, ErrorCode.INVALID_RESPONSE, status_code=status)
            except httpx.TransportError:
                error = ProviderError(self.provider, ErrorCode.NETWORK, status_code=status)
            except (ValueError, TypeError, KeyError, IndexError, RecursionError, ValidationError):
                error = ProviderError(self.provider, ErrorCode.INVALID_RESPONSE, status_code=status)
            except ProviderError as exc:
                error = exc
            except Exception:
                outcome = "internal_error"
                raise
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
                await budget.observe(
                    "provider_attempt_finished",
                    {
                        **trace,
                        "elapsed_seconds": f"{budget.attempts[-1].elapsed_seconds:.3f}",
                        "status_code": str(status) if status is not None else "unknown",
                        "outcome": error.code.value if error else outcome,
                        "validation_code": error.validation_code if error else "none",
                        "limit_reason": error.limit_reason if error else "none",
                        "response_bytes": str(response_bytes)
                        if response_bytes is not None
                        else "unknown",
                    },
                )
            if not error.retryable or attempt == self.settings.max_retries:
                await budget.observe(
                    "provider_retry_stopped",
                    {
                        **trace,
                        "reason": "not_retryable" if not error.retryable else "retry_limit_reached",
                        "outcome": error.code.value,
                    },
                )
                raise error from None
            try:
                budget.check(self.provider, operation, units)
            except ProviderError as exc:
                await budget.observe(
                    "provider_retry_stopped",
                    {
                        **trace,
                        "reason": exc.code.value,
                        "limit_reason": exc.limit_reason,
                    },
                )
                raise
            delay = max(0.25 * 2**attempt, error.retry_after or 0)

            async def check_backoff(delay, trace, error):
                # Trace persistence consumes time, so check both before and after it.
                if delay >= budget.remaining_seconds():
                    await budget.observe(
                        "provider_retry_stopped",
                        {
                            **trace,
                            "reason": "backoff_exceeds_deadline",
                            "delay_seconds": str(delay),
                        },
                    )
                    raise error from None

            await check_backoff(delay, trace, error)
            await budget.observe(
                "provider_retry_scheduled",
                {
                    **trace,
                    "reason": error.code.value,
                    "delay_seconds": str(delay),
                },
            )
            await check_backoff(delay, trace, error)
            await asyncio.sleep(delay)
        raise AssertionError("Unreachable retry state")
