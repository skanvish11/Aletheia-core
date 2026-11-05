"""Bounded HTTP calls, safe errors, and per-attempt accounting shared by providers."""

import asyncio
import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from enum import StrEnum
from typing import Literal

import httpx
from pydantic import ValidationError

from aletheia.providers.settings import ProviderSettings

Operation = Literal["model", "search", "extract"]
Provider = Literal["nebius", "tavily"]


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


class ErrorCode(StrEnum):
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    QUOTA = "quota_exceeded"
    RATE_LIMIT = "rate_limited"
    TIMEOUT = "timeout"
    NETWORK = "network"
    UNAVAILABLE = "unavailable"
    INVALID_REQUEST = "invalid_request"
    INVALID_RESPONSE = "invalid_response"
    RESPONSE_TOO_LARGE = "response_too_large"
    TRUNCATED = "truncated_output"
    REFUSAL = "refusal"
    BUDGET = "budget_exhausted"
    DEADLINE = "deadline_exceeded"


class ProviderError(Exception):
    """Safe to report: no remote message, body, URL, prompt, or credential."""

    def __init__(
        self,
        provider: Provider,
        code: ErrorCode,
        *,
        status_code: int | None = None,
        retry_after: float | None = None,
    ):
        self.provider = provider
        self.code = code
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(f"{provider}: {code.value}")

    @property
    def retryable(self) -> bool:
        return self.code in {
            ErrorCode.RATE_LIMIT,
            ErrorCode.TIMEOUT,
            ErrorCode.NETWORK,
            ErrorCode.UNAVAILABLE,
        }


@dataclass(frozen=True)
class Attempt:
    provider: Provider
    operation: Operation
    units: int
    elapsed_seconds: float
    status_code: int | None
    outcome: str


@dataclass
class CallBudget:
    """Share one budget across a run. Reservations are atomic within one event loop.

    Extraction units count URLs, not HTTP batches. Failed attempts also consume units.
    The future controller owns research/finalization reserves and passes its deadline.
    """

    model_attempts: int
    search_attempts: int
    extraction_attempts: int
    deadline: float
    used: dict[Operation, int] = field(
        default_factory=lambda: {"model": 0, "search": 0, "extract": 0}, init=False
    )
    attempts: list[Attempt] = field(default_factory=list, init=False)

    def __post_init__(self):
        if any(
            type(n) is not int or n < 0
            for n in (self.model_attempts, self.search_attempts, self.extraction_attempts)
        ) or not math.isfinite(self.deadline):
            raise ValueError("Budget limits must be nonnegative integers with a finite deadline.")

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def check(self, provider: Provider, operation: Operation, units: int) -> None:
        if self.remaining_seconds() <= 0:
            raise ProviderError(provider, ErrorCode.DEADLINE)
        limit = {
            "model": self.model_attempts,
            "search": self.search_attempts,
            "extract": self.extraction_attempts,
        }[operation]
        if self.used[operation] + units > limit:
            raise ProviderError(provider, ErrorCode.BUDGET)

    def reserve(self, provider: Provider, operation: Operation, units: int) -> None:
        self.check(provider, operation, units)
        self.used[operation] += units


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
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.provider = provider
        self.settings = settings
        key = settings.nebius_api_key if provider == "nebius" else settings.tavily_api_key
        if key is None:
            raise ProviderError(provider, ErrorCode.CONFIGURATION)
        self._client = httpx.AsyncClient(
            base_url=(
                "https://api.tokenfactory.nebius.com/v1/"
                if provider == "nebius"
                else "https://api.tavily.com/"
            ),
            headers={"Authorization": f"Bearer {key.get_secret_value()}"},
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
        for retry in range(self.settings.max_retries + 1):
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
                        if budget.remaining_seconds() <= 0:
                            raise ProviderError(self.provider, ErrorCode.DEADLINE)
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
            if not error.retryable or retry == self.settings.max_retries:
                raise error from None
            budget.check(self.provider, operation, units)
            delay = max(0.25 * 2**retry, error.retry_after or 0)
            # Do not shorten Retry-After, or sleep through the caller's deadline.
            if delay >= budget.remaining_seconds():
                raise error from None
            await asyncio.sleep(delay)
        raise AssertionError("Unreachable retry state")
