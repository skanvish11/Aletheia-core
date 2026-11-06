"""Step 4 acceptance through HTTP, real adapters and a persistent temporary database."""

import json
from itertools import permutations
from uuid import UUID

import httpx
import pytest
from research_fixtures import Providers, terminal
from test_research_integrity import judgment, source
from test_research_pipeline import running, submit

from aletheia.budgets import RunBudget
from aletheia.evidence import admit
from aletheia.planning import validate_plan
from aletheia.research_contracts import SearchPlan
from aletheia.research_gate import planning_context
from aletheia.verdicts import sufficient


class RoundProviders(Providers):
    """Each search round exposes new sources with explicit, synthetic provenance."""

    def __init__(self, rounds, **options):
        super().__init__(followups=True, **options)
        self.rounds = rounds
        self.round = -1
        self.pages = {}
        for index, pages in enumerate(rounds):
            for position, page in enumerate(pages):
                self.pages[f"https://source.test/round-{index}/{position}"] = page

    def model_value(self, schema, data):
        if schema == "SearchPlan":
            self.round += 1
            if self.round >= len(self.rounds):
                return {"queries": [], "gap": data["gap"]}
        value = super().model_value(schema, data)
        if schema == "AssessmentBatch":
            page = self.pages[data["url"]]
            item = value["assessments"][0]
            item.update({key: val for key, val in page.items() if key not in {"gap", "error"}})
            if item["independence"] != "unknown":
                item.update(provenance_span_ids=[1], provenance_note="Documented source origin.")
            value["gap"] = page.get("gap")
        return value

    async def handle(self, request):
        data = json.loads(request.content)
        if request.url.path == "/search":
            self.calls.append("/search")
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "url": url,
                            "title": "Synthetic research record",
                            "content": "Search text is never evidence",
                            "score": 0.9,
                        }
                        for url in self.pages
                        if f"/round-{self.round}/" in url
                    ]
                },
            )
        if request.url.path == "/extract":
            self.calls.append("/extract")
            url = data["urls"][0]
            if self.pages[url].get("error"):
                return httpx.Response(200, json={"results": [], "failed_results": [{"url": url}]})
            return httpx.Response(
                200,
                json={
                    "results": [{"url": url, "raw_content": "Synthetic Archive record.\n" + url}],
                    "failed_results": [],
                },
            )
        return await super().handle(request)


def independent(origin):
    return {"origin": origin, "independence": "established"}


async def test_followup_uses_scope_gap_and_new_evidence_to_finish(settings):
    providers = RoundProviders(
        [
            [{"scope_match": False}] * 5,
            [independent("Archive register"), independent("Independent census")],
        ]
    )
    async with running(settings, providers) as (app, client):
        saved = await submit(client)
        assert saved["status"] == "completed", saved
        assert saved["route"] == "deep"
        assert saved["result"]["verdict"] == "true"
        assert saved["stop_reason"] == "evidence_sufficient"
        assert saved["result"]["budget_used"] == {"model": 9, "search": 4, "extract": 4}
        plans = [value for name, value in providers.model_inputs if name == "SearchPlan"]
        assert len(plans) == 2
        assert "exact dates" in plans[1]["gap"]
        assert all(not e["scope_match"] for e in plans[1]["evidence_context"]["summaries"])
        assert len(plans[1]["previous_queries"]) == 2
        assert plans[1]["remaining_search_attempts"] == 6
        assert plans[1]["remaining_extraction_attempts"] == 8
        events = await app.state.storage.events(UUID(saved["id"]))
        assert sum(e.type == "route_escalated" for e in events) == 1
        assert sum(e.type == "followup_planned" for e in events) == 1
        calls = len(providers.calls)
        assert (await client.get(saved["links"]["self"])).json() == saved
        assert len(providers.calls) == calls


