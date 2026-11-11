"""Optional diagnostics must not change results, errors, or cancellation."""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def emit_diagnostic(emit, event, payload):
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        return
    try:
        await emit(event, payload)
    except Exception:
        # Never log exception text, payloads, or tracebacks: they may contain secrets.
        # CancelledError is a BaseException and must continue to propagate.
        logger.warning("Optional research diagnostic could not be saved.")
