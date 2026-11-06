"""Assess bounded source passages; validate every supplied reference before admission."""

from typing import get_args

from aletheia.evidence import admit
from aletheia.research_contracts import AssessmentBatch, Dimension


async def assess(tasks, assertion, source):
    selected = []
    size = 0
    for span in source.spans:
        if size + len(span.text) > 12000 or len(selected) >= 120:
            break
        selected.append(span)
        size += len(span.text)
    if not selected:
        return [], "Source has no assessable spans within the input limit."
    supplied = {s.id for s in selected}
    limited = len(selected) < len(source.spans) or "page_text_truncated" in source.limitations

    def validate(batch):
        for assessment in batch.assessments:
            admit(assessment, source, supplied)

    result = await tasks.call(
        "assess",
        "Assess the exact assertion against the supplied numbered source spans. Cite only "
        "this snapshot and supplied span IDs, in increasing order without duplicates. "
        "Never write quotations. Distinguish support, contradiction, context and irrelevance. "
        "A material mismatch in quantity, dates, population, jurisdiction or definition means "
        "scope_match=false. A publisher name or different domain alone is not proof of "
        "independence. Set independence=unknown unless cited provenance establishes an "
        "identifiable distinct underlying evidence origin; give origin, provenance_span_ids "
        "and provenance_note. Set authoritative_record only for a relevant original record. "
        "Use credible_synthesis only for an appropriate synthesis and explain relevance and "
        "coverage. Report documented limitations. Propose flags misleading_comparison "
        f"or narrow_scope with dimension {'/'.join(get_args(Dimension))}. "
        "evaluation_setup means results obtained under different evaluation methods "
        "(prompting, sampling, tool access or scoring harness); benchmark_subset means a "
        "result on part or a modified version of a benchmark presented as the full one. "
        "Name a concrete remaining gap, or null. "
        "When evidence establishes a relevant narrower or corrected fact, retain it as context "
        "and explain the scope/quantity difference in the rationale. Do not call it direct "
        "support for the original broader claim. A truncated source cannot establish "
        "comprehensive coverage.",
        {
            "assertion": assertion.model_dump(),
            "snapshot_id": source.id,
            "url": source.url,
            "title": source.title,
            "published_date": source.published_date,
            "source_truncated": limited,
            "spans": [s.model_dump() for s in selected],
        },
        AssessmentBatch,
        validate,
    )
    evidence = [admit(a, source, supplied) for a in result.assessments]
    return evidence, result.gap
