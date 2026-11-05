import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import replace
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from research_fixtures import Providers, terminal

from aletheia.api import create_app
from aletheia.budgets import RunBudget
from aletheia.providers.errors import ErrorCode, ProviderError
from aletheia.research_contracts import Evidence


@asynccontextmanager
async def running(settings, providers, **options):
    app = create_app(
        replace(settings, research_enabled=True), provider_factory=providers.factory, **options
    )
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield app, client


async def submit(client):
    response = await client.post("/investigations", json={"claim": "The Archive opened in 2000."})
    assert response.status_code == 202
    return await terminal(client, response.json()["id"])


async def test_complete_evidence_saved_reads_and_sse(settings):
    providers = Providers()
    async with running(settings, providers) as (app, client):
        saved = await submit(client)
        assert saved["status"] == "completed", saved
        assert saved["result"]["verdict"] == "true"
        assert saved["route"] == "quick"
        assert saved["result"]["budget_used"] == {"model": 5, "search": 2, "extract": 1}
        assert saved["result"]["token_usage"]["total_tokens"] == 150
        path = saved["links"]["self"]
        calls = len(providers.calls)
        sources = (await client.get(path + "/evidence")).json()
        assert "original_text" not in sources["sources"][0]
        evidence = sources["evidence"][0]
        assert evidence["excerpts"][0]["text"] == "The Archive opened in 2000."
        assert evidence["assessment"]["citation"]["snapshot_id"] == sources["sources"][0]["id"]
        assert saved["result"]["explanation"][0]["evidence_ids"] == [evidence["id"]]
        duplicate = await client.post("/investigations", json={"claim": saved["claim"]})
        assert duplicate.status_code == 200
        assert duplicate.json() == saved
        assert (await client.get(path)).json() == saved
        replay = await client.get(path + "/events")
        assert replay.headers["content-type"].startswith("text/event-stream")
        records = [
            json.loads(line[6:]) for line in replay.text.splitlines() if line.startswith("data: ")
        ]
        assert [e["sequence"] for e in records] == list(range(1, len(records) + 1))
        assert records[-1]["type"] == "investigation_completed"
        resumed = await client.get(path + "/events?after=999", headers={"Last-Event-ID": "2"})
        assert "id: 2\n" not in resumed.text and "id: 3\n" in resumed.text
        assert len(providers.calls) == calls
        assert (await client.get(path + "/comparison")).json()[
            "comparison_status"
        ] == "not_applicable"
        assert (await client.get("/health")).json()["research_enabled"] is True
    # Reopen with research disabled: same persisted result and passages, zero calls.
    reopened = create_app(settings)
    async with (
        reopened.router.lifespan_context(reopened),
        AsyncClient(transport=ASGITransport(app=reopened), base_url="http://test") as client,
    ):
        assert (await client.get(path)).json() == saved
        assert (await client.get(path + "/evidence")).json() == sources
    assert len(providers.calls) == calls


@pytest.mark.parametrize(
    ("options", "status", "verdict"),
    [
        ({"relation": "contradicts"}, "completed", "false"),
        ({"relation": "mixed", "source_count": 2}, "completed", None),
        ({"deep": True}, "completed", None),
        ({"deep": True, "synthesis": True}, "completed", "true"),
        ({"deep": True, "independent": True, "source_count": 2}, "completed", "true"),
        ({"empty": True}, "completed", None),
        ({"extraction_failure": True}, "completed", None),
        ({"scope_match": False}, "completed", None),
        ({"ambiguous": True}, "needs_clarification", None),
        ({"invalid_citation": True}, "failed", None),
        ({"invalid_plan": True}, "failed", None),
        ({"invalid_explanation": True}, "failed", None),
        ({"authentication_failure": True}, "failed", None),
    ],
)
async def test_outcomes(settings, options, status, verdict):
    providers = Providers(**options)
    async with running(settings, providers) as (app, client):
        saved = await submit(client)
        assert saved["status"] == status, saved
        assert (saved["result"]["verdict"] if saved["result"] else None) == verdict
        if saved["result"]:
            result = saved["result"]
            assert result["outcome"] == ("decided" if verdict else "unable_to_decide")
            expected_reason = (
                None
                if verdict
                else (
                    "conflicting_evidence"
                    if options.get("relation") == "mixed"
                    else "insufficient_evidence"
                )
            )
            assert result["unable_to_decide_reason"] == expected_reason
            assert result["almost_correction"] is None
        if options.get("invalid_plan") or options.get("ambiguous"):
            assert "/search" not in providers.calls
        if options.get("invalid_citation"):
            assert (
                len([name for name, _ in providers.model_inputs if name == "AssessmentBatch"]) == 2
            )
            assert not await app.state.storage.records(UUID(saved["id"]), "evidence", Evidence)
        assert "synthetic-provider-secret" not in json.dumps(saved)


