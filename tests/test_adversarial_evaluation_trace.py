"""Adversarial trace failures plus explicit, unresolved semantic counterexamples."""

import asyncio
import json
from contextlib import asynccontextmanager
from uuid import UUID

import httpx
import pytest
from research_fixtures import Providers, terminal
from test_research_pipeline import running, submit

from aletheia.budgets import RunBudget


async def events(app, saved):
    return await app.state.storage.events(UUID(saved["id"]))


@pytest.mark.parametrize("operation,status", [("search", 503), ("extract", 403), ("search", 504)])
async def test_non_model_failure_trace_survives_restart(settings, operation, status):
    class Unavailable(Providers):
        async def handle(self, request):
            if request.url.path == "/" + operation:
                self.calls.append(request.url.path)
                return httpx.Response(status, json={"secret": "private-provider-error"})
            return await super().handle(request)

    providers = Unavailable()
    async with running(settings, providers) as (app, client):
        saved = await submit(client)
        assert saved["status"] == "failed" and saved["result"] is None
        trace = await events(app, saved)
        config = next(e.payload for e in trace if e.type == "run_configured")
        assert config["max_output_tokens"] == "4096" and config["thinking"] == "default"
        failed = next(
            e
            for e in trace
            if e.type == "provider_attempt_finished" and e.payload["operation"] == operation
        )
        assert failed.payload["status_code"] == str(status)
        assert (
            failed.payload["outcome"]
            == {503: "unavailable", 403: "authentication", 504: "timeout"}[status]
        )
        assert int(failed.payload["request_bytes"]) > 0
        assert any(e.type == "provider_retry_stopped" for e in trace)
        assert failed.stage == ("searching" if operation == "search" else "extracting")
        assert failed.payload["search_used"] == ("1" if operation == "search" else "2")
        assert failed.sequence < trace[-1].sequence
        path = saved["links"]["events"]
        replay = (await client.get(path)).text
        assert "private-provider-error" not in replay
        assert "synthetic-nebius" not in replay
    async with running(settings, Providers()) as (_, client):
        assert (await client.get(path)).text == replay


@pytest.mark.parametrize("kind", ["json", "schema"])
async def test_invalid_completion_keeps_usage_and_safe_reason_not_private_keys(settings, kind):
    class Malformed(Providers):
        async def handle(self, request):
            if request.url.path.endswith("completions"):
                self.calls.append(request.url.path)
                value = self.model_value("ClaimPlan", {})
                value["assertions"][0]["text"] = 17
                value["private-field-name"] = "private-field-value"
                content = json.dumps(value) if kind == "schema" else '{"private-json":'
                return httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": content,
                                    "reasoning_content": "private-reasoning",
                                },
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 40,
                            "completion_tokens": 30,
                            "total_tokens": 70,
                            "completion_tokens_details": {"reasoning_tokens": 10},
                        },
                    },
                )
            return await super().handle(request)

    async with running(settings, Malformed()) as (app, client):
        saved = await submit(client)
        assert saved["status"] == "failed"
        trace = await events(app, saved)
        outcomes = [e.payload for e in trace if e.type == "task_finished"]
        assert len(outcomes) == 2
        assert len({p["task_call_id"] for p in outcomes}) == 1
        for payload in outcomes:
            assert payload["validation_code"] == "response_" + kind
            assert payload["completion_tokens"] == "30"
            assert payload["reasoning_tokens"] == "10"
            assert payload["finish_reason"] == "stop"
            assert int(payload["output_chars"]) > 0
            if kind == "schema":
                assert payload["schema_fields"] == "assertions"
                assert payload["schema_error_types"] == "extra_forbidden,string_type"
        assert "private-" not in (await client.get(saved["links"]["events"])).text


async def test_retry_failure_is_durable_while_next_attempt_is_still_running(settings):
    class Retry(Providers):
        count = 0

        def __init__(self):
            super().__init__()
            self.retry_entered, self.release = asyncio.Event(), asyncio.Event()

        @asynccontextmanager
        async def factory(self):
            async with super().factory() as (model, search, name):
                model.settings = model.settings.model_copy(update={"max_retries": 1})
                yield model, search, name

        async def handle(self, request):
            if request.url.path.endswith("completions"):
                self.count += 1
                if self.count == 1:
                    return httpx.Response(503, json={"private": "error"})
                if self.count == 2:
                    self.retry_entered.set()
                    await self.release.wait()
            return await super().handle(request)

    providers = Retry()
    async with running(settings, providers) as (app, client):
        initial = (
            await client.post("/investigations", json={"claim": "The Archive opened in 2000."})
        ).json()
        try:
            await asyncio.wait_for(providers.retry_entered.wait(), timeout=3)
            trace = await events(app, initial)
            failed = next(e for e in trace if e.type == "provider_attempt_finished")
            assert failed.payload["outcome"] == "unavailable"
            started = [e for e in trace if e.type == "provider_attempt_started"]
            assert [e.payload["attempt"] for e in started] == ["1", "2"]
            assert {e.payload["provider_call_id"] for e in started} == {
                failed.payload["provider_call_id"]
            }
            assert not any(e.type == "task_finished" for e in trace)
            assert any(e.type == "provider_retry_scheduled" for e in trace)
        finally:
            providers.release.set()
        assert (await terminal(client, initial["id"]))["status"] == "completed"


