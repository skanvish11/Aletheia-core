"""One shared budget; escalation preserves usage and elapsed time."""

import time

from aletheia.providers.common import CallBudget, ErrorCode, ProviderError


class RunBudget(CallBudget):
    def __init__(self):
        self.started = time.monotonic()
        self.finalizing = False
        self.route = "quick"
        self.reserve_seconds = 20.0
        super().__init__(10, 4, 4, self.started + 120)

    def escalate(self):
        self.route = "deep"
        self.model_attempts = 18
        self.search_attempts = 8
        self.extraction_attempts = 10
        self.deadline = self.started + 240

    def remaining_seconds(self):
        # The HTTP adapter also clips retries/timeouts against this research deadline.
        deadline = self.deadline - (0 if self.finalizing else self.reserve_seconds)
        return max(0.0, deadline - time.monotonic())

    def check(self, provider, operation, units):
        if not self.finalizing and operation == "model":
            if self.used["model"] + units > self.model_attempts - 3:
                raise ProviderError(provider, ErrorCode.BUDGET)
        super().check(provider, operation, units)
