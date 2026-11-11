"""Regression checks for the four adversarial Phase 1 review findings; offline only."""

import pytest
from research_fixtures import Providers, terminal
from test_phase_one import analysis, assertion, comparison_spec, value
from test_research_integrity import judgment, source
from test_research_pipeline import running

from aletheia.direct import comparison_relation, validate_component_assessment
from aletheia.evidence import admit
from aletheia.passages import select_passages
from aletheia.phase_one_contracts import RecordedValue
from aletheia.tasks import TaskValidationError
from aletheia.verdicts import finding


@pytest.mark.parametrize(
    "text,extracted",
    [
        ("The observed value is -108.", "108"),
        ("The observed value is 108,000.", "108"),
        ("The observed value is 0.108.", "108"),
    ],
)
def test_cropped_source_text_must_not_change_numeric_value(text, extracted):
    src = source(text)
    item = judgment(
        src,
        relation="context",
        component_id="c1",
        values=[value("left", extracted, source_text=extracted)],
    )
    claim = assertion(
        "Venus is closer than Mercury.", kind="direct_comparison", comparison=comparison_spec()
    )
    with pytest.raises(TaskValidationError):
        validate_component_assessment(item, claim, src, {1})


class BalanceProviders(Providers):
    def __init__(self):
        super().__init__(text="Account A balance is -108 USD; Account B balance is 0 USD.")

    def model_value(self, schema, data):
        result = super().model_value(schema, data)
        spec = comparison_spec(
            left="Account A",
            right="Account B",
            metric="balance",
            operator="gt",
            units="USD",
            period="2026",
            population="accounts",
            definition="account balance",
        )
        if schema == "ClaimPlan":
            result["analysis"] = analysis(
                data["claim"], kind="direct_comparison", comparison=spec
            ).model_dump()
        if schema == "AssessmentBatch":
            item = result["assessments"][0]
            item["values"] = [
                RecordedValue(
                    **spec.model_dump(exclude={"left", "right", "operator", "exhaustive"}),
                    side=side,
                    entity=entity,
                    value=number,
                    kind="number",
                    exact=True,
                    source_text=number,
                ).model_dump()
                for side, entity, number in [
                    ("left", "Account A", "108"),
                    ("right", "Account B", "0"),
                ]
            ]
        if schema == "Synthesis":
            result["units"][0]["text"] = "Account A has the larger balance: 108 USD versus 0 USD."
        return result


async def test_cropped_negative_value_must_not_publish_true(settings):
    providers = BalanceProviders()
    async with running(settings, providers) as (_, client):
        response = await client.post(
            "/investigations", json={"claim": "Account A has a larger balance than Account B."}
        )
        saved = await terminal(client, response.json()["id"])
        assert not (saved["status"] == "completed" and saved["result"]["verdict"] == "true"), saved


def test_superlative_requires_a_distinct_comparison_member():
    spec = comparison_spec(left="Mercury", right="all other planets", exhaustive=True)
    values = [value("left", "58", entity="Mercury"), value("right", "58", entity="Mercury")]
    assert comparison_relation(spec, values) is None


async def test_self_comparison_must_not_publish_false_superlative(settings):
    class SelfComparison(Providers):
        def __init__(self):
            super().__init__(
                relation="contradicts",
                text="Mercury orbits at an average distance of 58 million km from the Sun.",
            )

        def model_value(self, schema, data):
            result = super().model_value(schema, data)
            spec = comparison_spec(left="Mercury", right="all other planets", exhaustive=True)
            if schema == "ClaimPlan":
                result["analysis"] = analysis(
                    data["claim"], kind="direct_comparison", comparison=spec
                ).model_dump()
            if schema == "AssessmentBatch":
                result["assessments"][0]["values"] = [
                    value(side, "58", entity="Mercury").model_dump() for side in ["left", "right"]
                ]
            if schema == "Synthesis":
                result["units"][0]["text"] = "The two distances are equal, so the claim is false."
            return result

    async with running(settings, SelfComparison()) as (_, client):
        response = await client.post(
            "/investigations", json={"claim": "Mercury is the closest planet to the Sun."}
        )
        saved = await terminal(client, response.json()["id"])
        assert not (saved["status"] == "completed" and saved["result"]["verdict"] == "false"), saved


