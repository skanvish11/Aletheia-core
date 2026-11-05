import asyncio
import json
import sqlite3
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from aletheia.api import create_app
from aletheia.config import Settings


async def test_submit_retrieve_and_duplicate(client, app):
    payload = {"claim": "  Everest is above sea level.  ", "context": {"notes": "Check elevation"}}
    response = await client.post("/investigations", json=payload)
    assert response.status_code == 202
    first = response.json()
    UUID(first["id"])
    assert first["claim"] == payload["claim"]
    assert first["context"] == payload["context"]
    assert first["status"] == "queued"
    assert first["result"] is None
    assert first["started_at"] is None
    assert first["reused"] is False
    assert datetime.fromisoformat(first["created_at"]).utcoffset().total_seconds() == 0
    location = response.headers["location"]
    assert first["links"]["self"] == location
    retrieved = await client.get(location)
    assert retrieved.status_code == 200
    assert retrieved.json() == {**first, "reused": True}
    duplicate = await client.post("/investigations", json=payload)
    assert duplicate.status_code == 202
    assert duplicate.json() == {**first, "reused": True}
    events = await app.state.storage.events(UUID(first["id"]))
    assert len(events) == 1
    assert events[0].sequence == 1
    assert events[0].type == "investigation_queued"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"claim": ""},
        {"claim": " \n\t "},
        {"claim": 123},
        {"claim": "x" * 8001},
        {"claim": "test", "context": []},
        {"claim": "test", "context": None},
        {"claim": "test", "context": {"unknown": "value"}},
        {"claim": "test", "context": {"notes": "x" * 4001}},
        {"claim": "test", "context": {"location": 5}},
        {"claim": "test", "status": "completed"},
        {"claim": "test", "id": str(uuid4())},
    ],
)
async def test_invalid_input_does_not_persist(client, app, payload):
    response = await client.post("/investigations", json=payload)
    assert response.status_code == 422
    async with app.state.storage.connection() as db:
        for table in ("claim_requests", "investigations", "events"):
            assert (await (await db.execute(f"SELECT COUNT(*) FROM {table}")).fetchone())[0] == 0


async def test_invalid_json_and_unknown_id(client):
    response = await client.post(
        "/investigations", content='{ "claim":', headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert (await client.get(f"/investigations/{uuid4()}")).status_code == 404
    assert (await client.get("/investigations/not-an-id")).status_code == 422


async def test_request_boundaries(client):
    assert (
        await client.post(
            "/investigations", json={"claim": "x" * 8000, "context": {"notes": "x" * 4000}}
        )
    ).status_code == 202


async def test_validation_does_not_echo_supplied_secrets(client, caplog):
    secret = "synthetic-secret-never-a-real-key"
    response = await client.post("/investigations", json={"claim": {"token": secret}})
    assert response.status_code == 422
    assert secret not in response.text
    assert secret not in caplog.text


async def test_health_and_database_failure(client, app, monkeypatch):
    assert (await client.get("/health")).json() == {
        "status": "ok",
        "database": "ok",
        "research_enabled": False,
    }
    async with app.state.storage.connection() as db:
        await db.execute("DROP TABLE events")
    response = await client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable."}


async def test_sqlite_failure_redacted(client, app, monkeypatch, caplog):
    async def broken(*args, **kwargs):
        raise sqlite3.OperationalError("synthetic-secret and /private/database/path")

    monkeypatch.setattr(app.state.storage, "_append_event", broken)
    response = await client.post("/investigations", json={"claim": "Example"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable."}
    assert "synthetic-secret" not in caplog.text


async def test_full_queue_reuses_existing_and_rejects_new(tmp_path):
    app = create_app(Settings(database_path=tmp_path / "queue.db", queue_limit=1))
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.post("/investigations", json={"claim": "First"})
            reused = await client.post("/investigations", json={"claim": "First"})
            assert reused.status_code == 202
            assert reused.json()["id"] == first.json()["id"]
            assert (
                await client.post("/investigations", json={"claim": "Second"})
            ).status_code == 503


async def test_body_limit_checks_stream_even_with_false_content_length(tmp_path):
    app = create_app(Settings(database_path=tmp_path / "limit.db", max_body_bytes=1024))

    async def chunks():
        yield b'{"claim":"'
        yield b"x" * 1024
        yield b'"}'

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/investigations",
                content=chunks(),
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": "1",
                },
            )
            assert response.status_code == 413
            assert (await client.get("/health")).status_code == 200


async def test_concurrent_http_submissions(client):
    responses = await asyncio.gather(
        *[client.post("/investigations", json={"claim": "Concurrent claim"}) for _ in range(12)]
    )
    assert {response.status_code for response in responses} == {202}
    assert len({response.json()["id"] for response in responses}) == 1
    assert sum(not response.json()["reused"] for response in responses) == 1


@pytest.mark.parametrize("status", ["failed", "partial", "completed", "needs_clarification"])
async def test_terminal_reuse_never_requeues(client, app, status):
    original = (await client.post("/investigations", json={"claim": "Stored claim"})).json()
    # Seed later-stage state: no provider or research execution is implied by this fixture.
    async with app.state.storage.connection() as db:
        await db.execute(
            "UPDATE investigations SET status = ?, finished_at = ?, error_json = ? WHERE id = ?",
            (
                status,
                original["created_at"],
                json.dumps({"message": "Fixture outcome"}),
                original["id"],
            ),
        )
    before = (await client.get(original["links"]["self"])).json()
    response = await client.post("/investigations", json={"claim": "Stored claim"})
    assert response.status_code == 200
    assert response.json() == before
    assert len(await app.state.storage.events(UUID(original["id"]))) == 1
