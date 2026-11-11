"""Regression checks for failures exposed by the proposed live evaluation."""

import json
from uuid import UUID

import httpx
import pytest
from research_fixtures import Providers
from test_research_pipeline import running, submit

from aletheia.research_contracts import AssessmentBatch as SavedAssessmentBatch
from aletheia.task_contracts import AssessmentBatch, Synthesis


@pytest.mark.parametrize("mode", ["default", "enabled", "disabled"])
async def test_thinking_control_is_explicit_and_model_specific(mode):
    from test_providers import budget, completion, generate
    from test_providers import settings as provider_settings

    from aletheia.providers.nebius import NebiusProvider

    def handle(request):
        body = json.loads(request.content)
        if mode == "default":
            assert "chat_template_kwargs" not in body
        else:
            assert body["chat_template_kwargs"] == {"enable_thinking": mode == "enabled"}
        assert body["max_tokens"] == 4096
        assert body["model"] == "nvidia/Nemotron-3_5-Lightning"
        return httpx.Response(200, json=completion())

    settings = provider_settings(nebius_model="nvidia/Nemotron-3_5-Lightning", nebius_thinking=mode)
    async with NebiusProvider(settings, transport=httpx.MockTransport(handle)) as model:
        assert (await generate(model, budget())).value.year == 2023


def test_unverified_thinking_control_fails_before_network_and_env_is_explicit(monkeypatch):
    from aletheia.config import ConfigurationError, ProviderSettings
    from aletheia.providers.nebius import NebiusProvider

    assert ProviderSettings.from_environment().nebius_thinking == "default"
    monkeypatch.setenv("ALETHEIA_NEBIUS_THINKING", "disabled")
    monkeypatch.setenv("NEBIUS_MODEL", "unverified-model")
    with pytest.raises(ConfigurationError, match="verified thinking controls"):
        NebiusProvider(ProviderSettings.from_environment())
    monkeypatch.setenv("NEBIUS_MODEL", "nvidia/Nemotron-3_5-Lightning")
    assert ProviderSettings.from_environment().nebius_thinking == "disabled"
    monkeypatch.setenv("ALETHEIA_NEBIUS_THINKING", "private-invalid-setting")
    with pytest.raises(ConfigurationError) as error:
        ProviderSettings.from_environment()
    assert "private-invalid-setting" not in str(error.value)


@pytest.mark.parametrize("task", ["ClaimPlan", "AssessmentBatch", "Synthesis"])
async def test_truncated_task_retains_safe_diagnostics_and_replays(settings, task):
    class Truncated(Providers):
        async def handle(self, request):
            if request.url.path.endswith("completions"):
                body = json.loads(request.content)
                if body["response_format"]["json_schema"]["schema"]["title"] == task:
                    self.calls.append(request.url.path)
                    return httpx.Response(
                        200,
                        json={
                            "choices": [
                                {
                                    "message": {
                                        "role": "assistant",
                                        "content": "private-response-secret",
                                    },
                                    "finish_reason": "length",
                                }
                            ],
                            "usage": {
                                "prompt_tokens": 123,
                                "completion_tokens": 4096,
                                "total_tokens": 4219,
                            },
                        },
                    )
            return await super().handle(request)

    providers = Truncated()
    async with running(settings, providers) as (app, client):
        saved = await submit(client)
        assert saved["status"] == "failed" and saved["result"] is None
        path = saved["links"]["self"]
        replay = (await client.get(path + "/events")).text
        events = await app.state.storage.events(UUID(saved["id"]))
        tasks = [e for e in events if e.type == "task_finished" and e.payload["schema"] == task]
        assert len(tasks) == 1  # Truncation is not blindly retried.
        payload = tasks[0].payload
        assert payload["outcome"] == "truncated_output"
        assert payload["finish_reason"] == "length"
        assert payload["completion_tokens"] == "4096"
        assert float(payload["elapsed_seconds"]) >= 0
        attempts = [
            e
            for e in events
            if e.type == "provider_attempt_finished" and e.payload["operation"] == "model"
        ]
        assert attempts[-1].payload["outcome"] == "truncated_output"
        assert attempts[-1].payload["status_code"] == "200"
        assert tasks[0].sequence < events[-1].sequence
        assert "private-response-secret" not in replay
        assert "synthetic-nebius" not in replay
        count = len(providers.calls)
        assert (await client.get(path)).json() == saved
        assert len(providers.calls) == count
    # Diagnostics are durable even when no InvestigationResult exists.
    async with running(settings, Providers()) as (_, client):
        assert (await client.get(path + "/events")).text == replay


