"""The basis check: what code enforces before the verdict call's true or false is kept.

The model's readings below are scripted. These tests check how code combines them; they
cannot measure whether a real model reads pages correctly (see evals/provenance).
"""

import json

from test_simple_pipeline import Fake, answer, check, reading

from aletheia.one_call import Answer, basis_check, same_party, validate_answer

PAGES = [
    "Voltreon Labs report VL-1. In our continuous video-playback test at 200 nits, the "
    "Kestrel 7 ran for 20 hours.",
    "Gadgetline: the Kestrel 7 lasted 20 hours in a lab test, Voltreon Labs said.",
    "Ferrin Review test FR-9. At 200 nits, our video-playback test of the Kestrel 7 ran "
    "for 20 hours.",
]
OFFERED = [{"page": i, "passages": [text]} for i, text in enumerate(PAGES, start=1)]
QUOTE = {
    1: "the Kestrel 7 ran for 20 hours.",
    2: "the Kestrel 7 lasted 20 hours in a lab test",
    3: "the Kestrel 7 ran for 20 hours.",
}


def lab(page, **changes):
    value = {
        "page": page,
        "basis": "documented_record",
        "record": "Voltreon Labs report VL-1",
        "producer": "Voltreon Labs",
        "presentation": "original",
        "producer_owns_page": "yes",
        "conditions": "video playback at 200 nits",
        "record_date": "unknown",
        "evidence": ["Voltreon Labs report VL-1."],
    }
    return value | changes


def judged(sources, verdict="true", pages=(1,), **fields):
    value = {
        "claim_about": "the_fact_itself",
        "named_source": "none",
        "needs_test_conditions": True,
        "sources": sources,
        "original_record_not_supplied": "none",
        "verdict": verdict,
        "quotes": [{"page": p, "text": QUOTE[p]} for p in pages],
        "reason": "r",
    } | fields
    return validate_answer(Answer.model_validate(value), OFFERED, PAGES)


def test_one_original_record_on_its_producers_site_settles_a_direct_fact():
    state = judged([lab(1)])
    assert state["verdict"] == "true" and state["basis"]["route"] == "original_record"
    assert state["basis"]["pages"] == [1]


def test_an_authoritative_label_without_a_known_producer_or_record_is_not_enough():
    for change in ({"producer": "unknown"}, {"record": "Unknown"}, {"producer": "N/A"}):
        state = judged([lab(1, **change)])
        assert state["verdict"] == "cannot_settle" and state["basis_withheld"]


def test_provenance_passages_must_be_on_the_page():
    state = judged([lab(1, evidence=["Voltreon Labs certified report VL-1."])])
    assert state["verdict"] == "cannot_settle"
    assert state["basis"]["notes"][0]["why"] == "provenance_not_on_page"


def test_a_credited_page_must_carry_a_verdict_quotation():
    # Page 1 is a fine record, but the verdict quotes only the secondhand page 2.
    state = judged([lab(1), lab(2, presentation="attributed", producer_owns_page="no")], pages=(2,))
    assert state["verdict"] == "cannot_settle"


def test_a_record_on_a_site_the_producer_does_not_own_does_not_settle_alone():
    state = judged([lab(1, producer_owns_page="no")])
    assert state["verdict"] == "cannot_settle"
    state = judged([lab(1, producer_owns_page="unknown")])
    assert state["verdict"] == "cannot_settle"


def test_reports_of_one_producers_record_count_once():
    attributed = {"presentation": "attributed", "producer_owns_page": "no"}
    reports = [
        lab(1, **attributed),
        lab(2, **attributed, evidence=["Voltreon Labs said."]),
        # The same producer, written differently, is still one producer.
        lab(3, **attributed, producer="voltreon labs, inc.", evidence=["Ferrin Review test FR-9."]),
    ]
    state = judged(reports, pages=(1, 2, 3))
    assert state["verdict"] == "cannot_settle"
    assert state["basis"]["producers"] == ["voltreon labs"]


def test_documented_records_from_two_producers_corroborate():
    attributed = {"presentation": "attributed", "producer_owns_page": "no"}
    records = [
        lab(1, **attributed),
        lab(3, **attributed, producer="Ferrin Review", evidence=["Ferrin Review test FR-9."]),
    ]
    state = judged(records, pages=(1, 3))
    assert state["verdict"] == "true" and state["basis"]["route"] == "independent_records"


def test_unknown_origins_and_non_records_earn_no_corroboration_credit():
    attributed = {"presentation": "attributed", "producer_owns_page": "no"}
    weak = [
        lab(1, **attributed, producer="unknown"),
        lab(
            2,
            **attributed,
            basis="secondhand_report",
            producer="Gadgetline",
            evidence=["Voltreon Labs said."],
        ),
        lab(
            3,
            **attributed,
            basis="personal_anecdote",
            producer="A reader",
            evidence=["Ferrin Review test FR-9."],
        ),
    ]
    assert judged(weak, pages=(1, 2, 3))["verdict"] == "cannot_settle"


def test_a_measurement_needs_its_recorded_conditions():
    assert judged([lab(1, conditions="unknown")])["verdict"] == "cannot_settle"
    # A fact that does not depend on how it was measured needs none.
    assert judged([lab(1, conditions="unknown")], needs_test_conditions=False)["verdict"] == "true"


def test_one_announcement_settles_what_was_announced_but_not_the_fact():
    release = lab(1, basis="statement_or_announcement", producer="Corvane")
    about_source = judged(
        [release], claim_about="what_a_named_source_said_or_published", named_source="Corvane"
    )
    assert about_source["verdict"] == "true"
    assert judged([release])["verdict"] == "cannot_settle"
    # The publication must be the named source's own.
    other = judged(
        [release], claim_about="what_a_named_source_said_or_published", named_source="Pelora"
    )
    assert other["verdict"] == "cannot_settle"


