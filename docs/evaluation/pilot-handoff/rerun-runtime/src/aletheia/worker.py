"""Single in-process worker over a durable queue; no provider calls on saved reads."""

import asyncio

from aletheia.orchestrator import Pipeline
from aletheia.storage import Conflict, StorageError


class Worker:
    def __init__(self, storage, model, search, model_name, *, budget_factory=None):
        self.storage = storage
        options = {"budget_factory": budget_factory} if budget_factory else {}
        self.pipeline = Pipeline(storage, model, search, model_name, **options)
        self.stopping = asyncio.Event()
        self.task = None
        self.current = None
        self.recovering = False

    def start(self):
        self.task = asyncio.create_task(self.run(), name="aletheia-research-worker")

    async def recover_storage(self):
        # Never replay partially executed provider work. Reconcile the durable
        # state first, then resume claiming queued jobs after storage recovers.
        self.recovering = True
        for attempt in range(3):
            if attempt:
                await asyncio.sleep(0.1 * attempt)
            try:
                await self.storage.recover_interrupted(storage_failure=True)
            except StorageError:
                continue
            self.recovering = False
            return True
        return False

    async def run(self):
        while not self.stopping.is_set():
            try:
                self.current = await self.storage.claim_next()
                if self.current is None:
                    try:
                        await asyncio.wait_for(self.stopping.wait(), timeout=0.2)
                    except TimeoutError:
                        pass
                    continue
                try:
                    await self.pipeline.run(self.current)
                except (asyncio.CancelledError, StorageError):
                    raise
                except Exception:
                    try:
                        await self.storage.progress(
                            self.current.id, "pipeline_failed", {"reason": "internal_error"}
                        )
                        await self.storage.finish(
                            self.current.id,
                            status="failed",
                            stop_reason="provider_failure",
                            error="The investigation could not be completed.",
                        )
                    except Conflict:
                        # A terminal commit may already have succeeded.
                        pass
            except StorageError:
                if not await self.recover_storage():
                    # Bounded recovery failed. Health exposes this and startup
                    # recovery reconciles running records when storage returns.
                    return
            finally:
                self.current = None

    async def stop(self, grace_seconds=5):
        self.stopping.set()
        if self.task is None:
            return
        try:
            try:
                await asyncio.wait_for(asyncio.shield(self.task), timeout=grace_seconds)
            except TimeoutError:
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                if not self.task.cancelled():
                    raise
        finally:
            # Reconcile only after the worker stopped. Covers cancellation after
            # claim commit and after terminal commit without overwriting results.
            if self.task.done():
                try:
                    await self.storage.recover_interrupted()
                except StorageError:
                    pass  # Startup recovery retries once storage is available.
