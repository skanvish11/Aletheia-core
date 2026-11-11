"""Compact generation contracts; persisted research records remain backward compatible."""

from typing import Annotated, Literal

from pydantic import Field

from aletheia import research_contracts as saved
from aletheia.phase_one_contracts import ClaimAnalysis, ComponentId, RecordedValue

Brief = Annotated[str, Field(strict=True, min_length=1, max_length=300)]
Label = Annotated[str, Field(strict=True, min_length=1, max_length=160)]


class ClaimPlan(saved.ClaimPlan):
    analysis: ClaimAnalysis
    clarification_reason: (
        Literal["missing_scope", "compound", "non_factual", "factual_uncertainty"] | None
    )


class Citation(saved.Citation):
    span_ids: Annotated[
        list[Annotated[int, Field(strict=True, ge=1)]], Field(min_length=1, max_length=6)
    ]


class ProposedFlag(saved.ProposedFlag):
    explanation: Brief


class Assessment(saved.Assessment):
    component_id: ComponentId
    values: Annotated[list[RecordedValue], Field(max_length=2)]
    citation: Citation
    synthesis_coverage: Brief | None
    publisher: Label | None
    origin: Label | None
    provenance_span_ids: Annotated[
        list[Annotated[int, Field(strict=True, ge=1)]], Field(max_length=6)
    ]
    provenance_note: Brief | None
    rationale: Brief
    limitations: Annotated[list[Brief], Field(max_length=3)]
    flags: Annotated[list[ProposedFlag], Field(max_length=3)]


class AssessmentBatch(saved.AssessmentBatch):
    assessments: Annotated[list[Assessment], Field(max_length=8)]


class ExplanationUnit(saved.ExplanationUnit):
    text: Brief
    evidence_ids: Annotated[list[saved.Identifier], Field(min_length=1, max_length=6)]


class AlmostCorrection(saved.AlmostCorrection):
    what_is_correct: ExplanationUnit
    what_needs_correction: ExplanationUnit
    corrected_claim: ExplanationUnit


class Synthesis(saved.Synthesis):
    almost_correction: AlmostCorrection | None
    units: Annotated[list[ExplanationUnit], Field(min_length=1, max_length=3)]
