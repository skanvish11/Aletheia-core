"""Phase-one contract checks using saved pilot passages and offline HTTP adapters.

Historical labels/results remain untouched. These are development regressions,
not model-quality evaluation or evidence that these judgments generalize.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from research_fixtures import Providers, terminal
from test_research_integrity import judgment, source
from test_research_pipeline import running, submit

from aletheia.api import create_app
from aletheia.claims import validate_claim
from aletheia.direct import comparison_relation, validate_component_assessment
from aletheia.evidence import admit
from aletheia.passages import select_passages
from aletheia.phase_one_contracts import ClaimAnalysis, ComparisonSpec, RecordedValue
from aletheia.planning import validate_plan
from aletheia.research_contracts import Assertion, Evidence, SearchPlan, SnapshotMetadata, Span
from aletheia.task_contracts import ClaimPlan
from aletheia.tasks import TaskValidationError
from aletheia.verdicts import finding

HANDOFF = Path(__file__).resolve().parents[1] / "docs/evaluation/pilot-handoff"


def pilot(case):
    return json.loads((HANDOFF / f"rerun/cases/{case}.json").read_text())


def analysis(claim, *, kind="direct_fact", components=None, comparison=None):
    return ClaimAnalysis(
        primary_type=kind,
        scope="complete",
        required_method={
            "direct_fact": "record_lookup",
            "direct_comparison": "record_comparison",
        }.get(kind, kind),
        supported=kind in {"direct_fact", "direct_comparison"},
        reason="Reviewed development case.",
        missing_scope=[],
        components=components
        or [
            {
                "id": "c1",
                "text": claim,
                "role": "essential",
                "subject": "Named subject",
                "predicate": "Submitted proposition",
                "timeframe": None,
                "location_or_population": None,
                "comparison": comparison,
            }
        ],
    )


def assertion(claim, **kwargs):
    return Assertion(
        text=claim,
        kind="direct_record",
        consequential=False,
        recommended_route="quick",
        analysis=analysis(claim, **kwargs),
    )


def comparison_spec(**updates):
    return ComparisonSpec(
        **{
            "left": "Venus",
            "right": "Mercury",
            "metric": "average orbital distance",
            "operator": "lt",
            "units": "million km",
            "period": "orbital average",
            "population": "Solar System planets",
            "definition": "distance from the Sun",
            "exhaustive": False,
            **updates,
        }
    )


def value(side, number, **updates):
    spec = comparison_spec()
    return RecordedValue(
        **{
            **spec.model_dump(exclude={"left", "right", "operator", "exhaustive"}),
            "side": side,
            "entity": spec.left if side == "left" else spec.right,
            "value": number,
            "kind": "number",
            "exact": True,
            "source_text": number,
            **updates,
        }
    )


class PlannedProviders(Providers):
    def __init__(self, parsed, **options):
        super().__init__(**options)
        self.parsed = parsed

    def model_value(self, schema, data):
        result = super().model_value(schema, data)
        if schema == "ClaimPlan":
            result["analysis"] = self.parsed.model_dump()
        return result


def test_b0001_relevant_saved_span_reaches_assessment_and_effort_does_not_change_verdict():
    record = json.loads((HANDOFF / "apollo-selection.json").read_text())
    saved = pilot("b0001")
    claim = assertion(saved["investigation"]["claim"])
    excluded = record["excluded_relevant_span"]
    spans = [Span.model_validate(s) for s in record["supplied_spans"] + [excluded]]
    selected = select_passages(claim, SimpleNamespace(spans=spans))
    assert excluded["id"] in {s.id for s in selected}
    assert sum(len(s.text) for s in selected) <= 12000
    assert next(s for s in selected if s.id == excluded["id"]).text == excluded["text"]
    sources = [SnapshotMetadata.model_validate(s) for s in saved["evidence"]["sources"]]
    evidence = [Evidence.model_validate(e) for e in saved["evidence"]["evidence"]]
    for item in evidence:
        item.assessment.component_id = "c1"
    quick = finding(claim, "quick", evidence, sources)[0]
    deep = finding(claim, "deep", evidence, sources)[0]
    assert quick == deep
    assert quick.verdict == "true"


def test_b0002_saved_operands_reject_reversed_support():
    saved = pilot("b0002")
    passage = next(
        e["excerpts"][0]["text"]
        for e in saved["evidence"]["evidence"]
        if "58 million km" in e["excerpts"][0]["text"]
    )
    src = source(passage)
    claim = assertion(
        saved["investigation"]["claim"],
        kind="direct_comparison",
        comparison=comparison_spec(exhaustive=True, right="all other planets"),
    )
    item = judgment(src)
    item.component_id = "c1"
    item.values = [value("left", "108"), value("right", "58")]
    supplied = {s.id for s in src.spans}
    item.citation.span_ids = sorted(supplied)
    with pytest.raises(TaskValidationError, match="deterministic comparison"):
        validate_component_assessment(item, claim, src, supplied)
    item.relation = "contradicts"
    validate_component_assessment(item, claim, src, supplied)
    computed = finding(claim, "deep", [admit(item, src, supplied)], [src])[0]
    assert computed.verdict == "false"
    assert computed.unable_to_decide_reason is None


@pytest.mark.parametrize(
    "changes",
    [
        {"units": "km"},
        {"period": "today"},
        {"population": "different population"},
        {"definition": "distance from Earth"},
        {"metric": "diameter"},
        {"exact": False},
        {"entity": "Earth"},
        {"value": "NaN"},
        {"kind": "date", "value": "2020-01-01"},
    ],
)
def test_incompatible_or_uncertain_operands_cannot_decide(changes):
    assert (
        comparison_relation(
            comparison_spec(), [value("left", "108"), value("right", "58", **changes)]
        )
        is None
    )


def test_comparison_can_join_separate_sources_but_each_operand_needs_evidence():
    spec = comparison_spec()
    claim = assertion("Venus is closer than Mercury.", kind="direct_comparison", comparison=spec)
    sources, evidence = [], []
    for side, number in [("left", "108"), ("right", "58")]:
        src = source(number)
        item = judgment(src, relation="context")
        item.component_id, item.values = "c1", [value(side, number)]
        sources.append(src)
        evidence.append(admit(item, src, {1}))
    assert finding(claim, "deep", evidence[:1], sources)[0].verdict is None
    assert finding(claim, "deep", evidence, sources)[0].verdict == "false"
    evidence[1].assessment.authoritative_record = False
    assert finding(claim, "quick", evidence, sources)[0].verdict is None


@pytest.mark.parametrize(
    "kind",
    ["causal", "prediction", "counterfactual", "scientific_inference", "interpretive", "mixed"],
)
async def test_unsupported_method_is_separate_persisted_and_has_no_search(settings, kind):
    claim = pilot("b0004")["investigation"]["claim"]
    parsed = analysis(claim, kind=kind)
    providers = PlannedProviders(parsed)
    async with running(settings, providers) as (_, client):
        initial = await client.post("/investigations", json={"claim": claim})
        saved = await terminal(client, initial.json()["id"])
        assert saved["status"] == "completed" and saved["stop_reason"] == "unsupported_method"
        assert saved["result"] is None and saved["clarification_questions"] is None
        assert saved["method_limitation"]["analysis"]["required_method"] == kind
        assert saved["method_limitation"]["original_claim"] == claim
        assert "/search" not in providers.calls
        assert (await client.post("/investigations", json={"claim": claim})).json() == saved
    calls = len(providers.calls)
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        assert (await client.get(saved["links"]["self"])).json() == saved
    assert len(providers.calls) == calls


def date_components(claim, modifier):
    base = analysis(claim).components[0].model_dump()
    base["text"] = claim.split(", ", 2)[2]
    return [
        base,
        {
            **base,
            "id": "c2",
            "text": modifier,
            "role": "modifier",
            "predicate": "date of named event",
        },
    ]


@pytest.mark.parametrize(
    "case,modifier,anchor",
    [
        ("b0023", "discovered in Egypt in 1798", "1799"),
        ("b0028", "adopted in 1986", "1987"),
    ],
)
def test_saved_date_modifiers_cannot_be_swallowed_by_main_proposition(case, modifier, anchor):
    saved = pilot(case)
    text = saved["investigation"]["claim"]
    claim = assertion(text, components=date_components(text, modifier))
    passage = next(
        x["text"]
        for e in saved["evidence"]["evidence"]
        for x in e["excerpts"]
        if anchor in x["text"]
    )
    src = source(passage)
    evidence = []
    for component, relation in [("c1", "supports"), ("c2", "contradicts")]:
        item = judgment(src, relation=relation)
        item.component_id = component
        evidence.append(admit(item, src, {1}))
    computed = finding(claim, "quick", evidence, [src])[0]
    assert computed.verdict is None
    assert [c.outcome for c in computed.components] == ["supported", "contradicted"]
    assert computed.unable_to_decide_reason == "insufficient_evidence"
    # This is a bounded correction candidate, not a fabricated inter-source conflict.
    assert finding(claim, "quick", evidence[:1], [src])[0].verdict is None


async def test_b0028_invalid_later_assessment_preserves_saved_evidence(settings):
    saved = pilot("b0028")
    text = saved["investigation"]["claim"]
    passage = "\n".join(x["text"] for x in saved["evidence"]["evidence"][0]["excerpts"])

    class BadSecond(PlannedProviders):
        def model_value(self, schema, data):
            result = super().model_value(schema, data)
            if schema == "AssessmentBatch":
                if data["url"].endswith("/1"):
                    result["assessments"][0]["citation"]["snapshot_id"] = "invented"
                else:
                    first = result["assessments"][0]
                    first["citation"]["span_ids"] = [1]
                    second = json.loads(json.dumps(first))
                    second.update(component_id="c2", relation="contradicts")
                    second["citation"]["span_ids"] = [2]
                    result["assessments"].append(second)
            return result

    providers = BadSecond(
        analysis(text, components=date_components(text, "adopted in 1986")),
        text=passage,
        source_count=2,
        deep=True,
    )
    async with running(settings, providers) as (_, client):
        initial = await client.post("/investigations", json={"claim": text})
        result = await terminal(client, initial.json()["id"])
        assert result["status"] == "partial"
        assert result["stop_reason"] == "invalid_task_output"
        assert result["result"]["verdict"] is None
        evidence = (await client.get(result["links"]["evidence"])).json()["evidence"]
        assert len(evidence) == 2
        assert {e["assessment"]["component_id"] for e in evidence} == {"c1", "c2"}
        assert "1987" in evidence[1]["excerpts"][0]["text"]


@pytest.mark.parametrize("recover", [True, False])
async def test_b0006_final_check_diagnostics_and_bounded_repair(settings, recover):
    saved = pilot("b0006")
    text = saved["investigation"]["claim"]
    passage = saved["evidence"]["evidence"][0]["excerpts"][0]["text"]

    class RejectOnce(PlannedProviders):
        checks = 0

        def model_value(self, schema, data):
            result = super().model_value(schema, data)
            if schema == "Synthesis":
                result["units"][0]["text"] = passage
            if schema == "ExplanationCheck":
                self.checks += 1
                if self.checks == 1 or not recover:
                    result["supported_units"] = []
            return result

    providers = RejectOnce(analysis(text), text=passage)
    async with running(settings, providers) as (_, client):
        initial = await client.post("/investigations", json={"claim": text})
        result = await terminal(client, initial.json()["id"])
        assert providers.checks == 2
        assert result["status"] == ("completed" if recover else "failed")
        if recover:
            assert result["result"]["verdict"] == "true"
        else:
            assert result["result"] is None and result["stop_reason"] == "semantic_rejection"
        assert (await client.get(result["links"]["evidence"])).json()["evidence"]
        artifacts = list(settings.database_path.parent.glob("*.diagnostics/*.json"))
        assert len(artifacts) == (1 if recover else 2)
        diagnostic = json.loads(artifacts[0].read_text())
        assert diagnostic["failed_conditions"] == ["unsupported_explanation"]
        assert diagnostic["affected_units"] == [0]
        assert diagnostic["rejected_explanation"][0]["text"] == passage
        assert artifacts[0].stat().st_mode & 0o077 == 0
        public = (await client.get(result["links"]["events"])).text
        assert "rejected_explanation" not in public


def test_over_capacity_search_plan_fails_before_any_search():
    data = Providers().model_value("SearchPlan", {"previous_queries": [], "gap": None})
    plan = SearchPlan.model_validate(data)
    with pytest.raises(TaskValidationError, match="remaining search capacity"):
        validate_plan(plan, set(), True, capacity=1)


def test_parser_cannot_drop_or_rewrite_date_modifier():
    claim = pilot("b0023")["investigation"]["claim"]
    plan = Providers().model_value("ClaimPlan", {"claim": claim})
    plan["analysis"]["components"][0]["text"] = "helped scholars decipher Egyptian hieroglyphs"
    with pytest.raises(TaskValidationError, match="material detail"):
        validate_claim(ClaimPlan.model_validate(plan), claim)


async def test_route_review_can_correct_initial_method_with_audit_reason(settings):
    class Revised(Providers):
        interpretations = 0

        def model_value(self, schema, data):
            result = super().model_value(schema, data)
            if schema == "ClaimPlan":
                self.interpretations += 1
                if self.interpretations == 1:
                    result["analysis"] = analysis(
                        data["claim"], kind="scientific_inference"
                    ).model_dump()
            return result

    providers = Revised()
    async with running(settings, providers) as (app, client):
        saved = await submit(client)
        assert saved["result"]["verdict"] == "true"
        events = await app.state.storage.events(UUID(saved["id"]))
        revision = next(e for e in events if e.type == "route_revised")
        assert revision.payload["previous_method"] == "scientific_inference"
        assert revision.payload["method"] == "record_lookup"
        assert revision.payload["reason"]


async def test_denied_later_search_does_not_discard_completed_searches(settings):
    from aletheia.budgets import RunBudget
    from aletheia.providers.errors import ErrorCode, ProviderError

    class DenySecondSearch(RunBudget):
        def check(self, provider, operation, units):
            if operation == "search" and self.used["search"] == 1:
                raise ProviderError("tavily", ErrorCode.BUDGET)
            super().check(provider, operation, units)

    providers = Providers()
    async with running(settings, providers, budget_factory=DenySecondSearch) as (_, client):
        saved = await submit(client)
        assert providers.calls.count("/search") == 1
        assert providers.calls.count("/extract") == 1
        assert saved["status"] == "partial"
        assert saved["stop_reason"] == "budget_exhausted"
        assert saved["result"]["verdict"] == "true"
        assert saved["result"]["explanation"]


async def test_failed_decision_check_never_publishes_true(settings):
    class RejectedDecision(Providers):
        def model_value(self, schema, data):
            result = super().model_value(schema, data)
            if schema == "ExplanationCheck":
                result["decision_supported"] = False
                result["rejected_component_ids"] = ["c1"]
            return result

    providers = RejectedDecision()
    async with running(settings, providers) as (_, client):
        saved = await submit(client)
        assert saved["result"] is None
        assert saved["stop_reason"] == "semantic_rejection"
        assert len([n for n, _ in providers.model_inputs if n == "ExplanationCheck"]) == 2
        records = [
            json.loads(p.read_text())
            for p in settings.database_path.parent.glob("*.diagnostics/*.json")
        ]
        assert all(r["failed_conditions"] == ["unsupported_decision"] for r in records)
        assert all(r["component_ids"] == ["c1"] for r in records)


async def test_diagnostic_write_failure_does_not_replace_semantic_failure(settings, monkeypatch):
    original = Path.mkdir

    def fail_diagnostics(path, *args, **kwargs):
        if path.name.endswith(".diagnostics"):
            raise OSError("synthetic-private-path")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_diagnostics)
    async with running(settings, Providers(invalid_explanation=True)) as (_, client):
        saved = await submit(client)
        assert saved["result"] is None and saved["stop_reason"] == "semantic_rejection"
        assert "synthetic-private-path" not in json.dumps(saved)


async def test_unsupported_terminal_write_is_atomic_and_refreshable(tmp_path, monkeypatch):
    import sqlite3

    from aletheia.contracts import InvestigationRequest
    from aletheia.phase_one_contracts import UnsupportedMethod
    from aletheia.storage import Storage, StorageError

    storage = Storage(tmp_path / "atomic.sqlite3")
    await storage.initialize()
    original = await storage.submit(InvestigationRequest(claim="A prediction."))
    run = await storage.claim_next()
    limited = UnsupportedMethod(
        original_claim=run.claim,
        analysis=analysis(run.claim, kind="prediction"),
        explanation="Prediction unsupported.",
    )
    append = storage._append_event

    async def fail(*args, **kwargs):
        raise sqlite3.OperationalError("synthetic-private-error")

    monkeypatch.setattr(storage, "_append_event", fail)
    with pytest.raises(StorageError):
        await storage.finish(
            run.id, status="completed", stop_reason="unsupported_method", method_limitation=limited
        )
    saved = await storage.get(run.id)
    assert saved.status == "running" and saved.method_limitation is None
    assert not await storage.records(run.id, "unsupported_method", UnsupportedMethod)
    monkeypatch.setattr(storage, "_append_event", append)
    await storage.finish(
        run.id, status="completed", stop_reason="unsupported_method", method_limitation=limited
    )
    restarted = Storage(storage.path)
    await restarted.initialize()
    saved = await restarted.get(original.id)
    assert saved.method_limitation == limited
    assert saved.links.refresh
    refreshed = await restarted.refresh(original.id, "phase-one-retry")
    assert refreshed.parent_id == original.id and refreshed.version == 2
    assert (await restarted.get(original.id)).method_limitation == limited


def test_missing_component_cannot_become_true():
    claim = assertion(
        "A opened in 2000, in Rome.",
        components=[
            {
                "id": "c1",
                "text": "A opened in 2000",
                "role": "essential",
                "subject": "A",
                "predicate": "opened",
                "timeframe": "2000",
                "location_or_population": None,
                "comparison": None,
            },
            {
                "id": "c2",
                "text": "in Rome",
                "role": "modifier",
                "subject": "A",
                "predicate": "location",
                "timeframe": None,
                "location_or_population": "Rome",
                "comparison": None,
            },
        ],
    )
    src = source("A opened in 2000.")
    item = judgment(src)
    item.component_id = "c1"
    computed = finding(claim, "quick", [admit(item, src, {1})], [src])[0]
    assert computed.verdict is None
    assert computed.components[1].outcome == "not_established"


def test_dates_properties_superlatives_and_forged_values():
    spec = comparison_spec(units="ISO date", operator="lt")
    dates = [
        value("left", "2000-01-01", units="ISO date", kind="date"),
        value("right", "2001-01-01", units="ISO date", kind="date"),
    ]
    assert comparison_relation(spec, dates) == "supports"
    props = [value("left", "solid", kind="property"), value("right", "solid", kind="property")]
    assert comparison_relation(comparison_spec(operator="eq"), props) == "supports"
    assert (
        comparison_relation(
            comparison_spec(exhaustive=True), [value("left", "1"), value("right", "2")]
        )
        is None
    )
    src = source("The value is 1080.")
    item = judgment(src, relation="context")
    item.component_id = "c1"
    item.values = [value("left", "108", source_text="The value is 1080.")]
    claim = assertion(
        "Venus is closer than Mercury.", kind="direct_comparison", comparison=comparison_spec()
    )
    with pytest.raises(TaskValidationError):
        validate_component_assessment(item, claim, src, {1})


async def test_b0023_cited_date_correction_can_finish_as_almost(settings):
    saved = pilot("b0023")
    claim = saved["investigation"]["claim"]
    passage = next(
        x["text"]
        for e in saved["evidence"]["evidence"]
        for x in e["excerpts"]
        if "campaign in Egypt in 1798" in x["text"]
    )

    class DateCorrection(PlannedProviders):
        def model_value(self, schema, data):
            result = super().model_value(schema, data)
            if schema == "AssessmentBatch":
                first = result["assessments"][0]
                first["citation"]["span_ids"] = [s["id"] for s in data["spans"]]
                second = json.loads(json.dumps(first))
                second.update(component_id="c2", relation="contradicts")
                result["assessments"].append(second)
            if schema == "Synthesis":
                ids = [e["id"] for e in data["evidence"]]
                result["units"] = [
                    {
                        "text": "The discovery was in 1799; 1798 was the campaign year.",
                        "evidence_ids": ids,
                    }
                ]
                result["almost_correction"] = {
                    "what_is_correct": {
                        "text": "The stone helped decipher hieroglyphs.",
                        "evidence_ids": ids,
                    },
                    "what_needs_correction": {
                        "text": "The discovery year was 1799, not 1798.",
                        "evidence_ids": ids,
                    },
                    "corrected_claim": {"text": claim.replace("1798", "1799"), "evidence_ids": ids},
                }
            return result

    providers = DateCorrection(
        analysis(claim, components=date_components(claim, "discovered in Egypt in 1798")),
        text=passage,
        almost=True,
    )
    async with running(settings, providers) as (_, client):
        initial = await client.post("/investigations", json={"claim": claim})
        result = await terminal(client, initial.json()["id"])
        assert result["status"] == "completed"
        assert result["result"]["verdict"] == "almost"
        assert result["result"]["assertion"]["text"] == claim
        assert "1799" in result["result"]["almost_correction"]["corrected_claim"]["text"]
        assert [c["outcome"] for c in result["result"]["finding"]["components"]] == [
            "supported",
            "contradicted",
        ]


@pytest.mark.parametrize(
    "quoted,extracted,valid",
    [
        ("The value is -108.", "108", False),
        ("The value is −108.", "108", False),
        ("The value is −108.", "-108", True),
        ("The value is 108,000.", "108", False),
        ("The value is 108,000.", "108000", True),
        ("The value is -108.", "-108", True),
        ("The value is 108.", "108", True),
    ],
)
def test_numeric_grounding_preserves_sign_and_thousands(quoted, extracted, valid):
    src = source(quoted)
    item = judgment(src, relation="context")
    item.component_id = "c1"
    item.values = [value("left", extracted, source_text=quoted)]
    claim = assertion(
        "Venus is closer than Mercury.", kind="direct_comparison", comparison=comparison_spec()
    )
    if valid:
        validate_component_assessment(item, claim, src, {1})
    else:
        with pytest.raises(TaskValidationError):
            validate_component_assessment(item, claim, src, {1})
