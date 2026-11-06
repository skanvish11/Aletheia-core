"""User-facing truth labels require evidence; uncertainty and partial truth differ."""

import json
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from research_fixtures import Providers, terminal
from test_research_pipeline import running, submit

from aletheia.api import create_app
from aletheia.budgets import RunBudget
from aletheia.comparison import decision_key
from aletheia.contracts import InvestigationRequest
from aletheia.research_contracts import Decision, InvestigationResult
from aletheia.storage import Storage, StorageError


@pytest.mark.parametrize(
    "options",
    [
        {"relation": "contradicts"},
        {"relation": "context", "scope_match": False, "deep": True, "synthesis": True},
    ],
)
async def test_almost_requires_cited_correction_and_survives_saved_reads(settings, options):
    providers = Providers(almost=True, text="The Archive opened in 2001.", **options)
    async with running(settings, providers) as (_, client):
        saved = await submit(client)
        assert saved["status"] == "completed", saved
        result = saved["result"]
        assert result["outcome"] == "decided"
        assert result["verdict"] == "almost"
        assert result["unable_to_decide_reason"] is None
        assert result["finding"]["almost_correction"] == result["almost_correction"]
        correction = result["almost_correction"]
        assert correction["corrected_claim"]["text"] == "The Archive opened in 2001."
        assert correction["what_is_correct"]["text"].strip()
        assert correction["what_needs_correction"]["text"].strip()
        evidence = (await client.get(saved["links"]["evidence"])).json()["evidence"]
        ids = {e["id"] for e in evidence if e["admissible"]}
        assert all(set(unit["evidence_ids"]) <= ids for unit in correction.values())
        assert not any("does not meet" in note for note in result["limitations"])
        calls = list(providers.calls)
        assert (await client.get(saved["links"]["self"])).json() == saved
        assert (
            await client.post("/investigations", json={"claim": saved["claim"]})
        ).json() == saved
        assert providers.calls == calls
    reopened = create_app(settings)
    async with (
        reopened.router.lifespan_context(reopened),
        AsyncClient(transport=ASGITransport(app=reopened), base_url="http://test") as client,
    ):
        assert (await client.get(saved["links"]["self"])).json() == saved


@pytest.mark.parametrize(
    "check_field",
    [
        "core_supported",
        "correction_supported",
        "corrected_claim_supported",
        "preserves_core",
        "no_unresolved_conflict",
    ],
)
async def test_each_failed_correction_check_prevents_almost(settings, check_field):
    class RejectedCorrection(Providers):
        def model_value(self, schema, data):
            value = super().model_value(schema, data)
            if schema == "ExplanationCheck":
                value[check_field] = False
            return value

    providers = RejectedCorrection(relation="contradicts", almost=True)
    async with running(settings, providers) as (_, client):
        saved = await submit(client)
        assert saved["status"] == "failed"
        assert saved["result"] is None
        assert "validation" in saved["error"]["message"]


@pytest.mark.parametrize(
    "defect", ["missing_part", "blank", "invented_id", "no_citations", "unchanged"]
)
async def test_invalid_correction_has_one_repair_then_fails(settings, defect):
    class BadCorrection(Providers):
        def model_value(self, schema, data):
            value = super().model_value(schema, data)
            if schema == "Synthesis":
                correction = value["almost_correction"]
                if defect == "missing_part":
                    del correction["what_is_correct"]
                elif defect == "blank":
                    correction["what_needs_correction"]["text"] = "   "
                elif defect == "invented_id":
                    correction["corrected_claim"]["evidence_ids"] = ["invented"]
                elif defect == "no_citations":
                    correction["what_is_correct"]["evidence_ids"] = []
                else:
                    correction["corrected_claim"]["text"] = data["assertion"]["text"]
            return value

    providers = BadCorrection(relation="contradicts", almost=True)
    async with running(settings, providers) as (_, client):
        saved = await submit(client)
        assert saved["status"] == "failed" and saved["result"] is None
        assert [name for name, _ in providers.model_inputs].count("Synthesis") == 2
        assert [name for name, _ in providers.model_inputs].count("ExplanationCheck") == 0


@pytest.mark.parametrize(
    "options",
    [
        {"relation": "mixed", "source_count": 2},
        {"relation": "supports"},
        {"relation": "context", "deep": True},
        {"relation": "context", "deep": True, "independent": True, "source_count": 2},
    ],
)
async def test_almost_cannot_bypass_conflict_truth_or_per_part_evidence_bar(settings, options):
    providers = Providers(almost=True, **options)
    async with running(settings, providers) as (_, client):
        saved = await submit(client)
        assert saved["status"] == "failed" and saved["result"] is None
        # In the two-origin case the whole set is adequate, but each correction part
        # cites only one origin. Individual support requirements must still be enforced.
        assert [name for name, _ in providers.model_inputs].count("Synthesis") == 2


