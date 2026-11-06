"""Deterministic evidence gaps and bounded context for the next research round."""

from dataclasses import dataclass

from aletheia.verdicts import finding


@dataclass(frozen=True)
class ResearchGate:
    sufficient: bool
    reason: str
    gap: str | None


def evaluate(assertion, route, evidence, sources, retrieval_gap=None):
    computed, _ = finding(assertion, route, evidence, sources)
    if computed.verdict in {"true", "false"}:
        return ResearchGate(True, "evidence_sufficient", None)
    # A retrieval problem must not hide a known material contradiction.
    if computed.unable_to_decide_reason == "conflicting_evidence":
        return ResearchGate(
            False,
            "conflicting_evidence",
            "Investigate the conflicting passages and their original records, dates and scope. "
            "Seek evidence that explains the disagreement; do not count votes or ignore a side.",
        )
    relevant = [e for e in evidence if e.assertion_id == assertion.id]
    if any(e.admissible and e.assessment.relation in {"supports", "contradicts"} for e in relevant):
        return ResearchGate(
            False,
            "evidence_quality",
            "Find an authoritative original record or documented independent origins or an "
            "appropriate synthesis for the exact claim. Repeated reports of one origin "
            "do not establish independent evidence.",
        )
    if any(not e.assessment.scope_match for e in relevant):
        return ResearchGate(
            False,
            "scope_mismatch",
            "Find evidence matching the claim's exact dates, population, quantity and definition; "
            "the collected passages address a different or narrower scope.",
        )
    return ResearchGate(
        False,
        "missing_evidence",
        retrieval_gap or "Find direct records or independent evidence for the exact scope.",
    )


def planning_context(evidence, sources):
    """Balance both sides, including rejected scope matches, without copying whole pages."""
    by_id = {s.id: s for s in sources}
    groups = [
        sorted(
            (e for e in evidence if e.assessment.relation == relation),
            key=lambda e: not e.admissible,
        )
        for relation in ("supports", "contradicts", "context", "irrelevant")
    ]
    # At most twelve summaries. Balance relations and put admitted evidence before
    # rejected metadata so a flood of rejections cannot hide a real contradiction.
    selected = [
        group[index]
        for index in range(max((len(group) for group in groups), default=0))
        for group in groups
        if index < len(group)
    ][:12]
    summaries = []
    for item in selected:
        assessment = item.assessment
        source = by_id[assessment.citation.snapshot_id]
        summaries.append(
            {
                "evidence_id": item.id,
                "url": source.url,
                "relation": assessment.relation,
                "admissible": item.admissible,
                "scope_match": assessment.scope_match,
                "origin": assessment.origin if item.admissible else None,
                "independence": assessment.independence,
                "duplicate_group": source.duplicate_group,
                "rationale": assessment.rationale[:600] if item.admissible else None,
                "excerpts": [excerpt.text[:600] for excerpt in item.excerpts[:2]]
                if item.admissible
                else [],
            }
        )
    return {"summaries": summaries, "omitted_assessments": len(evidence) - len(selected)}
