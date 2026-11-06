"""Safe provider error vocabulary shared with request accounting."""

from enum import StrEnum
from typing import Literal

Operation = Literal["model", "search", "extract"]
Provider = Literal["nebius", "tavily"]


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
