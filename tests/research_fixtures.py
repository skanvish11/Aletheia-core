"""Synthetic provider responses over real HTTP adapters; no network or real claims."""

import asyncio
import json
from contextlib import asynccontextmanager

import httpx
from pydantic import SecretStr

from aletheia.providers.nebius import NebiusProvider
from aletheia.providers.settings import ProviderSettings
from aletheia.providers.tavily import TavilyProvider


class Providers:
    def __init__(
        self,
        *,
        relation="supports",
        almost=False,
        invalid_correction=False,
        deep=False,
        empty=False,
        ambiguous=False,
        invalid_citation=False,
        invalid_plan=False,
        invalid_explanation=False,
        authentication_failure=False,
        scope_match=True,
        synthesis=False,
        independent=False,
        source_count=1,
        followups=False,
        flags=None,
        extraction_failure=False,
        text="The Archive opened in 2000.",
    ):
        self.options = locals().copy()
        self.options.pop("self")
        self.calls = []
        self.model_inputs = []
        self.hold = None
        self.entered = asyncio.Event()

    def model_value(self, schema, data):
        o = self.options
        if schema == "ClaimPlan":
            return {
                "assertions": []
                if o["ambiguous"]
                else [
                    {
                        "id": "a1",
                        "text": "The Archive opened in 2000.",
                        "kind": "direct_record",
                        "consequential": o["deep"],
                        "recommended_route": "quick",
                    }
                ],
                "questions": ["Which archive do you mean?"] if o["ambiguous"] else [],
                "scope_note": "Opening year of the named Archive.",
            }
        if schema == "SearchPlan":
            previous = data["previous_queries"]
            if previous and not o["followups"]:
                return {"queries": [], "gap": data["gap"]}
            suffix = str(len(previous))
            return {
                "queries": [
                    {
                        "assertion_id": "a1",
                        "text": "archive record " + suffix,
                        "purpose": "support",
                    },
                    {
                        "assertion_id": "a1",
                        "text": "archive correction " + suffix,
                        "purpose": "support" if o["invalid_plan"] else "contradiction",
                    },
                ],
                "gap": data["gap"],
            }
        if schema == "AssessmentBatch":
            relation = o["relation"]
            if relation == "mixed":
                relation = "contradicts" if data["url"].endswith("/1") else "supports"
            return {
                "assessments": [
                    {
                        "citation": {
                            "snapshot_id": "invented"
                            if o["invalid_citation"]
                            else data["snapshot_id"],
                            "span_ids": [1],
                        },
                        "relation": relation,
                        "scope_match": o["scope_match"],
                        "authoritative_record": True,
                        "credible_synthesis": o["synthesis"],
                        "synthesis_coverage": "Reviews all Archive records."
                        if o["synthesis"]
                        else None,
                        "publisher": "Synthetic Archive",
                        "origin": data["url"] if o["independent"] else None,
                        "independence": "established" if o["independent"] else "unknown",
                        "provenance_span_ids": [1] if o["independent"] else [],
                        "provenance_note": "Independent original observation."
                        if o["independent"]
                        else None,
                        "rationale": "The supplied record states the opening year.",
                        "limitations": [],
                        "flags": o["flags"] or [],
                    }
                ],
                "gap": None,
            }
        if schema == "Synthesis":
            evidence_id = data["evidence"][0]["id"]
            correction = (
                {
                    "what_is_correct": {
                        "text": "The Archive did open around that time.",
                        "evidence_ids": [evidence_id],
                    },
                    "what_needs_correction": {
                        "text": "Its opening year was 2001, not 2000.",
                        "evidence_ids": [evidence_id],
                    },
                    "corrected_claim": {
                        "text": "The Archive opened in 2001.",
                        "evidence_ids": [evidence_id],
                    },
                }
                if o["almost"]
                else None
            )
            return {
                "almost_correction": correction,
                "units": [
                    {
                        "text": (
                            "The opening occurred in 2001; the claim needs its year corrected."
                            if o["almost"]
                            else "The record states that the Archive opened in 2000."
                        ),
                        "evidence_ids": [data["evidence"][0]["id"]],
                    }
                ],
            }
        if schema == "ExplanationCheck":
            return {
                "supported_units": [] if o["invalid_explanation"] else [0],
                "core_supported": o["almost"],
                "correction_supported": o["almost"],
                "corrected_claim_supported": o["almost"] and not o["invalid_correction"],
                "preserves_core": o["almost"],
                "no_unresolved_conflict": o["almost"],
            }
        raise AssertionError(schema)

    async def handle(self, request):
        data = json.loads(request.content)
        self.calls.append(request.url.path)
        self.entered.set()
        if self.hold is not None:
            await self.hold.wait()
        if self.options["authentication_failure"]:
            return httpx.Response(401, json={"secret": "synthetic-provider-secret"})
        if request.url.path.endswith("completions"):
            schema = data["response_format"]["json_schema"]["schema"]["title"]
            value = json.loads(data["messages"][1]["content"])
            self.model_inputs.append((schema, value))
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(self.model_value(schema, value)),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                },
            )
        if request.url.path == "/search":
            return httpx.Response(
                200,
                json={
                    "results": []
                    if self.options["empty"]
                    else [
                        {
                            "url": f"https://source.test/{i}",
                            "title": f"Record {i}",
                            "content": "A search snippet is not evidence",
                            "score": 0.9,
                            "published_date": None,
                        }
                        for i in range(self.options["source_count"])
                    ]
                },
            )
        if request.url.path == "/extract":
            url = data["urls"][0]
            failed = self.options["extraction_failure"]
            text = self.options["text"]
            if self.options["source_count"] > 1:
                text += "\n" + url
            return httpx.Response(
                200,
                json={
                    "results": [] if failed else [{"url": url, "raw_content": text}],
                    "failed_results": [{"url": url}] if failed else [],
                },
            )
        raise AssertionError(request.url.path)

    @asynccontextmanager
    async def factory(self):
        settings = ProviderSettings(
            nebius_api_key=SecretStr("synthetic-nebius"),
            tavily_api_key=SecretStr("synthetic-tavily"),
            nebius_model="synthetic-model",
            max_retries=0,
        )
        transport = httpx.MockTransport(self.handle)
        async with (
            NebiusProvider(settings, transport=transport) as model,
            TavilyProvider(settings, transport=transport) as search,
        ):
            yield model, search, "synthetic-model"


async def terminal(client, run_id):
    async with asyncio.timeout(10):
        while True:
            response = await client.get(f"/investigations/{run_id}")
            assert response.status_code == 200
            value = response.json()
            if value["status"] not in {"queued", "running"}:
                return value
            await asyncio.sleep(0.01)
