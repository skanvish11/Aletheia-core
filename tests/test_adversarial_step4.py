"""Adversarial Step 4 cases: overlap, rejected evidence floods and asymmetric refresh."""

import json
from uuid import UUID

import httpx
from research_fixtures import Providers, terminal
from test_deeper_research import RoundProviders, independent
from test_research_integrity import judgment, source
from test_research_pipeline import running, submit

from aletheia.budgets import RunBudget
from aletheia.evidence import admit
from aletheia.research_gate import planning_context


async def test_overlapping_top_hits_do_not_crowd_out_counterevidence(settings):
    class OverlappingResults(Providers):
        def model_value(self, schema, data):
            value = super().model_value(schema, data)
            if schema == "SearchPlan" and not data["previous_queries"]:
                value["queries"].insert(
                    1,
                    {"assertion_id": "a1", "text": "archive history", "purpose": "support"},
                )
            return value

        async def handle(self, request):
            response = await super().handle(request)
            if request.url.path == "/search":
                query = json.loads(request.content)["query"]
                hits = response.json()["results"]
                # The top counter-search hit repeats A. Its next result C must get
                # a chance before the second support query's distinct result B.
                selected = (
                    [hits[0], hits[1]]
                    if "correction" in query
                    else [hits[2]]
                    if query == "archive history"
                    else [hits[0]]
                )
                return httpx.Response(200, json={"results": selected})
            return response

    providers = OverlappingResults(source_count=3, relation="mixed")
    async with running(settings, providers) as (_, client):
        saved = await submit(client)
        checked = [v["url"] for name, v in providers.model_inputs if name == "AssessmentBatch"]
        assert checked == ["https://source.test/0", "https://source.test/1"]
        assert saved["result"]["unable_to_decide_reason"] == "conflicting_evidence"
        assert saved["result"]["verdict"] is None


def test_rejected_assessments_cannot_hide_admitted_conflict_from_planner():
    s = source("Synthetic relevant evidence.")
    rejected = [
        admit(judgment(s, relation="contradicts", scope_match=False), s, {1}) for _ in range(12)
    ]
    support = [admit(judgment(s), s, {1}) for _ in range(12)]
    contradiction = admit(judgment(s, relation="contradicts"), s, {1})
    context = planning_context([*support, *rejected, contradiction], [s])
    assert len(context["summaries"]) == 12
    assert context["omitted_assessments"] == 13
    assert contradiction.id in {item["evidence_id"] for item in context["summaries"]}


async def test_refresh_rechecks_both_sides_of_a_previously_conflicting_finding(settings):
    class MissingNewResults(Providers):
        shifted = False

        def model_value(self, schema, data):
            value = super().model_value(schema, data)
            if schema == "AssessmentBatch":
                value["assessments"][0]["relation"] = (
                    "contradicts" if data["url"].endswith("/2") else "supports"
                )
            return value

        async def handle(self, request):
            response = await super().handle(request)
            if request.url.path == "/search" and self.shifted:
                return httpx.Response(200, json={"results": []})
            return response

    providers = MissingNewResults(source_count=3, deep=True, independent=True)
    async with running(settings, providers) as (_, client):
        first = await submit(client)
        assert first["result"]["unable_to_decide_reason"] == "conflicting_evidence"
        providers.shifted = True
        refreshed = await client.post(
            first["links"]["refresh"], headers={"Idempotency-Key": "both"}
        )
        second = await terminal(client, refreshed.json()["id"])
        sources = (await client.get(second["links"]["evidence"])).json()["sources"]
        assert {s["url"] for s in sources} == {"https://source.test/0", "https://source.test/2"}
        assert second["result"]["verdict"] is None
        assert second["result"]["unable_to_decide_reason"] == "conflicting_evidence"


async def test_planner_consuming_last_research_call_stops_without_false_followup(settings):
    class FiveResearchCalls(RunBudget):
        def escalate(self):
            super().escalate()
            self.model_attempts = 9  # Five research attempts and four reserved finalization calls.

    providers = RoundProviders([[{}, {}], [independent("new")]], deep=True, authoritative=False)
    async with running(settings, providers, budget_factory=FiveResearchCalls) as (app, client):
        saved = await submit(client)
        assert saved["status"] == "partial"
        assert saved["stop_reason"] == "budget_exhausted"
        events = await app.state.storage.events(UUID(saved["id"]))
        assert not any(e.type == "followup_planned" for e in events)
        assert not any(
            e.type == "research_gate" and e.payload["action"] == "followup" for e in events
        )
        assert providers.calls.count("/search") == 2
        assert saved["result"]["explanation"]
        assert saved["result"]["budget_used"]["model"] <= 9


async def test_refresh_keeps_new_metadata_for_a_rechecked_baseline_url(settings):
    class MetadataChange(Providers):
        changed = False

        async def handle(self, request):
            response = await super().handle(request)
            if request.url.path == "/search" and self.changed:
                data = response.json()
                for hit in data["results"]:
                    hit["title"] = "Updated archive record"
                    hit["published_date"] = "2001-01-01"
                return httpx.Response(200, json=data)
            return response

    providers = MetadataChange()
    async with running(settings, providers) as (_, client):
        first = await submit(client)
        providers.changed = True
        refreshed = await client.post(
            first["links"]["refresh"], headers={"Idempotency-Key": "meta"}
        )
        second = await terminal(client, refreshed.json()["id"])
        sources = (await client.get(second["links"]["evidence"])).json()["sources"]
        assert sources[0]["title"] == "Updated archive record"
        assert sources[0]["published_date"] == "2001-01-01"
        comparison = (await client.get(second["links"]["comparison"])).json()
        assert comparison["sources"][0]["metadata_changed"] is True