def test_false_needs_the_same_basis_and_weak_contradiction_is_insufficient():
    assert judged([lab(1)], verdict="false")["verdict"] == "false"
    bare = lab(1, basis="unsupported_assertion", producer="unknown")
    assert judged([bare], verdict="false")["verdict"] == "cannot_settle"


def test_withheld_verdict_names_what_is_missing_and_the_unread_original():
    state = judged(
        [
            lab(
                2,
                basis="secondhand_report",
                presentation="attributed",
                producer_owns_page="no",
                evidence=["Voltreon Labs said."],
            )
        ],
        pages=(2,),
        original_record_not_supplied="Voltreon Labs report VL-1",
    )
    assert state["verdict"] == "cannot_settle"
    assert "secondhand reports" in state["reason"]
    assert "with its test conditions" in state["reason"]
    assert "Voltreon Labs report VL-1, which was not read" in state["reason"]


def test_same_party_matches_names_and_acronyms_only():
    assert same_party("U.S. Geological Survey", "USGS")
    assert same_party("World Health Organization", "WHO")
    assert same_party("Corvane Inc.", "Corvane")
    assert not same_party("Corvane", "Pelora")
    assert not basis_check(
        Answer.model_validate(
            {
                "claim_about": "what_a_named_source_said_or_published",
                "named_source": "none",
                "needs_test_conditions": False,
                "sources": [lab(1, basis="statement_or_announcement")],
                "original_record_not_supplied": "none",
                "verdict": "true",
                "quotes": [{"page": 1, "text": QUOTE[1]}],
                "reason": "r",
            }
        ),
        [{"page": 1, "text": QUOTE[1]}],
        PAGES,
    )["qualifies"]


async def test_a_withheld_verdict_publishes_nothing_and_searches_for_the_record(settings):
    weak = answer(
        "true",
        sources=[
            reading(
                basis="secondhand_report",
                presentation="attributed",
                producer_owns_page="no",
                producer="unknown",
            )
        ],
        original_record_not_supplied="The Archive's founding charter",
    )
    fake = Fake([weak, weak])
    saved, evidence, events = await check(settings, fake)
    assert saved["result"]["verdict"] is None
    assert saved["result"]["unable_to_decide_reason"] == "insufficient_evidence"
    # Quotations are kept as context only; none is published as support.
    assert {e["assessment"]["relation"] for e in evidence["evidence"]} <= {"context"}
    assert not any(e["assessment"]["authoritative_record"] for e in evidence["evidence"])
    rejected = [e["payload"] for e in events if e["type"] == "task_output_rejected"]
    assert {"task": "verdict", "reason": "no_qualifying_basis"} in rejected
    gap = next(e["payload"]["gap"] for e in events if e["type"] == "followup_planned")
    assert "The Archive's founding charter" in gap
    # The follow-up plan is asked to look for the named original record.
    plans = [json.loads(m[1]["content"]) for t, m in fake.inputs if t == "Queries"]
    assert "The Archive's founding charter" in plans[1]["missing"]


async def test_saved_evidence_carries_the_provenance_the_verdict_rested_on(settings):
    fake = Fake([answer("true")])
    saved, evidence, _ = await check(settings, fake)
    assert saved["result"]["verdict"] == "true"
    assessment = evidence["evidence"][0]["assessment"]
    assert assessment["authoritative_record"] is True
    assert assessment["origin"] == "The Archive" and assessment["publisher"] == "The Archive"
    assert assessment["provenance_span_ids"] == [1]
    assert assessment["provenance_note"].startswith("documented_record, original")
    assert saved["result"]["prompt_version"] == "one-call-v3"


def test_a_provenance_row_copied_from_a_table_is_matched_like_the_table():
    from aletheia.one_call import provenance_on_page

    page = (
        "| Rank | Model | Score |\n| --- | --- | --- |\n| 1 | Arvo-3 | 71.4% |\n"
        "| 2 | Tessel-L | 69.8% |\n"
    )
    assert provenance_on_page(page, "| 1 | Arvo-3 | 71.4% |")
    assert not provenance_on_page(page, "| 1 | Arvo-3 | 69.8% |")


def test_an_official_reference_page_settles_a_fact_but_a_commercial_one_does_not():
    from aletheia.one_call import reference_site

    copy = lab(
        1,
        presentation="attributed",
        producer_owns_page="no",
        producer="Abraham Lincoln",
        record="The Emancipation Proclamation",
    )
    answer = Answer.model_validate(
        {
            "claim_about": "the_fact_itself",
            "named_source": "none",
            "needs_test_conditions": False,
            "sources": [copy],
            "original_record_not_supplied": "none",
            "verdict": "false",
            "quotes": [{"page": 1, "text": QUOTE[1]}],
            "reason": "r",
        }
    )
    valid = [{"page": 1, "text": QUOTE[1]}]
    archive = ["https://avalon.law.yale.edu/19th_century/emancipa.asp"]
    blog = ["https://www.historyfacts.com/emancipation"]
    assert basis_check(answer, valid, PAGES, archive, references="official")["qualifies"]
    assert not basis_check(answer, valid, PAGES, blog, references="official")["qualifies"]
    assert not basis_check(answer, valid, PAGES, archive, references="none")["qualifies"]
    # The address decides, not the name: a look-alike domain is not official.
    assert not reference_site("https://gov.example.com/page", "official")
    assert reference_site("https://www.census.gov/x", "official")
    assert reference_site("https://www.who.int/x", "official")
    assert not reference_site("https://www.reuters.com/x", "official")
    assert reference_site("https://www.reuters.com/x", "official_and_list")
