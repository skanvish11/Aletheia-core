"""Conservative evidence comparison, independent of the new synthesis."""

import json

from aletheia.evidence import canonical_url, digest
from aletheia.research_contracts import Comparison, Evidence, Snapshot, SourceChange


def fingerprint(sources, evidence):
    by_id = {s.id: s for s in sources}
    items = set()
    for e in evidence:
        if not e.admissible or e.assessment.relation == "irrelevant":
            continue
        a = e.assessment
        source = by_id[a.citation.snapshot_id]
        for excerpt in e.excerpts:
            items.add(
                (
                    source.canonical_url,
                    source.content_hash,
                    excerpt.quote_hash,
                    source.published_date,
                    a.publisher,
                    a.origin,
                    source.normalization_version,
                    source.splitter_version,
                    tuple(sorted(set(source.limitations))),
                )
            )
    if not items:
        return None
    return digest(json.dumps(sorted(items, key=lambda v: json.dumps(v)), ensure_ascii=False))


def decision_key(result):
    correction = result.almost_correction
    return (
        result.verdict,
        result.outcome,
        result.unable_to_decide_reason,
        tuple(
            unit.text
            for unit in (
                correction.what_is_correct,
                correction.what_needs_correction,
                correction.corrected_claim,
            )
        )
        if correction
        else None,
    )


async def compare(storage, investigation, result, sources, evidence):
    if not investigation.parent_id:
        return None
    parent = await storage.get(investigation.parent_id)
    if not parent or not parent.result:
        return Comparison(comparison_status="unavailable", baseline_id=str(investigation.parent_id))
    old_sources = await storage.records(parent.id, "snapshot", Snapshot)
    old_evidence = await storage.records(parent.id, "evidence", Evidence)
    old = {s.canonical_url: s for s in old_sources}
    new = {s.canonical_url: s for s in sources}
    events = await storage.events(investigation.id)
    failed = {
        canonical_url(e.payload["url"])
        for e in events
        if e.type == "source_rejected"
        and e.payload.get("reason") in {"extraction_failed", "missing_result", "empty_content"}
    }
    changes = []
    for url in sorted(old.keys() | new.keys()):
        if url not in new:
            change = "retrieval_failed" if url in failed else "not_selected"
        elif url not in old:
            change = "new"
        else:
            change = "unchanged" if old[url].content_hash == new[url].content_hash else "changed"
        changes.append(
            SourceChange(
                url=url,
                change=change,
                metadata_changed=bool(
                    url in old
                    and url in new
                    and (
                        old[url].published_date != new[url].published_date
                        or old[url].title != new[url].title
                    )
                ),
            )
        )
    before, after = fingerprint(old_sources, old_evidence), fingerprint(sources, evidence)
    scope_changed = parent.result.assertion.text != result.assertion.text
    same = bool(before and before == after and not scope_changed)
    verdict_changed = parent.result.verdict != result.verdict
    decision_changed = decision_key(parent.result) != decision_key(result)
    config_fields = ("model", "prompt_version", "application_version", "configuration")
    return Comparison(
        comparison_status="complete",
        baseline_id=str(parent.id),
        scope_changed=scope_changed,
        sources=changes,
        verdict_changed=verdict_changed,
        decision_changed=decision_changed,
        same_relevant_evidence=same,
        consistency_status="inconsistent"
        if same and decision_changed
        else ("no_inconsistency_detected" if same else "not_comparable"),
        baseline_fingerprint=before,
        current_fingerprint=after,
        configuration_changed=any(
            getattr(parent.result, f) != getattr(result, f) for f in config_fields
        )
        or parent.route != investigation.route,
        limitations=[
            "Exact evidence comparison includes surrounding page text and provenance; "
            "harmless page edits may count as changes.",
            "Automatic consistency rechecks are disabled; "
            "any detected inconsistency remains visible.",
        ],
    )
