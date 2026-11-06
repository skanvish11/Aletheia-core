"""Per-run provider attempt limits, deadline, and safe attempt records."""

import math
import time
from dataclasses import dataclass, field

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

    def check(self, provider: Provider, operation: Operation, units: int) -> None:
        if self.remaining_seconds() <= 0:
            raise ProviderError(provider, ErrorCode.DEADLINE)
        limit = self.limits[operation]
        if self.used[operation] + units > limit:
            raise ProviderError(provider, ErrorCode.BUDGET)

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
        super().__init__(8, 4, 4, self.started + 120)

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
                raise ProviderError(provider, ErrorCode.BUDGET)
        # Profiles may escalate, but counters and the original clock never reset.
        self.limits.update(
            model=self.model_attempts, search=self.search_attempts, extract=self.extraction_attempts
        )
        super().check(provider, operation, units)