async def test_flags_drop_invalid_and_preserve_multiple(settings):
    flags = [
        {"type": "narrow_scope", "dimension": "timeframe", "explanation": "Only 2000 records."},
        {
            "type": "misleading_comparison",
            "dimension": "baseline",
            "explanation": "Different baselines.",
        },
        {"type": "unknown", "dimension": "timeframe", "explanation": "Invalid flag."},
    ]
    providers = Providers(flags=flags, relation="context", scope_match=False)
    async with running(settings, providers) as (app, client):
        saved = await submit(client)
        assert len(saved["result"]["finding"]["qualification_flags"]) == 2
        events = await app.state.storage.events(UUID(saved["id"]))
        assert sum(e.type == "qualification_flag_dropped" for e in events) == 1


async def test_refresh_idempotency_comparison_and_no_old_verdict_in_prompts(settings):
    providers = Providers()
    async with running(settings, providers) as (app, client):
        first = await submit(client)
        path = first["links"]["self"]
        providers.options["relation"] = "contradicts"
        input_count = len(providers.model_inputs)
        responses = await asyncio.gather(
            *[
                client.post(path + "/refresh", headers={"Idempotency-Key": "refresh-one"})
                for _ in range(8)
            ]
        )
        assert all(r.status_code in {200, 202} for r in responses)
        ids = {r.json()["id"] for r in responses}
        assert len(ids) == 1
        second = await terminal(client, ids.pop())
        assert second["version"] == 2 and second["parent_id"] == first["id"]
        assert second["result"]["verdict"] == "false"
        assert (await client.get(path)).json() == first
        comparison = (await client.get(second["links"]["self"] + "/comparison")).json()
        assert comparison["same_relevant_evidence"] is True
        assert comparison["consistency_status"] == "inconsistent"
        assert comparison["recheck_status"] == "disabled"
        for name, data in providers.model_inputs[input_count:]:
            if name not in {"Synthesis", "ExplanationCheck"}:
                assert "verdict" not in json.dumps(data)
            else:
                assert data["finding"]["verdict"] == "false"
        mismatch = await client.post(
            second["links"]["self"] + "/refresh", headers={"Idempotency-Key": "refresh-one"}
        )
        assert mismatch.status_code == 409


async def test_limits_preserve_valid_partial_and_no_unbudgeted_calls(settings):
    class SmallBudget(RunBudget):
        def __init__(self):
            super().__init__()
            self.search_attempts = 1

    providers = Providers()
    async with running(settings, providers, budget_factory=SmallBudget) as (_, client):
        saved = await submit(client)
        assert saved["status"] == "partial", saved
        assert saved["stop_reason"] == "budget_exhausted"
        assert saved["result"]["verdict"] is None
        assert providers.calls.count("/search") == 1
        assert "/extract" not in providers.calls


@pytest.mark.parametrize("status", [401, 402])
async def test_extraction_provider_failure_stops_research(settings, status):
    providers = Providers(extraction_status=status, source_count=2)
    async with running(settings, providers) as (_, client):
        saved = await submit(client)
        assert saved["status"] == "failed"
        assert saved["stop_reason"] == "provider_failure"
        assert saved["result"] is None
        assert providers.calls.count("/extract") == 1
        assert [name for name, _ in providers.model_inputs] == ["ClaimPlan", "SearchPlan"]


