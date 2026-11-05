"""Single in-process worker over a durable queue; no provider calls on saved reads."""

import asyncio

from aletheia.orchestrator import Pipeline
from aletheia.storage import StorageError


class Worker:
    def __init__(self, storage, model, search, model_name, *, budget_factory=None):
        self.storage = storage
        options = {"budget_factory": budget_factory} if budget_factory else {}
        self.pipeline = Pipeline(storage, model, search, model_name, **options)
        self.stopping = asyncio.Event()
        self.task = None
        self.current = None

    def start(self):
        self.task = asyncio.create_task(self.run(), name="aletheia-research-worker")

    async def run(self):
        try:
            while not self.stopping.is_set():
                self.current = await self.storage.claim_next()
                if self.current is None:
                    try:
                        await asyncio.wait_for(self.stopping.wait(), timeout=0.2)
                    except TimeoutError:
                        pass
                    continue
                try:
                    await self.pipeline.run(self.current)
                except asyncio.CancelledError:
                    await self.storage.finish(
                        self.current.id,
                        status="failed",
                        stop_reason="interrupted",
                        error="Investigation interrupted by application shutdown.",
                    )
                    raise
                except StorageError:
                    # Leave the durable running state for startup recovery; stop claiming jobs.
                    raise
                except Exception:
                    await self.storage.finish(
                        self.current.id,
                        status="failed",
                        stop_reason="provider_failure",
                        error="The investigation could not be completed.",
                    )
                finally:
                    self.current = None
        except StorageError:
            # Health reports the stopped worker; never log raw DB/provider exceptions.
            return

    async def stop(self, grace_seconds=5):
        self.stopping.set()
        if self.task is None or self.task.cancelled():
            return
        try:
            await asyncio.wait_for(asyncio.shield(self.task), timeout=grace_seconds)
        except TimeoutError:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            # Cancellation can land after claim_next commits but before it returns.
            # Single-worker ownership lets shutdown reconcile that narrow race too.
            try:
                await self.storage.recover_interrupted()
            except StorageError:
                pass  # Startup recovery will retry once storage is available.