def test_comparison_does_not_silently_drop_admitted_counterevidence():
    claim = assertion(
        "Venus is closer than Mercury.", kind="direct_comparison", comparison=comparison_spec()
    )
    sources, evidence = [], []
    for a, b, authoritative, relation in [
        ("50", "58", True, "supports"),
        ("108", "58", False, "contradicts"),
    ]:
        src = source(f"Venus: {a}; Mercury: {b}.")
        item = judgment(
            src,
            component_id="c1",
            relation=relation,
            authoritative_record=authoritative,
            values=[value("left", a), value("right", b)],
        )
        validate_component_assessment(item, claim, src, {1})
        sources.append(src)
        evidence.append(admit(item, src, {1}))
    assert all(e.admissible for e in evidence)
    computed = finding(claim, "quick", evidence, sources)[0]
    assert computed.verdict is None, computed
    assert computed.unable_to_decide_reason == "conflicting_evidence"


def test_evidence_heading_is_not_navigation_boilerplate():
    claim = assertion("The Archive opened in 2000.")
    src = source("# The Archive opened in 2000.\nVisitor information and opening hours.")
    selected = select_passages(claim, src)
    assert any("2000" in span.text for span in selected), selected


async def test_supported_single_operand_records_can_be_joined(settings):
    class IndividualRecords(Providers):
        def __init__(self):
            super().__init__(
                source_count=2, deep=True, text="Venus: 108 million km; Mercury: 58 million km."
            )

        def model_value(self, schema, data):
            result = super().model_value(schema, data)
            if schema == "ClaimPlan":
                result["analysis"] = analysis(
                    data["claim"], kind="direct_comparison", comparison=comparison_spec()
                ).model_dump()
            if schema == "AssessmentBatch":
                side, number = ("left", "108") if data["url"].endswith("/0") else ("right", "58")
                result["assessments"][0]["values"] = [value(side, number).model_dump()]
                # Each authoritative passage supports an operand, not the overall inequality.
                result["assessments"][0]["relation"] = "context"
            return result

    async with running(settings, IndividualRecords()) as (_, client):
        response = await client.post(
            "/investigations", json={"claim": "Venus is closer than Mercury."}
        )
        saved = await terminal(client, response.json()["id"])
        assert saved["result"]["verdict"] == "false", saved


@pytest.mark.parametrize(
    "text,extracted",
    [
        ("The observed value is -108.", "108"),
        ("The observed value is 108,000.", "108"),
        ("The observed value is 0.108.", "108"),
    ],
)
def test_control_full_citation_rejects_changed_numeric_value(text, extracted):
    src = source(text)
    item = judgment(
        src,
        relation="context",
        component_id="c1",
        values=[value("left", extracted, source_text=text)],
    )
    claim = assertion(
        "Venus is closer than Mercury.", kind="direct_comparison", comparison=comparison_spec()
    )
    with pytest.raises(TaskValidationError):
        validate_component_assessment(item, claim, src, {1})


def test_control_distinct_planet_is_a_valid_superlative_counterexample():
    spec = comparison_spec(right="all other planets", exhaustive=True)
    assert comparison_relation(spec, [value("left", "108"), value("right", "58")]) == "contradicts"


def test_control_two_authoritative_comparisons_remain_conflicting():
    claim = assertion(
        "Venus is closer than Mercury.", kind="direct_comparison", comparison=comparison_spec()
    )
    sources, evidence = [], []
    for a, b, relation in [("50", "58", "supports"), ("108", "58", "contradicts")]:
        src = source(f"Venus: {a}; Mercury: {b}.")
        item = judgment(
            src,
            component_id="c1",
            relation=relation,
            authoritative_record=True,
            values=[value("left", a), value("right", b)],
        )
        validate_component_assessment(item, claim, src, {1})
        sources.append(src)
        evidence.append(admit(item, src, {1}))
    assert (
        finding(claim, "quick", evidence, sources)[0].unable_to_decide_reason
        == "conflicting_evidence"
    )


def test_control_identical_fact_in_paragraph_is_selected():
    claim = assertion("The Archive opened in 2000.")
    src = source("The Archive opened in 2000.\nVisitor information and opening hours.")
    assert any("2000" in span.text for span in select_passages(claim, src))
