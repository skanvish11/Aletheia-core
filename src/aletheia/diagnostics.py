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


async def save_final_check(database_path, record):
    """Local owner-only artifact; deliberately absent from all API and SSE responses."""
    import os

    task = asyncio.current_task()
    if task is not None and task.cancelling():
        return
    try:
        directory = database_path.parent / (database_path.name + ".diagnostics")
        directory.mkdir(mode=0o700, exist_ok=True)
        # Refuse permissive/preexisting or symlinked directories rather than expose text.
        if directory.is_symlink() or directory.stat().st_mode & 0o077:
            raise OSError("Diagnostic directory is not restricted.")
        path = directory / (record.id + ".json")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(record.model_dump_json())
    except Exception:
        logger.warning("Optional final-check diagnostic could not be saved.")