@pytest.mark.parametrize("extra_support", [False, True])
async def test_counterevidence_gets_page_capacity_beside_a_long_support_list(
    settings, extra_support
):
    class SeparateSearches(Providers):
        def model_value(self, schema, data):
            value = super().model_value(schema, data)
            if schema == "SearchPlan" and not data["previous_queries"] and extra_support:
                value["queries"].insert(
                    1,
                    {"assertion_id": "a1", "text": "archive history", "purpose": "support"},
                )
            return value

        async def handle(self, request):
            response = await super().handle(request)
            if request.url.path == "/search":
                contradiction = "correction" in json.loads(request.content)["query"]
                response = httpx.Response(
                    200,
                    json={
                        "results": [
                            hit
                            for hit in response.json()["results"]
                            if hit["url"].endswith("/1") == contradiction
                        ]
                    },
                )
            return response

    providers = SeparateSearches(source_count=5, relation="mixed")
    async with running(settings, providers) as (_, client):
        saved = await submit(client)
        assert saved["status"] == "completed"
        assert saved["result"]["unable_to_decide_reason"] == "conflicting_evidence"
        assessed = [v["url"] for name, v in providers.model_inputs if name == "AssessmentBatch"]
        assert assessed == ["https://source.test/0", "https://source.test/1"]


async def test_refresh_prioritizes_fresh_search_results_over_old_pages(settings):
    class NewEvidence(Providers):
        async def handle(self, request):
            response = await super().handle(request)
            if request.url.path == "/search" and self.options["relation"] == "contradicts":
                data = response.json()
                for hit in data["results"]:
                    hit["url"] = hit["url"].replace("source.test/", "source.test/new/")
                return httpx.Response(200, json=data)
            return response

    providers = NewEvidence(source_count=2)
    async with running(settings, providers) as (_, client):
        first = await submit(client)
        assert first["result"]["verdict"] == "true"
        providers.options["relation"] = "contradicts"
        refreshed = await client.post(first["links"]["refresh"], headers={"Idempotency-Key": "new"})
        second = await terminal(client, refreshed.json()["id"])
        assert second["result"]["verdict"] == "false"
        evidence = (await client.get(second["links"]["evidence"])).json()
        assert {s["url"] for s in evidence["sources"]} == {
            "https://source.test/new/0",
            "https://source.test/new/1",
        }
        comparison = (await client.get(second["links"]["comparison"])).json()
        assert {s["change"] for s in comparison["sources"]} == {"new", "not_selected"}


async def test_conflict_takes_priority_over_retrieval_gap_and_can_stop_honestly(settings):
    providers = RoundProviders([[{}, {"relation": "contradicts"}, {"error": True}]], deep=True)
    async with running(settings, providers) as (app, client):
        saved = await submit(client)
        assert saved["status"] == "completed", saved
        assert saved["stop_reason"] == "no_useful_query"
        assert saved["result"]["verdict"] is None
        assert saved["result"]["unable_to_decide_reason"] == "conflicting_evidence"
        plans = [value for name, value in providers.model_inputs if name == "SearchPlan"]
        assert len(plans) == 2
        assert "conflicting passages" in plans[1]["gap"]
        summaries = plans[1]["evidence_context"]["summaries"]
        assert {e["relation"] for e in summaries} == {"supports", "contradicts"}
        assert all(e["excerpts"] == ["Synthetic Archive record."] for e in summaries)
        assert "verdict" not in json.dumps(plans)
        events = await app.state.storage.events(UUID(saved["id"]))
        assert not any(e.type == "route_escalated" for e in events)
        assert any(e.type == "source_rejected" for e in events)


async def test_counterevidence_in_followup_prevents_true_even_with_more_support(settings):
    providers = RoundProviders(
        [
            [independent("one")],
            [independent("two"), {"relation": "contradicts"}],
            [independent("three")],
        ],
        deep=True,
    )
    async with running(settings, providers) as (app, client):
        saved = await submit(client)
        assert saved["status"] == "partial", saved
        assert saved["result"]["verdict"] is None
        assert saved["result"]["unable_to_decide_reason"] == "conflicting_evidence"
        assert saved["stop_reason"] == "budget_exhausted"
        assert "The follow-up round limit was reached." in saved["result"]["limitations"]
        assert providers.calls.count("/search") == 6
        events = await app.state.storage.events(UUID(saved["id"]))
        assert sum(e.type == "followup_planned" for e in events) == 2
        assert any(
            e.type == "budget_reached" and e.payload["reason"] == "followup_round_limit"
            for e in events
        )


