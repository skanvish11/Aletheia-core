"""Regression checks for the ten Step 3 review findings; no live providers."""

import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from research_fixtures import Providers, terminal
from test_research_integrity import judgment, source
from test_research_pipeline import running, submit

from aletheia.api import create_app
from aletheia.budgets import RunBudget
from aletheia.contracts import InvestigationRequest
from aletheia.evidence import admit
from aletheia.providers.errors import ProviderError
from aletheia.providers.tavily import ExtractionResult, PageOutcome, TavilyProvider
from aletheia.research_contracts import Assertion, Snapshot
from aletheia.storage import QueueFull, Storage, StorageError
from aletheia.tasks import Tasks
from aletheia.verdicts import finding, synthesize


async def test_empty_initial_plan_completes_without_search(settings):
    class NoSearch(Providers):
        def model_value(self, schema, data):
            if schema == "SearchPlan":
                return {"queries": [], "gap": "No useful search is available."}
            return super().model_value(schema, data)

    providers = NoSearch()
    async with running(settings, providers) as (_, client):
        saved = await submit(client)
        assert saved["status"] == "completed"
        assert saved["stop_reason"] == "no_useful_query"
        assert saved["result"]["unable_to_decide_reason"] == "insufficient_evidence"
        assert saved["result"]["verdict"] is None
        assert providers.calls == ["/v1/chat/completions"] * 2


@pytest.mark.parametrize("interrupted", [False, True])
async def test_failed_run_has_explicit_idempotent_retry(settings, interrupted):
    providers = Providers(authentication_failure=not interrupted)
    if interrupted:
        store = Storage(settings.database_path)
        await store.initialize()
        queued = await store.submit(InvestigationRequest(claim="The Archive opened in 2000."))
        await store.claim_next()
    async with running(settings, providers) as (_, client):
        initial = await client.post(
            "/investigations", json={"claim": "The Archive opened in 2000."}
        )
        assert initial.status_code == (200 if interrupted else 202)
        failed = await terminal(client, initial.json()["id"])
        assert failed["status"] == "failed"
        if interrupted:
            assert failed["id"] == str(queued.id)
            assert failed["stop_reason"] == "interrupted"
        count = len(providers.calls)
        reused = await client.post("/investigations", json={"claim": failed["claim"]})
        assert reused.status_code == 200 and reused.json() == failed
        assert len(providers.calls) == count
        providers.options["authentication_failure"] = False
        responses = await asyncio.gather(
            *[
                client.post(failed["links"]["refresh"], headers={"Idempotency-Key": "retry"})
                for _ in range(6)
            ]
        )
        assert all(r.status_code in {200, 202} for r in responses)
        assert len({r.json()["id"] for r in responses}) == 1
        retried = await terminal(client, responses[0].json()["id"])
        assert retried["status"] == "completed"
        assert retried["result"]["verdict"] == "true"
        assert retried["parent_id"] == failed["id"] and retried["version"] == 2
        assert (await client.get(failed["links"]["self"])).json() == failed
        assert (await client.get(retried["links"]["comparison"])).json()[
            "comparison_status"
        ] == "unavailable"


async def test_failed_retry_respects_capacity_without_consuming_key(settings):
    store = Storage(settings.database_path, queue_limit=1)
    await store.initialize()
    first = await store.submit(InvestigationRequest(claim="Failed claim"))
    await store.claim_next()
    await store.finish(first.id, status="failed", stop_reason="provider_failure")
    other = await store.submit(InvestigationRequest(claim="Occupy capacity"))
    with pytest.raises(QueueFull):
        await store.refresh(first.id, "retry-after-capacity")
    assert (await store.submit(InvestigationRequest(claim="Failed claim"))).id == first.id
    await store.claim_next()
    await store.finish(other.id, status="failed", stop_reason="provider_failure")
    retried = await store.refresh(first.id, "retry-after-capacity")
    assert retried.version == 2 and not retried.reused
    assert len(await store.events(retried.id)) == 1


