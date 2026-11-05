"""Foundation endpoints and bounded, sanitized HTTP input handling."""

import asyncio
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from aletheia.config import Settings
from aletheia.contracts import ACTIVE_STATUSES, Investigation, InvestigationRequest
from aletheia.research_contracts import Comparison, Evidence
from aletheia.runtime import research_providers
from aletheia.storage import Conflict, QueueFull, Storage, StorageError
from aletheia.worker import Worker


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            size += len(body)
            if size > self.max_bytes:
                await JSONResponse({"detail": "Request body exceeds the size limit."}, 413)(
                    scope, receive, send
                )
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)


def create_app(
    settings: Settings | None = None, *, provider_factory=research_providers, budget_factory=None
) -> FastAPI:
    settings = settings if settings is not None else Settings.from_environment()
    storage = Storage(settings.database_path, settings.queue_limit)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await storage.initialize()
        app.state.worker = None
        if settings.research_enabled:
            async with provider_factory() as (model, search, model_name):
                worker = Worker(storage, model, search, model_name, budget_factory=budget_factory)
                app.state.worker = worker
                worker.start()
                app.state.initialized = True
                try:
                    yield
                finally:
                    app.state.initialized = False
                    await worker.stop()
        else:
            app.state.initialized = True
            try:
                yield
            finally:
                app.state.initialized = False

    app = FastAPI(title="Aletheia", version="0.2.0", lifespan=lifespan)
    app.state.storage = storage
    app.state.worker = None
    app.state.initialized = False
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_body_bytes)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        # FastAPI's default details include the rejected input. Never echo it.
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Invalid request. Check the API schema and input limits.",
            },
        )

    @app.exception_handler(StorageError)
    async def database_unavailable(request: Request, exc: StorageError):
        return JSONResponse(status_code=503, content={"detail": "Database unavailable."})

    @app.exception_handler(Conflict)
    async def conflict(request: Request, exc: Conflict):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(QueueFull)
    async def queue_full(request: Request, exc: QueueFull):
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Investigation queue is full. Existing investigations remain available.",
            },
        )

    @app.post(
        "/investigations",
        response_model=Investigation,
        status_code=202,
        responses={200: {"model": Investigation}},
    )
    async def submit(payload: InvestigationRequest, response: Response):
        investigation = await storage.submit(payload)
        response.status_code = 202 if investigation.status in ACTIVE_STATUSES else 200
        response.headers["Location"] = investigation.links.self
        return investigation

    @app.get("/investigations/{investigation_id}", response_model=Investigation)
    async def get_investigation(investigation_id: UUID):
        investigation = await storage.get(investigation_id)
        if investigation is None:
            raise HTTPException(status_code=404, detail="Investigation not found.")
        return investigation

    @app.post(
        "/investigations/{investigation_id}/refresh", response_model=Investigation, status_code=202
    )
    async def refresh(
        investigation_id: UUID,
        request: Request,
        response: Response,
        idempotency_key: Annotated[str, Header(min_length=1, max_length=200)],
    ):
        if not idempotency_key.strip() or await request.body() not in (b"", b"{}"):
            raise HTTPException(
                422, "Refresh accepts an empty body and a nonblank Idempotency-Key."
            )
        investigation = await storage.refresh(investigation_id, idempotency_key)
        if investigation is None:
            raise HTTPException(404, "Investigation not found.")
        response.status_code = 202 if investigation.status in ACTIVE_STATUSES else 200
        response.headers["Location"] = investigation.links.self
        return investigation

    @app.get("/investigations/{investigation_id}/evidence")
    async def evidence(investigation_id: UUID):
        if await storage.get(investigation_id) is None:
            raise HTTPException(404, "Investigation not found.")
        sources = await storage.snapshot_metadata(investigation_id)
        assessments = await storage.records(investigation_id, "evidence", Evidence)
        return {
            "sources": [s.model_dump(mode="json") for s in sources],
            "evidence": [e.model_dump(mode="json") for e in assessments],
        }

    @app.get("/investigations/{investigation_id}/comparison", response_model=Comparison)
    async def comparison(investigation_id: UUID):
        saved = await storage.get(investigation_id)
        if saved is None:
            raise HTTPException(404, "Investigation not found.")
        values = await storage.records(investigation_id, "comparison", Comparison)
        if values:
            return values[0]
        return Comparison(
            comparison_status="not_applicable"
            if not saved.parent_id
            else ("pending" if saved.status in ACTIVE_STATUSES else "unavailable"),
            baseline_id=str(saved.parent_id) if saved.parent_id else None,
        )

    @app.get("/investigations/{investigation_id}/events")
    async def events(
        investigation_id: UUID,
        request: Request,
        after: Annotated[int, Query(ge=0, le=9_223_372_036_854_775_807)] = 0,
        last_event_id: Annotated[str | None, Header()] = None,
    ):
        if await storage.get(investigation_id) is None:
            raise HTTPException(404, "Investigation not found.")
        cursor = after
        if last_event_id is not None:
            if (
                not last_event_id.isascii()
                or not last_event_id.isdigit()
                or len(last_event_id) > 18
            ):
                raise HTTPException(422, "Last-Event-ID must be a nonnegative sequence number.")
            cursor = int(last_event_id)

        async def stream():
            nonlocal cursor
            while not await request.is_disconnected():
                worker = app.state.worker
                worker_stopped = worker is not None and worker.task.done()
                # Read status BEFORE events: a terminal transition between reads cannot
                # make us close before its committed terminal event has been replayed.
                saved = await storage.get(investigation_id)
                for event in await storage.events(investigation_id, after=cursor):
                    yield (
                        f"id: {event.sequence}\nevent: {event.type}\n"
                        f"data: {event.model_dump_json()}\n\n"
                    )
                    cursor = event.sequence
                if saved.status not in ACTIVE_STATUSES:
                    return
                if worker_stopped:
                    # Permanent storage failure cannot append a terminal event.
                    # Close the stream; health exposes the unavailable worker.
                    return
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/health")
    async def health():
        if not app.state.initialized:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable",
                    "database": "not_initialized",
                    "research_enabled": settings.research_enabled,
                },
            )
        await storage.health()
        worker = app.state.worker
        if worker and (worker.task.done() or worker.recovering):
            return JSONResponse(
                status_code=503,
                content={"status": "unavailable", "database": "ok", "research_enabled": True},
            )
        return {"status": "ok", "database": "ok", "research_enabled": settings.research_enabled}

    return app