async def test_deadline_before_correction_check_never_publishes_candidate(settings):
    class CheckDeadline(RunBudget):
        def reserve(self, provider, operation, units):
            if self.finalizing and self.used["model"] == 4:
                self.deadline = self.started - 1
            super().reserve(provider, operation, units)

    providers = Providers(relation="contradicts", almost=True)
    async with running(settings, providers, budget_factory=CheckDeadline) as (_, client):
        saved = await submit(client)
        assert saved["status"] == "partial"
        assert saved["result"]["verdict"] == "false"
        assert saved["result"]["almost_correction"] is None
        assert saved["result"]["explanation"] == []
        assert not any(name == "ExplanationCheck" for name, _ in providers.model_inputs)


@pytest.mark.parametrize(
    "decision",
    [
        {
            "outcome": "decided",
            "verdict": "almost",
            "unable_to_decide_reason": None,
            "almost_correction": None,
        },
        {
            "outcome": "unable_to_decide",
            "verdict": "almost",
            "unable_to_decide_reason": "conflicting_evidence",
            "almost_correction": None,
        },
        {
            "outcome": "unable_to_decide",
            "verdict": None,
            "unable_to_decide_reason": None,
            "almost_correction": None,
        },
        {
            "outcome": "decided",
            "verdict": "true",
            "unable_to_decide_reason": "insufficient_evidence",
            "almost_correction": None,
        },
        {
            "outcome": "decided",
            "verdict": True,
            "unable_to_decide_reason": None,
            "almost_correction": None,
        },
    ],
)
def test_decision_contract_rejects_inconsistent_labels(decision):
    with pytest.raises(ValidationError):
        Decision.model_validate(decision)


async def test_same_almost_label_with_changed_correction_is_flagged(settings):
    class RevisedCorrection(Providers):
        year = "2001"

        def model_value(self, schema, data):
            value = super().model_value(schema, data)
            if schema == "Synthesis":
                unit = value["almost_correction"]["corrected_claim"]
                unit["text"] = f"The Archive opened in {self.year}."
            return value

    providers = RevisedCorrection(relation="contradicts", almost=True)
    async with running(settings, providers) as (_, client):
        first = await submit(client)
        providers.year = "2002"
        response = await client.post(
            first["links"]["refresh"], headers={"Idempotency-Key": "correction-change"}
        )
        second = await terminal(client, response.json()["id"])
        comparison = (await client.get(second["links"]["comparison"])).json()
        assert first["result"]["verdict"] == second["result"]["verdict"] == "almost"
        assert comparison["verdict_changed"] is False
        assert comparison["decision_changed"] is True
        assert comparison["same_relevant_evidence"] is True
        assert comparison["consistency_status"] == "inconsistent"
        assert (await client.get(first["links"]["self"])).json() == first
        result = InvestigationResult.model_validate(first["result"])
        cloned = result.model_copy(deep=True)
        cloned.almost_correction.corrected_claim.evidence_ids = ["new-run-evidence-id"]
        assert decision_key(result) == decision_key(cloned)


def legacy_payload(result, verdict):
    result = json.loads(json.dumps(result))
    for decision in (result, result["finding"]):
        for field in ("outcome", "unable_to_decide_reason", "almost_correction"):
            decision.pop(field)
        decision["verdict"] = verdict
    result["prompt_version"] = "one-claim-v1"
    result["application_version"] = "research-v1"
    return json.dumps(result, indent=2)


@pytest.mark.parametrize(
    ("legacy", "verdict", "reason"),
    [
        ("supported", "true", None),
        ("contradicted", "false", None),
        ("mixed", None, "conflicting_evidence"),
        ("insufficient_evidence", None, "insufficient_evidence"),
    ],
)
async def test_schema2_results_migrate_without_research_and_preserve_original(
    settings, legacy, verdict, reason
):
    providers = Providers()
    async with running(settings, providers) as (app, client):
        saved = await submit(client)
        original = legacy_payload(saved["result"], legacy)
        storage = app.state.storage
        events = await storage.events(UUID(saved["id"]))
        async with storage.connection() as db:
            await db.execute(
                "UPDATE investigations SET result_json=? WHERE id=?", (original, saved["id"])
            )
            await db.execute("PRAGMA user_version=2")
    before_calls = list(providers.calls)
    store = Storage(settings.database_path)
    await store.initialize()
    migrated = await store.get(UUID(saved["id"]))
    assert migrated.result.verdict == verdict
    assert migrated.result.unable_to_decide_reason == reason
    assert migrated.result.outcome == ("decided" if verdict else "unable_to_decide")
    assert migrated.result.almost_correction is None
    assert migrated.result.prompt_version == "one-claim-v1"
    assert migrated.created_at.isoformat() == saved["created_at"].replace("Z", "+00:00")
    assert await store.events(migrated.id) == events
    assert providers.calls == before_calls
    await store.initialize()
    async with store.connection() as db:
        rows = await (
            await db.execute("SELECT payload_json FROM research_records WHERE kind='legacy_result'")
        ).fetchall()
        assert len(rows) == 1 and rows[0][0] == original
        assert (await (await db.execute("PRAGMA user_version")).fetchone())[0] == 3