async def test_truncated_source_is_saved_and_changes_evidence_comparison(settings):
    text = "The Archive opened in 2000.\n" + "x" * 1200
    providers = Providers(deep=True, synthesis=True, max_extracted_chars=1024, text=text)
    async with running(settings, providers) as (_, client):
        first = await submit(client)
        assert first["result"]["verdict"] is None
        assert first["result"]["unable_to_decide_reason"] == "insufficient_evidence"
        assert "page_text_truncated" in first["result"]["limitations"]
        path = first["links"]["self"]
        evidence = (await client.get(path + "/evidence")).json()
        assert "page_text_truncated" in evidence["sources"][0]["limitations"]
        assessments = [v for name, v in providers.model_inputs if name == "AssessmentBatch"]
        assert assessments[0]["source_truncated"] is True

        # The complete replacement happens to equal the old retained prefix. Equal
        # content hashes must not hide that comprehensive coverage is now available.
        providers.options["text"] = text[:1024]
        refresh = await client.post(path + "/refresh", headers={"Idempotency-Key": "full-page"})
        second = await terminal(client, refresh.json()["id"])
        assert second["result"]["verdict"] == "true"
        comparison = (await client.get(second["links"]["self"] + "/comparison")).json()
        assert comparison["sources"][0]["change"] == "unchanged"
        assert comparison["same_relevant_evidence"] is False
        assert comparison["consistency_status"] == "not_comparable"
        assert comparison["algorithm"] == "relevant-evidence-v2"


def test_finalization_reserve_and_escalation_are_shared():
    budget = RunBudget()
    start = budget.started
    for _ in range(5):
        budget.reserve("nebius", "model", 1)
    with pytest.raises(ProviderError) as error:
        budget.reserve("nebius", "model", 1)
    assert error.value.code == ErrorCode.BUDGET
    budget.escalate()
    assert budget.used["model"] == 5 and budget.deadline == start + 240
    for _ in range(8):
        budget.reserve("nebius", "model", 1)
    with pytest.raises(ProviderError):
        budget.reserve("nebius", "model", 1)
    budget.finalizing = True
    for _ in range(3):
        budget.reserve("nebius", "model", 1)
    with pytest.raises(ProviderError):
        budget.reserve("nebius", "model", 1)


async def test_shutdown_interrupts_and_restart_does_not_rerun(settings):
    providers = Providers()
    providers.hold = asyncio.Event()
    async with running(settings, providers) as (app, client):
        initial = (
            await client.post("/investigations", json={"claim": "Interrupted research"})
        ).json()
        async with asyncio.timeout(3):
            await providers.entered.wait()
        await app.state.worker.stop(grace_seconds=0.01)
        saved = await terminal(client, initial["id"])
        assert saved["status"] == "failed" and saved["stop_reason"] == "interrupted"
    providers.hold = None
    calls = len(providers.calls)
    async with running(settings, providers) as (_, client):
        assert (await client.get(saved["links"]["self"])).json() == saved
    assert len(providers.calls) == calls


async def test_queued_work_is_consumed_after_restart_with_research_enabled(settings):
    from aletheia.contracts import InvestigationRequest
    from aletheia.storage import Storage

    store = Storage(settings.database_path)
    await store.initialize()
    queued = await store.submit(InvestigationRequest(claim="The Archive opened in 2000."))
    async with running(settings, Providers()) as (_, client):
        saved = await terminal(client, str(queued.id))
        assert saved["status"] == "completed"
        assert saved["created_at"] == queued.model_dump(mode="json")["created_at"]


async def test_followup_limit_is_partial_and_queries_do_not_repeat(settings):
    providers = Providers(empty=True, followups=True)
    async with running(settings, providers) as (_, client):
        saved = await submit(client)
        assert saved["status"] == "partial"
        assert saved["stop_reason"] == "budget_exhausted"
        assert saved["route"] == "deep"
        assert providers.calls.count("/search") == 6
        plans = [data for name, data in providers.model_inputs if name == "SearchPlan"]
        assert len(plans) == 3
        assert len(plans[-1]["previous_queries"]) == 4