async def test_worker_recovers_after_real_sqlite_lock_without_replaying_work(settings, monkeypatch):
    providers = Providers()
    lock = sqlite3.connect(settings.database_path, isolation_level=None)
    locked = asyncio.Event()
    recovering = asyncio.Event()
    try:
        async with running(settings, providers) as (app, client):
            store = app.state.storage
            original_connection, original_progress = store.connection, store.progress
            original_recover = store.recover_interrupted

            async def observe_recovery(**kwargs):
                recovering.set()
                await original_recover(**kwargs)

            @asynccontextmanager
            async def immediate_busy():
                async with original_connection() as db:
                    if locked.is_set():
                        await db.execute("PRAGMA busy_timeout=0")
                    yield db

            async def lock_after_interpretation(run_id, event, payload, **kwargs):
                if event == "claim_interpreted" and not locked.is_set():
                    lock.execute("BEGIN IMMEDIATE")
                    locked.set()
                await original_progress(run_id, event, payload, **kwargs)

            monkeypatch.setattr(store, "connection", immediate_busy)
            monkeypatch.setattr(store, "progress", lock_after_interpretation)
            monkeypatch.setattr(store, "recover_interrupted", observe_recovery)
            first = (await client.post("/investigations", json={"claim": "First"})).json()
            await asyncio.wait_for(locked.wait(), timeout=3)
            await asyncio.wait_for(recovering.wait(), timeout=3)
            assert (await client.get("/health")).status_code == 503
            lock.rollback()
            failed = await terminal(client, first["id"])
            assert failed["status"] == "failed" and failed["stop_reason"] == "storage_failure"
            replay = await client.get(failed["links"]["events"])
            assert replay.text.count("event: investigation_failed") == 1
            second = await submit(client)
            assert second["status"] == "completed"
            assert (await client.get("/health")).status_code == 200
            assert sum(name == "ClaimPlan" for name, _ in providers.model_inputs) == 2
    finally:
        lock.close()


async def test_persistent_storage_failure_stops_bounded_recovery_and_sse(settings, monkeypatch):
    providers = Providers()
    async with running(settings, providers) as (app, client):
        store = app.state.storage
        recover = store.recover_interrupted
        attempts = 0

        async def unavailable(*args, **kwargs):
            raise StorageError("Database unavailable.")

        async def failed_recovery(**kwargs):
            nonlocal attempts
            attempts += 1
            raise StorageError("Database unavailable.")

        monkeypatch.setattr(store, "progress", unavailable)
        monkeypatch.setattr(store, "recover_interrupted", failed_recovery)
        saved = (await client.post("/investigations", json={"claim": "Storage outage"})).json()
        await asyncio.wait_for(app.state.worker.task, timeout=3)
        assert attempts == 3
        assert (await client.get("/health")).status_code == 503
        replay = await asyncio.wait_for(client.get(saved["links"]["events"]), timeout=2)
        assert "event: investigation_started" in replay.text
        assert not providers.calls
        monkeypatch.setattr(store, "recover_interrupted", recover)
    assert (await store.get(UUID(saved["id"]))).stop_reason == "interrupted"


async def test_shutdown_after_terminal_commit_preserves_result(settings, monkeypatch):
    providers = Providers()
    committed = asyncio.Event()
    async with running(settings, providers) as (app, client):
        original = app.state.storage.finish

        async def pause_after_commit(*args, **kwargs):
            await original(*args, **kwargs)
            committed.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(app.state.storage, "finish", pause_after_commit)
        saved = await submit(client)
        await asyncio.wait_for(committed.wait(), timeout=3)
        await app.state.worker.stop(grace_seconds=0.01)
        assert (await client.get(saved["links"]["self"])).json() == saved
        events = await app.state.storage.events(UUID(saved["id"]))
        assert sum(e.type == "investigation_completed" for e in events) == 1
        assert not any(e.type == "investigation_failed" for e in events)


@pytest.mark.parametrize(
    "reason",
    [
        "timeout",
        "rate_limited",
        "network",
        "unavailable",
        "response_too_large",
        "invalid_response",
        "page_size_limit",
    ],
)
async def test_all_selected_source_rejections_are_retrieval_failures(settings, monkeypatch, reason):
    async with running(settings, Providers()) as (_, client):
        first = await submit(client)

        async def failed_extract(self, urls, *, budget):
            return ExtractionResult(
                pages=tuple(PageOutcome(url, None, reason) for url in urls),
                retrieved_at=datetime.now(UTC),
                usage=None,
            )

        monkeypatch.setattr(TavilyProvider, "extract", failed_extract)
        refreshed = await client.post(
            first["links"]["refresh"], headers={"Idempotency-Key": reason}
        )
        saved = await terminal(client, refreshed.json()["id"])
        comparison = (await client.get(saved["links"]["comparison"])).json()
        assert comparison["sources"][0]["change"] == "retrieval_failed"


@pytest.mark.parametrize("length,truncated", [(150_000, False), (210_000, True)])
async def test_configured_extraction_limit_preserves_large_pages(settings, length, truncated):
    prefix = "The Archive opened in 2000.\n"
    text = prefix + "x" * (length - len(prefix))
    providers = Providers(text=text, max_extracted_chars=200_000)
    async with running(settings, providers) as (app, client):
        saved = await submit(client)
        assert saved["status"] == "completed"
        assert saved["result"]["verdict"] == "true"
        snapshots = await app.state.storage.records(UUID(saved["id"]), "snapshot", Snapshot)
        assert snapshots[0].original_text == text[:200_000]
        assert ("page_text_truncated" in snapshots[0].limitations) is truncated
        assert saved["result"]["configuration"]["max_extracted_chars"] == 200_000