@pytest.mark.parametrize("repair", [True, False])
async def test_factual_uncertainty_is_repaired_or_failed_not_asked_of_user(settings, repair):
    class Uncertain(Providers):
        count = 0

        def model_value(self, schema, data):
            value = super().model_value(schema, data)
            if schema == "ClaimPlan":
                self.count += 1
                if self.count == 1 or not repair:
                    value.update(
                        assertions=[],
                        questions=["Did the Archive open in 2000?"],
                        clarification_reason="factual_uncertainty",
                    )
            return value

    providers = Uncertain()
    async with running(settings, providers) as (app, client):
        saved = await submit(client)
        assert saved["status"] == ("completed" if repair else "failed")
        assert saved["clarification_questions"] is None
        assert ("/search" in providers.calls) is repair
        events = await app.state.storage.events(UUID(saved["id"]))
        rejected = [
            e
            for e in events
            if e.type == "task_finished" and e.payload["outcome"] == "invalid_task_output"
        ]
        assert len(rejected) == (1 if repair else 2)
        assert providers.count == 2


@pytest.mark.parametrize(
    "schema,field", [("AssessmentBatch", "assessments"), ("Synthesis", "units")]
)
async def test_oversized_generation_gets_one_repair_and_keeps_citations(settings, schema, field):
    class Verbose(Providers):
        count = 0

        def model_value(self, name, data):
            value = super().model_value(name, data)
            if name == schema:
                self.count += 1
                if self.count == 1:
                    value[field] *= 9
            return value

    providers = Verbose()
    async with running(settings, providers) as (_, client):
        saved = await submit(client)
        assert saved["status"] == "completed", saved
        assert saved["result"]["explanation"][0]["evidence_ids"]
        assert providers.count == 2


def test_generation_limits_do_not_invalidate_older_saved_assessments():
    value = Providers().model_value("AssessmentBatch", {"snapshot_id": "s1", "url": "https://test"})
    value["assessments"][0]["rationale"] = "A" * 301
    assert SavedAssessmentBatch.model_validate(value)
    with pytest.raises(ValueError):
        AssessmentBatch.model_validate(value)
    schema = Synthesis.model_json_schema()
    assert schema["properties"]["units"]["maxItems"] == 3
    assert schema["$defs"]["ExplanationUnit"]["properties"]["text"]["maxLength"] == 300


async def test_citation_repair_receives_safe_specific_guidance(settings):
    class BadReference(Providers):
        count = 0
        repairs = []

        async def handle(self, request):
            if request.url.path.endswith("completions"):
                body = json.loads(request.content)
                prompt = body["messages"][0]["content"]
                if "previous response failed" in prompt:
                    self.repairs.append(prompt)
            return await super().handle(request)

        def model_value(self, schema, data):
            value = super().model_value(schema, data)
            if schema == "AssessmentBatch":
                self.count += 1
                if self.count == 1:
                    value["assessments"][0]["citation"]["snapshot_id"] = "private-invented-id"
            return value

    providers = BadReference()
    async with running(settings, providers) as (app, client):
        saved = await submit(client)
        assert saved["status"] == "completed"
        assert providers.count == 2 and len(providers.repairs) == 1
        assert "Copy the exact supplied snapshot_id" in providers.repairs[0]
        assert "private-invented-id" not in providers.repairs[0]
        events = await app.state.storage.events(UUID(saved["id"]))
        rejected = [
            e.payload
            for e in events
            if e.type == "task_finished" and e.payload["outcome"] == "invalid_task_output"
        ]
        assert rejected[0]["validation_code"] == "citation_snapshot"
        assert "private-invented-id" not in json.dumps([e.model_dump(mode="json") for e in events])


async def test_explanation_checker_receives_explicit_zero_based_indices(settings):
    class TwoUnits(Providers):
        def model_value(self, schema, data):
            value = super().model_value(schema, data)
            if schema == "Synthesis":
                value["units"] *= 2
            if schema == "ExplanationCheck":
                assert [u["index"] for u in data["units"]] == [0, 1]
                value["supported_units"] = [u["index"] for u in data["units"]]
            return value

    async with running(settings, TwoUnits()) as (_, client):
        saved = await submit(client)
        assert saved["status"] == "completed"
        assert len(saved["result"]["explanation"]) == 2


@pytest.mark.parametrize(
    "options,reason",
    [
        ({"invalid_explanation": True}, "unsupported_explanation"),
        (
            {"almost": True, "invalid_correction": True, "relation": "contradicts"},
            "unsupported_correction",
        ),
    ],
)
async def test_final_semantic_rejection_is_auditable(settings, options, reason):
    async with running(settings, Providers(**options)) as (app, client):
        saved = await submit(client)
        assert saved["status"] == "failed" and saved["result"] is None
        events = await app.state.storage.events(UUID(saved["id"]))
        assert any(
            e.type == "task_output_rejected"
            and (
                reason in e.payload.get("failed_conditions", "")
                or (
                    reason == "unsupported_correction"
                    and "corrected_claim_supported" in e.payload.get("failed_conditions", "")
                )
            )
            for e in events
        )
