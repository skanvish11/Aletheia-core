"""Compact generation contracts; persisted research records remain backward compatible."""

from typing import Annotated, Literal

from pydantic import Field

from aletheia import research_contracts as saved

Brief = Annotated[str, Field(strict=True, min_length=1, max_length=300)]
Label = Annotated[str, Field(strict=True, min_length=1, max_length=160)]


class ClaimPlan(saved.Record):
    # Decide whether scope is missing BEFORE generating either branch. Emitting
    # assertions first encouraged contradictory assertions + clarification questions.
    clarification_reason: (
        Literal["missing_scope", "compound", "non_factual", "factual_uncertainty"] | None
    ) = Field(
        description="Null for any checkable claim, including false or unresolved claims.",
        json_schema_extra={"enum": [None, "missing_scope", "compound", "non_factual"]},
    )
    questions: Annotated[list[saved.Short], Field(max_length=4)]
    assertions: Annotated[list[saved.Assertion], Field(max_length=1)]
    scope_note: saved.Text


class Citation(saved.Citation):
    span_ids: Annotated[
        list[Annotated[int, Field(strict=True, ge=1)]], Field(min_length=1, max_length=6)
    ]


class ProposedFlag(saved.ProposedFlag):
    explanation: Brief


class Assessment(saved.Assessment):
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
    assessments: Annotated[list[Assessment], Field(max_length=3)]


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