@pytest.mark.parametrize("limit", ["reserve", "research_deadline", "hard_deadline"])
async def test_rejected_call_records_exact_limit_without_network(settings, limit):
    class Exhausted(RunBudget):
        def __init__(self):
            super().__init__()
            if limit == "reserve":
                self.model_attempts = self.reserve_model_attempts
            else:
                self.deadline = self.started + (20 if limit == "research_deadline" else -1)

    providers = Providers()
    async with running(settings, providers, budget_factory=Exhausted) as (app, client):
        saved = await submit(client)
        assert saved["status"] == "failed" and providers.calls == []
        trace = await events(app, saved)
        blocked = next(e.payload for e in trace if e.type == "provider_call_rejected")
        assert blocked["limit_reason"] == (
            "model_finalization_reserve" if limit == "reserve" else limit
        )
        assert blocked["model_used"] == "0"
        assert not any(e.type == "provider_attempt_started" for e in trace)


async def test_trace_links_query_selection_snapshot_and_assessment(settings):
    async with running(settings, Providers()) as (app, client):
        saved = await submit(client)
        assert saved["status"] == "completed"
        trace = await events(app, saved)
        selected = next(e.payload for e in trace if e.type == "source_selected")
        query_ids = {e.payload["query_id"] for e in trace if e.type == "search_completed"}
        assert set(selected["query_ids"].split(",")) <= query_ids
        assert selected["selection_rule"] == "purpose_balanced_search_rank"
        extraction = next(
            e.payload
            for e in trace
            if e.type == "provider_attempt_finished" and e.payload["operation"] == "extract"
        )
        assert extraction["candidate_id"] == selected["candidate_id"]
        snapshot = next(e.payload for e in trace if e.type == "source_extracted")
        assert snapshot["candidate_id"] == selected["candidate_id"]
        assessment = next(
            e.payload for e in trace if e.type == "task_finished" and e.payload["task"] == "assess"
        )
        assert assessment["snapshot_id"] == snapshot["snapshot_id"]
        synthesis = next(
            e.payload
            for e in trace
            if e.type == "task_finished" and e.payload["task"] == "synthesize"
        )
        assert "snapshot_id" not in synthesis  # A previous task must not contaminate context.
        assert synthesis["phase"] == "finalization"


async def test_internal_exception_is_not_mislabeled_as_remote_provider_failure(settings):
    class Broken(Providers):
        async def handle(self, request):
            raise RuntimeError("private-internal-details")

    async with running(settings, Broken()) as (app, client):
        saved = await submit(client)
        assert saved["status"] == "failed"
        trace = await events(app, saved)
        assert any(
            e.type == "pipeline_failed" and e.payload["reason"] == "internal_error" for e in trace
        )
        assert any(
            e.type == "task_finished" and e.payload["outcome"] == "internal_error" for e in trace
        )
        assert "private-internal-details" not in (await client.get(saved["links"]["events"])).text


@pytest.mark.parametrize(
    "options,code",
    [
        ({"invalid_plan": True}, "query_coverage"),
        ({"almost": True}, "correction_ineligible"),
    ],
)
async def test_task_contract_rejections_have_specific_codes(settings, options, code):
    async with running(settings, Providers(**options)) as (app, client):
        saved = await submit(client)
        assert saved["status"] == "failed"
        trace = await events(app, saved)
        rejected = [
            e.payload
            for e in trace
            if e.type == "task_finished" and e.payload["outcome"] == "invalid_task_output"
        ]
        assert len(rejected) == 2
        assert {p["validation_code"] for p in rejected} == {code}


@pytest.mark.parametrize("expire_on", ["provider_attempt_started", "provider_retry_scheduled"])
async def test_trace_storage_time_cannot_start_http_or_sleep_past_deadline(monkeypatch, expire_on):
    import time

    from test_providers import budget, generate
    from test_providers import settings as provider_settings

    from aletheia.providers.errors import ProviderError
    from aletheia.providers.nebius import NebiusProvider

    allowance = budget()
    records, requests = [], []

    async def observe(event, payload):
        records.append((event, payload))
        if event == expire_on:
            allowance.deadline = time.monotonic() - 1

    async def forbidden_sleep(*args):
        pytest.fail("Do not sleep after the trace write consumed the deadline")

    def handle(request):
        requests.append(request)
        return httpx.Response(503, json={})

    allowance.observer = observe
    monkeypatch.setattr("aletheia.providers.common.asyncio.sleep", forbidden_sleep)
    async with NebiusProvider(
        provider_settings(max_retries=1), transport=httpx.MockTransport(handle)
    ) as model:
        with pytest.raises(ProviderError):
            await generate(model, allowance)
    assert len(requests) == (0 if expire_on == "provider_attempt_started" else 1)
    if expire_on == "provider_retry_scheduled":
        assert records[-1][0] == "provider_retry_stopped"
        assert records[-1][1]["reason"] == "backoff_exceeds_deadline"


async def test_truth_question_with_inconsistent_scope_analysis_is_rejected(settings):
    class Misclassified(Providers):
        def model_value(self, schema, data):
            value = super().model_value(schema, data)
            if schema == "ClaimPlan":
                value.update(
                    assertions=[],
                    questions=["Did the Archive open in 2000?"],
                    clarification_reason="missing_scope",
                )
            return value

    async with running(settings, Misclassified()) as (_, client):
        assert (await submit(client))["status"] != "needs_clarification"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="F05/F06 open: semantic checks can agree on unsupported evidence",
)
async def test_references_alone_cannot_make_unrelated_passages_support_a_claim(settings):
    # The model calls this authoritative support and its checker agrees. IDs/offsets
    # are valid, but the passage says nothing about the opening year.
    async with running(settings, Providers(text="The Archive gift shop sells postcards.")) as (
        _,
        client,
    ):
        saved = await submit(client)
        assert not (saved["status"] == "completed" and saved["result"]["verdict"] == "true")
