"""Lossless archive and deterministic presentation migration for pre-label results."""

import json

from aletheia.research_contracts import InvestigationResult

LEGACY_DECISIONS = {
    "supported": ("true", "decided", None),
    "contradicted": ("false", "decided", None),
    "mixed": (None, "unable_to_decide", "conflicting_evidence"),
    "insufficient_evidence": (None, "unable_to_decide", "insufficient_evidence"),
}


async def migrate_results(db):
    rows = await (
        await db.execute("SELECT id, result_json FROM investigations WHERE result_json IS NOT NULL")
    ).fetchall()
    for row in rows:
        result = json.loads(row["result_json"])
        previous = result["verdict"]
        if previous not in LEGACY_DECISIONS or result["finding"]["verdict"] != previous:
            raise ValueError("Unexpected historical decision contract.")
        verdict, outcome, reason = LEGACY_DECISIONS[previous]
        for decision in (result, result["finding"]):
            decision.update(
                verdict=verdict,
                outcome=outcome,
                unable_to_decide_reason=reason,
                almost_correction=None,
            )
        validated = InvestigationResult.model_validate(result)
        # Preserve the original bytes, citations, wording, timestamps and version metadata.
        # No old result is retroactively inferred to be Almost.
        await db.execute(
            "INSERT INTO research_records VALUES (?,?,?,?)",
            (row["id"], "legacy_result", "schema-2", row["result_json"]),
        )
        await db.execute(
            "UPDATE investigations SET result_json=? WHERE id=?",
            (validated.model_dump_json(), row["id"]),
        )
    comparisons = await (
        await db.execute(
            "SELECT investigation_id, record_id, payload_json FROM research_records "
            "WHERE kind='comparison'"
        )
    ).fetchall()
    for row in comparisons:
        value = json.loads(row["payload_json"])
        value["decision_changed"] = value["verdict_changed"]
        # Old mixed -> insufficient changed the old verdict, but now changes only
        # the undecided reason. Keep that distinction in historical comparisons.
        current = await (
            await db.execute(
                "SELECT result_json FROM investigations WHERE id=?", (row["investigation_id"],)
            )
        ).fetchone()
        baseline = await (
            await db.execute(
                "SELECT result_json FROM investigations WHERE id=?", (value.get("baseline_id"),)
            )
        ).fetchone()
        if current and baseline and current[0] and baseline[0]:
            value["verdict_changed"] = (
                json.loads(current[0])["verdict"] != json.loads(baseline[0])["verdict"]
            )
        await db.execute(
            "INSERT INTO research_records VALUES (?,?,?,?)",
            (row["investigation_id"], "legacy_comparison", row["record_id"], row["payload_json"]),
        )
        await db.execute(
            "UPDATE research_records SET payload_json=? "
            "WHERE investigation_id=? AND kind='comparison' AND record_id=?",
            (json.dumps(value), row["investigation_id"], row["record_id"]),
        )