async def test_hard_deadline_starts_no_calls(settings):
    class ExpiredBudget(RunBudget):
        def __init__(self):
            super().__init__()
            self.deadline = self.started - 1

    providers = Providers()
    async with running(settings, providers, budget_factory=ExpiredBudget) as (_, client):
        saved = await submit(client)
        assert saved["status"] == "failed"
        assert saved["stop_reason"] == "deadline_exceeded"
        assert not providers.calls


async def test_finalization_deadline_keeps_finding_but_discards_unchecked_prose(settings):
    class FinalDeadlineBudget(RunBudget):
        def reserve(self, provider, operation, units):
            if self.finalizing and self.used["model"] == 4:
                self.deadline = self.started - 1
            super().reserve(provider, operation, units)

    providers = Providers()
    async with running(settings, providers, budget_factory=FinalDeadlineBudget) as (_, client):
        saved = await submit(client)
        assert saved["status"] == "partial"
        assert saved["stop_reason"] == "deadline_exceeded"
        assert saved["result"]["verdict"] == "true"
        assert saved["result"]["explanation"] == []
        assert not any(name == "ExplanationCheck" for name, _ in providers.model_inputs)


async def test_disconnected_progress_subscriber_does_not_cancel_research(settings):
    providers = Providers()
    providers.hold = asyncio.Event()
    async with running(settings, providers) as (app, client):
        initial = (
            await client.post("/investigations", json={"claim": "The Archive opened in 2000."})
        ).json()
        await asyncio.wait_for(providers.entered.wait(), timeout=3)
        messages = asyncio.Queue()
        await messages.put({"type": "http.request", "body": b"", "more_body": False})
        delivered = []

        async def send(message):
            delivered.append(message)
            if message["type"] == "http.response.body" and message.get("body"):
                await messages.put({"type": "http.disconnect"})

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": initial["links"]["self"] + "/events",
            "query_string": b"",
            "headers": [],
            "server": ("test", 80),
            "client": ("test", 1234),
            "root_path": "",
        }
        await asyncio.wait_for(app(scope, messages.get, send), timeout=3)
        assert any(m.get("body", b"").startswith(b"id: 1") for m in delivered)
        assert not app.state.worker.task.done()
        providers.hold.set()
        saved = await terminal(client, initial["id"])
        assert saved["status"] == "completed"


async def test_research_enabled_missing_configuration_fails_without_calls(settings):
    from aletheia.config import ConfigurationError

    app = create_app(replace(settings, research_enabled=True))
    with pytest.raises(ConfigurationError, match="valid documented configuration"):
        async with app.router.lifespan_context(app):
            pytest.fail("Research requires explicit provider configuration.")


async def test_shutdown_cancellation_during_claim_reconciles_committed_running_row(settings):
    from aletheia.contracts import InvestigationRequest
    from aletheia.storage import Storage
    from aletheia.worker import Worker

    store = Storage(settings.database_path)
    await store.initialize()
    queued = await store.submit(InvestigationRequest(claim="Claim cancellation race"))
    claim_committed = asyncio.Event()
    never_return = asyncio.Event()
    original = store.claim_next

    async def slow_claim():
        claimed = await original()
        claim_committed.set()
        await never_return.wait()
        return claimed

    store.claim_next = slow_claim
    providers = Providers()
    async with providers.factory() as (model, search, model_name):
        worker = Worker(store, model, search, model_name)
        worker.start()
        await asyncio.wait_for(claim_committed.wait(), timeout=3)
        await worker.stop(grace_seconds=0.01)
    saved = await store.get(queued.id)
    assert saved.status == "failed" and saved.stop_reason == "interrupted"
    assert len([e for e in await store.events(queued.id) if e.type == "investigation_failed"]) == 1
    assert not providers.calls
