"""Acceptance evaluation must not leak labels or hide failed research."""

import importlib.util
import json
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from research_fixtures import Providers

from aletheia.api import create_app
from aletheia.evaluation import EvaluationCase, capture, load_cases, score, summarize

spec = importlib.util.spec_from_file_location(
    "evaluation_runner", Path(__file__).parents[1] / "scripts" / "evaluate_research.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.fixture
def case():
    return EvaluationCase.model_validate(
        {
            "id": "t001",
            "split": "tuning",
            "claim": "The Archive opened in 2000.",
            "case_type": "direct_fact",
            "expected": {
                "outcome": "decided",
                "verdict": "true",
                "unable_to_decide_reason": None,
                "expected_correction": None,
            },
            "acceptable_alternatives": [],
            "expected_flags": [],
            "key_sources": [
                {"url": "https://example.org/secret-label", "shows": "The reference source."}
            ],
            "as_of": "2026-11-05",
            "labelers": [],
            "status": "proposed",
            "reviewer_note": "Secret evaluator rationale; never send to the research model.",
        }
    )


@asynccontextmanager
async def session(settings, providers):
    app = create_app(replace(settings, research_enabled=True), provider_factory=providers.factory)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


async def test_capture_live_contract_without_label_leakage(settings, case):
    providers = Providers()
    async with session(settings, providers) as client:
        artifact = await capture(
            client, case, call_count=lambda: len(providers.calls), refresh=True
        )
    assert artifact["investigation"]["status"] == "completed"
    assert all(artifact["saved_checks"].values())
    refresh = artifact["refresh"]
    for name in (
        "separate_version",
        "idempotent_retry",
        "baseline_unchanged",
        "zero_provider_calls_on_retry_and_reads",
    ):
        assert refresh[name]
    assert refresh["comparison"]["comparison_status"] == "complete"
    inputs = json.dumps(providers.model_inputs)
    assert "Secret evaluator" not in inputs and "secret-label" not in inputs
    assert score(case, artifact)["decision_correct"] is True


@pytest.mark.parametrize("status", ["partial", "failed", "needs_clarification", "running"])
def test_noncompleted_matching_labels_count_as_wrong(case, status):
    artifact = {"investigation": {"status": status, "result": case.expected.model_dump()}}
    row = score(case, artifact)
    assert row["decision_correct"] is False
    summary = summarize([row], 2)
    assert summary["all"]["count"] == 1
    assert summary["all"]["provisional_accuracy_upper_bound"] == 0
    assert summary["not_run"] == 1
    assert not summary["human_acceptance_complete"]


async def test_failed_case_retains_events_and_counts_as_wrong(settings, case):
    providers = Providers(authentication_failure=True)
    async with session(settings, providers) as client:
        artifact = await capture(client, case, call_count=lambda: len(providers.calls))
    assert artifact["investigation"]["status"] == "failed"
    assert artifact["events"][-1]["type"] == "investigation_failed"
    assert score(case, artifact)["decision_correct"] is False
    assert "synthetic-provider-secret" not in json.dumps(artifact)


def test_almost_label_is_not_automatically_correct(case):
    data = case.model_dump()
    data["expected"]["verdict"] = "almost"
    data["expected"]["expected_correction"] = {
        "what_is_correct": "The named Archive opened.",
        "what_needs_correction": "The year was 2001, not 2000.",
        "corrected_claim": "The Archive opened in 2001.",
    }
    almost = EvaluationCase.model_validate(data)
    row = score(
        almost,
        {
            "investigation": {
                "status": "completed",
                "result": {
                    **almost.expected.model_dump(),
                    "almost_correction": {"corrected_claim": "Wrong!"},
                },
            }
        },
    )
    assert row["decision_correct"] is None
    assert row["almost_review"] == "pending_human_review"
    assert summarize([row], 1)["all"]["provisional_accuracy_lower_bound"] == 0


def test_conflict_and_insufficient_are_distinct(case):
    data = case.model_dump()
    data["expected"].update(
        outcome="unable_to_decide", verdict=None, unable_to_decide_reason="conflicting_evidence"
    )
    conflict = EvaluationCase.model_validate(data)
    result = {**data["expected"], "unable_to_decide_reason": "insufficient_evidence"}
    assert not score(conflict, {"investigation": {"status": "completed", "result": result}})[
        "decision_correct"
    ]


def test_invalid_or_duplicate_dataset_rejected_before_provider_calls(tmp_path, case):
    path = tmp_path / "claims.json"
    for value in ([], {}, [case.model_dump(), case.model_dump()]):
        path.write_text(json.dumps(value))
        with pytest.raises(ValueError):
            load_cases(path)
    data = case.model_dump()
    data["status"] = "reconciled"
    with pytest.raises(ValueError):
        EvaluationCase.model_validate(data)
    duplicate = case.model_dump()
    duplicate.update(id="t002", claim="  " + case.claim + "  ")
    path.write_text(json.dumps([case.model_dump(), duplicate]))
    with pytest.raises(ValueError, match="Duplicate requests"):
        load_cases(path)


def test_proposed_set_has_20_cases_and_no_fabricated_review():
    cases = load_cases(Path(__file__).parents[1] / "docs/evaluation/proposed-claims.json")
    assert len(cases) == 20
    assert all(c.status == "proposed" and not c.labelers for c in cases)
    assert {c.case_type for c in cases} == {
        "direct_fact",
        "comparison",
        "causal",
        "interpretive",
        "conflict",
        "insufficient",
    }


def test_default_cli_does_not_load_credentials_or_call_providers(monkeypatch, capsys):
    monkeypatch.setattr(
        runner.ProviderSettings,
        "from_environment",
        lambda **kwargs: pytest.fail("Offline validation loaded credentials"),
    )
    path = Path(__file__).parents[1] / "docs/evaluation/proposed-claims.json"
    assert runner.main(["--cases", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["live"] is False


def test_contested_results_are_reported_separately_and_flags_keep_type(case):
    row = score(case, {"investigation": {"status": "failed"}})
    other = {**row, "id": "t002", "label_status": "contested"}
    report = summarize([row, other], 2)
    assert report["all"]["count"] == 2
    assert report["excluding_contested"]["count"] == 1
    assert report["all"]["flags"]["narrow_scope"]["precision"] is None


async def test_network_meter_does_not_retain_private_inputs():
    import httpx

    attempts = []
    transport = runner.MeteredTransport("nebius", attempts)
    await transport.inner.aclose()
    transport.inner = httpx.MockTransport(lambda request: httpx.Response(401, text="secret-body"))
    async with httpx.AsyncClient(transport=transport) as client:
        await client.post(
            "https://test/secret-url",
            headers={"Authorization": "secret-key"},
            content="secret-prompt",
        )
    assert attempts[0]["status_code"] == 401
    assert "secret" not in json.dumps(attempts)


async def test_diagnostic_retains_truncation_code_without_response(monkeypatch):
    from dataclasses import asdict

    import httpx
    from pydantic import SecretStr

    from aletheia.budgets import RunBudget
    from aletheia.config import ProviderSettings
    from aletheia.providers.errors import ErrorCode, ProviderError
    from aletheia.research_contracts import ClaimPlan

    response = {
        "choices": [
            {"message": {"role": "assistant", "content": "private-body"}, "finish_reason": "length"}
        ]
    }
    monkeypatch.setattr(
        runner,
        "MeteredTransport",
        lambda *args: httpx.MockTransport(lambda request: httpx.Response(200, json=response)),
    )
    settings = ProviderSettings(nebius_api_key=SecretStr("private-key"), nebius_model="test")
    budgets = []
    async with runner.DiagnosticModel(settings, attempts=[], budgets=budgets) as model:
        with pytest.raises(ProviderError) as error:
            await model.generate(
                instructions="Return JSON",
                input_text="private-claim",
                response_type=ClaimPlan,
                budget=RunBudget(),
            )
    assert error.value.code == ErrorCode.TRUNCATED
    records = [asdict(a) for a in budgets[0].attempts]
    assert records[-1]["outcome"] == "truncated_output"
    assert "private" not in json.dumps(records)
