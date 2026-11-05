import asyncio
import json
import sqlite3
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from aletheia.api import create_app
from aletheia.contracts import InvestigationRequest
from aletheia.storage import QueueFull, Storage, StorageError


@pytest.mark.parametrize(
    ("first", "second", "same"),
    [
        ({"claim": " Café "}, {"claim": "Cafe\u0301"}, True),
        ({"claim": "A fact"}, {"claim": "A fact", "context": {}}, True),
        (
            {"claim": "A fact", "context": {"notes": "x", "location": "US"}},
            {"claim": "A fact", "context": {"location": "US", "notes": "x"}},
            True,
        ),
        ({"claim": "A fact"}, {"claim": "a fact"}, False),
        ({"claim": "A fact"}, {"claim": "A  fact"}, False),
        ({"claim": "A fact"}, {"claim": "A fact."}, False),
        ({"claim": "Value 10"}, {"claim": "Value 11"}, False),
        ({"claim": "In 2025"}, {"claim": "In 2026"}, False),
        ({"claim": "Fact"}, {"claim": "Fact", "context": {"notes": ""}}, False),
        ({"claim": "Fact"}, {"claim": "Fact", "context": {"notes": None}}, False),
        (
            {"claim": "Fact", "context": {"notes": "x"}},
            {"claim": "Fact", "context": {"notes": " x "}},
            False,
        ),
        (
            {"claim": "Fact", "context": {"location": "US"}},
            {"claim": "Fact", "context": {"location": "UK"}},
            False,
        ),
    ],
)
async def test_request_identity_rules(app, first, second, same):
    storage = app.state.storage
    a = await storage.submit(InvestigationRequest(**first))
    b = await storage.submit(InvestigationRequest(**second))
    assert (a.id == b.id) is same
    assert b.reused is same
    if same:
        assert b.claim == a.claim
        assert b.context == a.context
        assert b.created_at == a.created_at


async def test_independent_connections_deduplicate(app, settings):
    stores = [Storage(settings.database_path) for _ in range(16)]
    request = InvestigationRequest(claim="Same claim across independent connections")
    results = await asyncio.gather(*[store.submit(request) for store in stores])
    assert len({result.id for result in results}) == 1
    assert sum(not result.reused for result in results) == 1
    async with stores[0].connection() as db:
        for table in ("claim_requests", "investigations", "events"):
            assert (await (await db.execute(f"SELECT COUNT(*) FROM {table}")).fetchone())[0] == 1


async def test_capacity_is_atomic_across_connections(app, settings):
    stores = [Storage(settings.database_path, queue_limit=1) for _ in range(8)]
    results = await asyncio.gather(
        *[
            store.submit(InvestigationRequest(claim=f"Distinct claim {i}"))
            for i, store in enumerate(stores)
        ],
        return_exceptions=True,
    )
    assert sum(isinstance(result, QueueFull) for result in results) == 7
    assert sum(not isinstance(result, Exception) for result in results) == 1