async def test_result_migration_failure_rolls_back_prior_archive_and_relabel(settings):
    async with running(settings, Providers()) as (_, client):
        saved = await submit(client)
    store = Storage(settings.database_path)
    second = await store.submit(InvestigationRequest(claim="Malformed historical fixture"))
    original = legacy_payload(saved["result"], "mixed")
    async with store.connection() as db:
        await db.execute(
            "UPDATE investigations SET result_json=? WHERE id=?", (original, saved["id"])
        )
        await db.execute("UPDATE investigations SET result_json='{}' WHERE id=?", (str(second.id),))
        await db.execute("PRAGMA user_version=2")
    with pytest.raises(StorageError, match="migration failed"):
        await store.initialize()
    async with store.connection() as db:
        assert (await (await db.execute("PRAGMA user_version")).fetchone())[0] == 2
        assert (
            await (
                await db.execute("SELECT COUNT(*) FROM research_records WHERE kind='legacy_result'")
            ).fetchone()
        )[0] == 0
        assert (
            await (
                await db.execute(
                    "SELECT result_json FROM investigations WHERE id=?", (saved["id"],)
                )
            ).fetchone()
        )[0] == original
        await db.execute("UPDATE investigations SET result_json=NULL WHERE id=?", (str(second.id),))
    await store.initialize()
    assert (
        await store.get(UUID(saved["id"]))
    ).result.unable_to_decide_reason == "conflicting_evidence"


async def test_public_schema_and_result_reject_mismatched_decisions(settings):
    async with running(settings, Providers(almost=True, relation="contradicts")) as (_, client):
        saved = await submit(client)
        schema = (await client.get("/openapi.json")).json()["components"]["schemas"]
        choices = schema["InvestigationResult"]["properties"]["verdict"]["anyOf"]
        assert choices == [
            {"enum": ["true", "false", "almost"], "type": "string"},
            {"type": "null"},
        ]
        data = saved["result"]
        data["finding"]["almost_correction"]["corrected_claim"]["text"] = "Different correction."
        with pytest.raises(ValidationError, match="must agree"):
            InvestigationResult.model_validate(data)


async def test_saving_almost_rolls_back_correction_with_terminal_event(settings):
    async with running(settings, Providers(almost=True, relation="contradicts")) as (_, client):
        saved = await submit(client)
    store = Storage(settings.database_path)
    request = await store.submit(InvestigationRequest(claim="Atomic Almost result"))
    claimed = await store.claim_next()
    assert claimed.id == request.id
    result = InvestigationResult.model_validate(saved["result"])
    async with store.connection() as db:
        await db.execute("""CREATE TRIGGER reject_almost_completion BEFORE INSERT ON events
            WHEN NEW.type='investigation_completed'
            BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END""")
    with pytest.raises(StorageError):
        await store.finish(request.id, status="completed", result=result)
    assert (await store.get(request.id)).result is None
    assert (await store.get(request.id)).status == "running"
    async with store.connection() as db:
        await db.execute("DROP TRIGGER reject_almost_completion")
    await store.finish(request.id, status="completed", result=result)
    assert (await store.get(request.id)).result.almost_correction == result.almost_correction


async def test_migrated_comparison_distinguishes_label_changes_from_undecided_reasons(settings):
    from aletheia.research_contracts import Comparison

    async with running(settings, Providers()) as (_, client):
        saved = await submit(client)
    store = Storage(settings.database_path)
    second = await store.submit(InvestigationRequest(claim="Second historical result"))
    first_payload = legacy_payload(saved["result"], "mixed")
    second_payload = legacy_payload(saved["result"], "insufficient_evidence")
    previous = Comparison(
        comparison_status="complete",
        baseline_id=saved["id"],
        verdict_changed=True,
        same_relevant_evidence=True,
        consistency_status="inconsistent",
    ).model_dump(exclude={"decision_changed"})
    raw_comparison = json.dumps(previous)
    async with store.connection() as db:
        await db.execute(
            "UPDATE investigations SET result_json=? WHERE id=?", (first_payload, saved["id"])
        )
        await db.execute(
            "UPDATE investigations SET result_json=?, status='completed', parent_id=? WHERE id=?",
            (second_payload, saved["id"], str(second.id)),
        )
        await db.execute(
            "INSERT INTO research_records VALUES (?,?,?,?)",
            (str(second.id), "comparison", "comparison", raw_comparison),
        )
        await db.execute("PRAGMA user_version=2")
    await store.initialize()
    comparison = (await store.records(second.id, "comparison", Comparison))[0]
    assert comparison.verdict_changed is False
    assert comparison.decision_changed is True
    assert comparison.consistency_status == "inconsistent"
    async with store.connection() as db:
        assert (
            await (
                await db.execute(
                    "SELECT payload_json FROM research_records WHERE kind='legacy_comparison'"
                )
            ).fetchone()
        )[0] == raw_comparison
