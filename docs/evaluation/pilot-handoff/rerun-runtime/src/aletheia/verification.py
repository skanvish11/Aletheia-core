"""Assess bounded source passages; validate every supplied reference before admission."""

from typing import Annotated

from pydantic import Field, create_model

from aletheia.evidence import admit, navigation_only
from aletheia.task_contracts import Assessment, AssessmentBatch, Citation


def assessment_schema(source, supplied):
    """Constrain generation to actual IDs; admission still verifies every reference."""
    span_id = Annotated[int, Field(strict=True, ge=1, json_schema_extra={"enum": sorted(supplied)})]
    citation = create_model(
        "Citation",
        __base__=Citation,
        snapshot_id=(str, Field(json_schema_extra={"const": source.id})),
        span_ids=(list[span_id], Field(min_length=1, max_length=6)),
    )
    assessment = create_model(
        "Assessment",
        __base__=Assessment,
        citation=(citation, ...),
        provenance_span_ids=(list[span_id], Field(max_length=6)),
    )
    return create_model(
        "AssessmentBatch",
        __base__=AssessmentBatch,
        assessments=(list[assessment], Field(max_length=3)),
    )


async def assess(tasks, assertion, source):
    selected = []
    size = 0
    for span in source.spans:
        if navigation_only(span.text):
            continue
        if size + len(span.text) > 12000 or len(selected) >= 120:
            break
        selected.append(span)
        size += len(span.text)
    if not selected:
        return [], "Source has no assessable spans within the input limit."
    supplied = {s.id for s in selected}
    limited = len(selected) < sum(not navigation_only(s.text) for s in source.spans)
    limited = limited or "page_text_truncated" in source.limitations

    def validate(batch):
        for assessment in batch.assessments:
            # Ordering and duplicate IDs do not change the cited passages.
            # Canonicalize only these lossless properties; unknown IDs still fail.
            assessment.citation.span_ids = sorted(set(assessment.citation.span_ids))
            assessment.provenance_span_ids = sorted(set(assessment.provenance_span_ids))
            admit(assessment, source, supplied)

    result = await tasks.call(
        "assess",
        "Assess the exact assertion against the supplied numbered source spans. Cite only "
        "this snapshot and supplied span IDs, in increasing order without duplicates. "
        "Never write quotations. Distinguish support, contradiction, context and irrelevance. "
        "Evaluate EVERY detail of the assertion, including dates in descriptive clauses. "
        "For the SAME event or entity, a different date or quantity can CONTRADICT the claim "
        "with scope_match=true; a different event, population or jurisdiction is a scope "
        "mismatch. Supporting just the main clause does not support the full assertion. "
        "Use context for a true subclaim when other details remain unchecked. "
        "A publisher name or different domain alone is not proof of "
        "independence. Set independence=unknown unless cited provenance establishes an "
        "identifiable distinct underlying evidence origin; give origin, provenance_span_ids "
        "and provenance_note. Set authoritative_record only for a relevant original record. "
        "Use credible_synthesis only for an appropriate synthesis and explain relevance and "
        "coverage. Report documented limitations. Propose flags misleading_comparison "
        "or narrow_scope with dimension population/timeframe/units/baseline/condition/"
        "jurisdiction/definition. Name a concrete remaining gap, or null. "
        "When evidence establishes a relevant narrower or corrected fact, retain it as context "
        "and explain the scope/quantity difference in the rationale. Do not call it direct "
        "support for the original broader claim. A truncated source cannot establish "
        "comprehensive coverage. Return at most three concise assessments, grouping spans "
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
        assessment_schema(source, supplied),
        validate,
    )
    evidence = [admit(a, source, supplied) for a in result.assessments]
    return evidence, result.gap
