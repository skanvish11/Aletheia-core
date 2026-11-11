"""Per-run provider attempt limits, deadline, and safe attempt records."""

import math
import time
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from dataclasses import dataclass, field

from aletheia.diagnostics import emit_diagnostic
from aletheia.providers.errors import ErrorCode, Operation, Provider, ProviderError


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
    limits: dict[Operation, int] = field(init=False)
    used: dict[Operation, int] = field(init=False)
    attempts: list[Attempt] = field(default_factory=list, init=False)
    observer: Callable[[str, dict[str, str]], Awaitable[None]] | None = field(
        default=None, init=False, repr=False
    )
    trace_context: dict[str, str] = field(default_factory=dict, init=False)
    trace_stage: str = field(default="interpreting", init=False)
    trace_sequence: int = field(default=0, init=False)

    def trace_id(self, prefix):
        self.trace_sequence += 1
        return f"{prefix}{self.trace_sequence}"

    @contextmanager
    def tracing(self, **context):
        previous = self.trace_context
        self.trace_context = {**previous, **context}
        try:
            yield
        finally:
            self.trace_context = previous

    def trace_budget(self):
        reserve = getattr(self, "reserve_model_attempts", 0)
        finalizing = getattr(self, "finalizing", False)
        return {
            "stage": self.trace_stage,
            "phase": "finalization" if finalizing else "research",
            "model_used": str(self.used["model"]),
            "model_limit": str(self.model_attempts),
            "model_available_limit": str(self.model_attempts - (0 if finalizing else reserve)),
            "search_used": str(self.used["search"]),
            "search_limit": str(self.search_attempts),
            "extract_used": str(self.used["extract"]),
            "extract_limit": str(self.extraction_attempts),
            "remaining_seconds": f"{self.remaining_seconds():.3f}",
            "hard_remaining_seconds": f"{max(0, self.deadline - time.monotonic()):.3f}",
        }

    async def observe(self, event, payload):
        if self.observer is not None:
            await emit_diagnostic(
                self.observer, event, {**self.trace_context, **self.trace_budget(), **payload}
            )

    def __post_init__(self):
        if any(
            type(n) is not int or n < 0
            for n in (self.model_attempts, self.search_attempts, self.extraction_attempts)
        ) or not math.isfinite(self.deadline):
            raise ValueError("Budget limits must be nonnegative integers with a finite deadline.")
        self.limits = {
            "model": self.model_attempts,
            "search": self.search_attempts,
            "extract": self.extraction_attempts,
        }
        self.used = dict.fromkeys(self.limits, 0)

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def deadline_error(self, provider, *, status_code=None):
        return ProviderError(
            provider,
            ErrorCode.DEADLINE,
            status_code=status_code,
            limit_reason="research_deadline"
            if self.deadline > time.monotonic()
            else "hard_deadline",
        )

    def check(self, provider: Provider, operation: Operation, units: int) -> None:
        if self.remaining_seconds() <= 0:
            raise self.deadline_error(provider)
        limit = self.limits[operation]
        if self.used[operation] + units > limit:
            error = ProviderError(provider, ErrorCode.BUDGET)
            error.limit_reason = operation + "_limit"
            raise error

    def reserve(self, provider: Provider, operation: Operation, units: int) -> None:
        self.check(provider, operation, units)
        self.used[operation] += units


class RunBudget(CallBudget):
    def __init__(self):
        self.started = time.monotonic()
        self.finalizing = False
        self.route = "quick"
        self.reserve_seconds = 45.0
        self.reserve_model_attempts = 4
        # Interpretation + planning + two assessments need four calls; allow
        # two repairs without consuming the four finalization calls.
        super().__init__(10, 4, 4, self.started + 120)

    def escalate(self):
        self.route = "deep"
        self.model_attempts = 16
        self.search_attempts = 8
        self.extraction_attempts = 10
        self.deadline = self.started + 240

    def remaining_seconds(self):
        # The HTTP adapter also clips retries/timeouts against this research deadline.
        deadline = self.deadline - (0 if self.finalizing else self.reserve_seconds)
        return max(0.0, deadline - time.monotonic())

    def check(self, provider, operation, units):
        if not self.finalizing and operation == "model":
            if self.used["model"] + units > self.model_attempts - self.reserve_model_attempts:
                error = ProviderError(provider, ErrorCode.BUDGET)
                error.limit_reason = "model_finalization_reserve"
                raise error
        # Profiles may escalate, but counters and the original clock never reset.
        self.limits.update(
            model=self.model_attempts, search=self.search_attempts, extract=self.extraction_attempts
        )
        super().check(provider, operation, units)
