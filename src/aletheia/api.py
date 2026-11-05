"""Foundation endpoints and bounded, sanitized HTTP input handling."""

from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from aletheia.config import Settings
from aletheia.contracts import ACTIVE_STATUSES, Investigation, InvestigationRequest
from aletheia.storage import QueueFull, Storage, StorageError


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


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings.from_environment()
    storage = Storage(settings.database_path, settings.queue_limit)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await storage.initialize()
        yield
        # Each storage operation owns and closes its connection; no worker starts here.

    app = FastAPI(title="Aletheia", version="0.1.0", lifespan=lifespan)
    app.state.storage = storage
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

    @app.get("/health")
    async def health():
        await storage.health()
        return {"status": "ok", "database": "ok", "research_enabled": False}

    return app