async def test_failed_event_rolls_back_entire_submission(app):
    storage = app.state.storage
    # SQLite itself rejects the last insert, after the other two have executed.
    async with storage.connection() as db:
        await db.execute("""CREATE TRIGGER reject_event BEFORE INSERT ON events
                            BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
    with pytest.raises(StorageError):
        await storage.submit(InvestigationRequest(claim="Must not partially persist"))
    async with storage.connection() as db:
        for table in ("claim_requests", "investigations", "events"):
            assert (await (await db.execute(f"SELECT COUNT(*) FROM {table}")).fetchone())[0] == 0
        await db.execute("DROP TRIGGER reject_event")
    result = await storage.submit(InvestigationRequest(claim="Must not partially persist"))
    assert not result.reused
    assert len(await storage.events(result.id)) == 1


async def test_reopen_application_preserves_queued_record(settings):
    app1 = create_app(settings)
    async with app1.router.lifespan_context(app1):
        async with AsyncClient(transport=ASGITransport(app=app1), base_url="http://test") as client:
            first = (
                await client.post("/investigations", json={"claim": "Survives restart"})
            ).json()
    app2 = create_app(settings)
    async with app2.router.lifespan_context(app2):
        async with AsyncClient(transport=ASGITransport(app=app2), base_url="http://test") as client:
            saved = (await client.get(first["links"]["self"])).json()
            assert saved == {**first, "reused": True}
            duplicate = await client.post("/investigations", json={"claim": "Survives restart"})
            assert duplicate.json() == saved


async def test_recovery_is_atomic_ordered_and_idempotent(app, settings):
    storage = app.state.storage
    running = await storage.submit(InvestigationRequest(claim="Interrupted"))
    queued = await storage.submit(InvestigationRequest(claim="Still queued"))
    async with storage.connection() as db:
        await db.execute(
            "UPDATE investigations SET status = 'running' WHERE id = ?", (str(running.id),)
        )
        await db.execute("""CREATE TRIGGER reject_terminal BEFORE INSERT ON events
                            WHEN NEW.type = 'investigation_failed'
                            BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
    with pytest.raises(StorageError):
        await storage.recover_interrupted()
    assert (await storage.get(running.id)).status == "running"
    assert len(await storage.events(running.id)) == 1
    async with storage.connection() as db:
        await db.execute("DROP TRIGGER reject_terminal")
    reopened = Storage(settings.database_path)
    await reopened.initialize()
    failed = await reopened.get(running.id)
    assert failed.status == "failed"
    assert failed.stop_reason == "interrupted"
    assert failed.result is None
    assert failed.finished_at is not None
    assert (await reopened.get(queued.id)).status == "queued"
    events = await reopened.events(running.id)
    assert [event.sequence for event in events] == [1, 2]
    assert [event.type for event in events] == ["investigation_queued", "investigation_failed"]
    await reopened.initialize()
    assert await reopened.events(running.id) == events


async def test_latest_version_reused_without_refresh_implementation(app):
    storage = app.state.storage
    request = InvestigationRequest(claim="Version fixture")
    original = await storage.submit(request)
    newer_id = str(uuid4())
    async with storage.connection() as db:
        await db.execute(
            """INSERT INTO investigations
               (id, claim_request_id, version, parent_id, status, created_at, error_json)
               SELECT ?, claim_request_id, 2, id, 'failed', created_at, ?
               FROM investigations WHERE id = ?""",
            (newer_id, json.dumps({"message": "Fixture failure"}), str(original.id)),
        )
    reused = await storage.submit(request)
    assert str(reused.id) == newer_id
    assert reused.version == 2
    assert reused.parent_id == original.id
    assert reused.reused
    assert reused.status == "failed"


async def test_schema_version_and_unique_constraints(app, settings):
    storage = app.state.storage
    saved = await storage.submit(InvestigationRequest(claim="Unique"))
    async with storage.connection() as db:
        assert (await (await db.execute("PRAGMA user_version")).fetchone())[0] == 2
        with pytest.raises(sqlite3.IntegrityError):
            await db.execute(
                "INSERT INTO claim_requests SELECT ?, original_claim, context_json, "
                "request_key, created_at FROM claim_requests",
                (str(uuid4()),),
            )
        with pytest.raises(sqlite3.IntegrityError):
            await db.execute(
                "INSERT INTO events SELECT * FROM events WHERE investigation_id = ?",
                (str(saved.id),),
            )
        await db.execute("PRAGMA user_version = 999")
    with pytest.raises(StorageError, match="schema version"):
        await Storage(settings.database_path).initialize()
    async with storage.connection() as db:
        assert (await (await db.execute("PRAGMA user_version")).fetchone())[0] == 999
    assert (await storage.get(saved.id)).claim == "Unique"


async def test_non_database_file_is_not_overwritten(tmp_path):
    path = tmp_path / "existing-file"
    path.write_text("Not a database")
    with pytest.raises(StorageError):
        await Storage(path).initialize()
    assert path.read_text() == "Not a database"