async def test_large_source_lists_leave_capacity_for_two_followups_and_finalization(settings):
    shared = {"independence": "shared", "origin": "One underlying report"}
    providers = RoundProviders([[shared] * 5, [shared] * 5, [shared] * 5], deep=True)
    async with running(settings, providers) as (app, client):
        saved = await submit(client)
        assert saved["status"] == "partial", saved
        assert saved["result"]["unable_to_decide_reason"] == "insufficient_evidence"
        assert saved["result"]["budget_used"] == {"model": 14, "search": 6, "extract": 8}
        assert saved["result"]["explanation"]
        assert len([value for name, value in providers.model_inputs if name == "SearchPlan"]) == 3
        events = await app.state.storage.events(UUID(saved["id"]))
        assert [e.payload["count"] for e in events if e.type == "sources_deferred"] == [
            "1",
            "3",
            "3",
        ]
        assert not any(e.type == "source_rejected" for e in events)


async def test_no_followup_planning_when_no_pages_can_be_extracted(settings):
    class TwoPages(RunBudget):
        def escalate(self):
            super().escalate()
            self.extraction_attempts = 2

    providers = RoundProviders([[{}, {}], [independent("new")]], deep=True)
    async with running(settings, providers, budget_factory=TwoPages) as (_, client):
        saved = await submit(client)
        assert saved["status"] == "partial"
        assert saved["stop_reason"] == "budget_exhausted"
        assert providers.calls.count("/search") == 2
        assert len([v for name, v in providers.model_inputs if name == "SearchPlan"]) == 1
        assert saved["result"]["explanation"]


async def test_repeated_followup_queries_are_repaired_once_then_fail_without_search(settings):
    class Repeating(Providers):
        def model_value(self, schema, data):
            value = super().model_value(schema, data)
            if schema == "SearchPlan" and data["previous_queries"]:
                value["queries"][0]["text"] = " ARCHIVE   RECORD 0 "
            return value

    providers = Repeating(deep=True, followups=True)
    async with running(settings, providers) as (_, client):
        saved = await submit(client)
        assert saved["status"] == "failed"
        assert saved["result"] is None
        assert providers.calls.count("/search") == 2
        assert len([v for name, v in providers.model_inputs if name == "SearchPlan"]) == 3


def test_blank_followup_gap_is_rejected():
    plan = SearchPlan(
        queries=[{"assertion_id": "a1", "text": "New original record", "purpose": "context"}],
        gap="   ",
    )
    with pytest.raises(ValueError):
        validate_plan(plan, set(), False)


def test_distinct_origin_and_content_pair_is_independent_of_order():
    sources = [source("Shared body."), source("Another body."), source("Shared body.")]
    evidence = [
        admit(
            judgment(
                s,
                independence="established",
                origin=origin,
                provenance_span_ids=[1],
                provenance_note="Original evidence.",
            ),
            s,
            {1},
        )
        for s, origin in zip(sources, ["Origin A", "Origin A", "Origin B"], strict=True)
    ]
    for ordering in permutations(evidence):
        assert sufficient(ordering, "deep", sources)
    assert not sufficient([evidence[0], evidence[1]], "deep", sources)
    assert not sufficient([evidence[0], evidence[2]], "deep", sources)


def test_bounded_planning_context_keeps_counterevidence_among_many_supporting_passages():
    s = source("A" * 2000 + ".")
    support = [admit(judgment(s), s, {1}) for _ in range(20)]
    contra = admit(judgment(s, relation="contradicts"), s, {1})
    context = planning_context([*support, contra], [s])
    assert len(context["summaries"]) == 12
    assert context["omitted_assessments"] == 9
    assert context["summaries"][1]["relation"] == "contradicts"
    assert all(len(item["excerpts"][0]) == 600 for item in context["summaries"])
