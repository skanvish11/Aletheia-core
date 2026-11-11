"""Assess bounded source passages; validate every supplied reference before admission."""

from aletheia.direct import validate_component_assessment
from aletheia.evidence import admit
from aletheia.passages import select_passages
from aletheia.task_contracts import AssessmentBatch


async def assess(tasks, assertion, source):
    selected = select_passages(assertion, source)
    if not selected:
        return [], "Source has no assessable spans within the input limit."
    supplied = {s.id for s in selected}
    limited = len(selected) < len(source.spans) or "page_text_truncated" in source.limitations

    def validate(batch):
        for assessment in batch.assessments:
            admit(assessment, source, supplied)
            if assertion.analysis:
                validate_component_assessment(assessment, assertion, source, supplied)

    result = await tasks.call(
        "assess",
        "Assess the exact assertion against the supplied numbered source spans. Cite only "
        "this snapshot and supplied span IDs, in increasing order without duplicates. "
        "Never write quotations. Distinguish support, contradiction, context and irrelevance. "
        "Assess each material component separately using its component_id. A different date "
        "or quantity for the SAME entity and event is contradiction with scope_match=true; "
        "a different entity, population or definition is scope_match=false. Never merge a "
        "campaign date with a discovery date or use partial support for the entire claim. "
        "For comparison components, extract both values with exact literal source_text, "
        "entity, metric, units, period, population and definition, and mark uncertainty. "
        "Do not invent operands, convert units silently, or infer a superlative from one pair. "
        "A publisher name or different domain alone is not proof of "
        "independence. Set independence=unknown unless cited provenance establishes an "
        "identifiable distinct underlying evidence origin; give origin, provenance_span_ids "
        "and provenance_note. Set authoritative_record only for a relevant original record. "
        "Use credible_synthesis only for an appropriate synthesis and explain relevance and "
        "coverage. Report documented limitations. Propose flags misleading_comparison "
        "or narrow_scope with dimension population/timeframe/units/baseline/condition/"
        "jurisdiction/definition. Name a concrete remaining gap, or null. "
        "When evidence establishes a relevant narrower fact about a "
        "different scope, retain it as context "
        "and explain the scope/quantity difference in the rationale. Do not call it direct "
        "support for the original broader claim. A truncated source cannot establish "
        "comprehensive coverage, but can establish a narrow explicit record. Return at most eight "
        "concise component assessments, grouping spans "
        "that establish the same point. Preserve material support AND contradiction when "
        "both occur; never produce one assessment per span. Use short factual rationales "
        "of at most 300 characters, at most six essential span IDs per citation, at most "
        "three limitations and three flags per assessment. Use null or empty lists for "
        "inapplicable fields; do not fill them with repetitive explanations.",
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