async def test_finalization_reserve_covers_repairs_to_both_model_tasks():
    class RepairBoth(Providers):
        def model_value(self, schema, data):
            if schema in {"Synthesis", "ExplanationCheck"}:
                if sum(name == schema for name, _ in self.model_inputs) == 1:
                    return {}
            return super().model_value(schema, data)

    budget = RunBudget()
    with pytest.raises(ProviderError):
        while True:
            budget.reserve("nebius", "model", 1)
    budget.finalizing = True
    s = source()
    evidence = [admit(judgment(s), s, {1})]
    assertion = Assertion(
        text="The Archive opened in 2000.",
        kind="direct_record",
        consequential=False,
        recommended_route="quick",
    )
    computed, _ = finding(assertion, "quick", evidence, [s])
    providers = RepairBoth()

    async def emit(*args, **kwargs):
        pass

    async with providers.factory() as (model, _, _):
        result, explanation = await synthesize(
            Tasks(model, budget, emit), assertion, computed, evidence, "quick", [s]
        )
    assert result.verdict == "true" and explanation
    assert len(providers.calls) == 4
    assert budget.used["model"] == budget.model_attempts


@pytest.mark.parametrize("header", [False, True])
async def test_event_cursor_filters_before_parsing_old_history(settings, header):
    async with running(settings, Providers()) as (app, client):
        saved = await submit(client)
        store = app.state.storage
        events = await store.events(UUID(saved["id"]))
        cursor = events[-2].sequence
        # A replay after this event must never load/parse its payload again.
        async with store.connection() as db:
            await db.execute(
                "UPDATE events SET payload_json='not json' WHERE investigation_id=? AND sequence=1",
                (saved["id"],),
            )
        suffix = "?after=0" if header else f"?after={cursor}"
        response = await client.get(
            saved["links"]["events"] + suffix,
            headers={"Last-Event-ID": str(cursor)} if header else {},
        )
        values = [json.loads(s[6:]) for s in response.text.splitlines() if s.startswith("data: ")]
        assert [v["sequence"] for v in values] == [events[-1].sequence]


async def test_event_cursor_rejects_values_outside_sqlite_integer_range(settings):
    async with running(settings, Providers()) as (_, client):
        saved = await submit(client)
        response = await client.get(saved["links"]["events"] + f"?after={2**63}")
        assert response.status_code == 422


async def test_sse_preserves_terminal_event_when_worker_stops_after_event_read(
    settings, monkeypatch
):
    providers = Providers()
    providers.hold = asyncio.Event()
    async with running(settings, providers) as (app, client):
        queued = (await client.post("/investigations", json={"claim": "SSE stop race"})).json()
        await asyncio.wait_for(providers.entered.wait(), timeout=3)
        original = app.state.storage.events
        raced = False

        async def finish_after_read(run_id, **kwargs):
            nonlocal raced
            batch = await original(run_id, **kwargs)
            if "after" in kwargs and not raced:
                raced = True
                providers.hold.set()
                await terminal(client, queued["id"])
                await app.state.worker.stop()
            return batch

        monkeypatch.setattr(app.state.storage, "events", finish_after_read)
        replay = await asyncio.wait_for(client.get(queued["links"]["events"]), timeout=3)
        assert raced
        assert replay.text.count("event: investigation_completed") == 1


async def test_evidence_read_projects_metadata_without_loading_full_snapshots(
    settings, monkeypatch
):
    async with running(
        settings, Providers(text="The Archive opened in 2000.\n" + "x" * 90_000)
    ) as (app, client):
        saved = await submit(client)
        stored = await app.state.storage.records(UUID(saved["id"]), "snapshot", Snapshot)
        expected = [
            s.model_dump(mode="json", exclude={"original_text", "normalized_text", "spans"})
            for s in stored
        ]

        def forbidden(*args, **kwargs):
            pytest.fail("Public evidence reads must not validate full page snapshots.")

        monkeypatch.setattr(Snapshot, "model_validate_json", forbidden)
        evidence = (await client.get(saved["links"]["evidence"])).json()
        assert evidence["sources"] == expected
        assert "original_text" not in json.dumps(evidence)


@pytest.mark.parametrize("research_enabled", [False, True])
async def test_health_without_lifespan_is_unavailable_even_with_existing_db(
    settings, research_enabled
):
    await Storage(settings.database_path).initialize()
    app = create_app(replace(settings, research_enabled=research_enabled))
    # Deliberately bypass lifespan to exercise the unsupported-host health response.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 503
        assert response.json()["status"] == "unavailable"
