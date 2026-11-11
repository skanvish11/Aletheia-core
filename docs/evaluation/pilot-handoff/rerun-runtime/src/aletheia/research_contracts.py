"""Bounded model tasks and saved research records for one scoped assertion."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(strict=True, min_length=1, max_length=2000)]
Short = Annotated[str, Field(strict=True, min_length=1, max_length=400)]
Identifier = Annotated[str, Field(strict=True, min_length=1, max_length=80)]
Verdict = Literal["true", "false", "almost"]
Outcome = Literal["decided", "unable_to_decide"]
UndecidedReason = Literal["insufficient_evidence", "conflicting_evidence"]
Route = Literal["quick", "deep"]
Relation = Literal["supports", "contradicts", "context", "irrelevant"]
Dimension = Literal[
    "population", "timeframe", "units", "baseline", "condition", "jurisdiction", "definition"
]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Assertion(Record):
    id: Literal["a1"] = "a1"
    text: Text
    kind: Literal["direct_record", "causal", "predictive", "generalized", "interpretive", "value"]
    consequential: bool
    recommended_route: Route


class ClaimPlan(Record):
    assertions: Annotated[list[Assertion], Field(max_length=1)]
    questions: Annotated[list[Short], Field(max_length=4)]
    scope_note: Text


class Query(Record):
    assertion_id: Literal["a1"]
    text: Short
    purpose: Literal["support", "contradiction", "context"]


class SearchPlan(Record):
    queries: Annotated[list[Query], Field(max_length=3)]
    gap: Short | None


class Span(Record):
    id: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    text: str
    kind: Literal["sentence", "block"]


class SnapshotMetadata(Record):
    id: str
    url: str
    canonical_url: str
    title: str
    published_date: str | None
    retrieved_at: AwareDatetime
    normalization_version: str = "whitespace-v1"
    splitter_version: str = "blocks-sentences-v1"
    content_hash: str
    duplicate_group: str
    limitations: list[str]


class Snapshot(SnapshotMetadata):
    original_text: str
    normalized_text: str
    spans: list[Span]


class Citation(Record):
    snapshot_id: Identifier
    span_ids: Annotated[
        list[Annotated[int, Field(strict=True, ge=1)]], Field(min_length=1, max_length=20)
    ]


class ProposedFlag(Record):
    # Validate semantic flag vocabulary independently; invalid flags are audit records.
    type: Short
    dimension: Short
    explanation: Text


class Assessment(Record):
    citation: Citation
    relation: Relation
    scope_match: bool
    authoritative_record: bool
    credible_synthesis: bool
    synthesis_coverage: Text | None
    publisher: Short | None
    origin: Short | None
    independence: Literal["established", "shared", "unknown"]
    provenance_span_ids: Annotated[
        list[Annotated[int, Field(strict=True, ge=1)]], Field(max_length=20)
    ]
    provenance_note: Text | None
    rationale: Text
    limitations: Annotated[list[Short], Field(max_length=8)]
    flags: Annotated[list[ProposedFlag], Field(max_length=8)]


class AssessmentBatch(Record):
    assessments: Annotated[list[Assessment], Field(max_length=12)]
    gap: Short | None


class Excerpt(Record):
    span_ids: list[int]
    start: int
    end: int
    text: str
    quote_hash: str


class Evidence(Record):
    id: str
    assertion_id: Literal["a1"] = "a1"
    assessment: Assessment
    excerpts: list[Excerpt]
    admissible: bool
    rejection_reason: str | None


class QualificationFlag(Record):
    type: Literal["misleading_comparison", "narrow_scope"]
    dimension: Dimension
    explanation: str
    evidence_ids: list[str]


class ExplanationUnit(Record):
    text: Text
    evidence_ids: Annotated[list[Identifier], Field(min_length=1, max_length=12)]


class AlmostCorrection(Record):
    what_is_correct: ExplanationUnit
    what_needs_correction: ExplanationUnit
    corrected_claim: ExplanationUnit

    @model_validator(mode="after")
    def nonblank_correction(self):
        for unit in (self.what_is_correct, self.what_needs_correction, self.corrected_claim):
            if not unit.text.strip():
                raise ValueError("Every correction part requires nonblank text.")
        return self


class Synthesis(Record):
    # A proposal, not an assigned verdict. Python and a semantic check must admit it.
    almost_correction: AlmostCorrection | None
    units: Annotated[list[ExplanationUnit], Field(min_length=1, max_length=6)]


class Decision(Record):
    outcome: Outcome
    verdict: Verdict | None
    unable_to_decide_reason: UndecidedReason | None
    almost_correction: AlmostCorrection | None

    @model_validator(mode="after")
    def consistent_decision(self):
        if self.outcome == "unable_to_decide":
            if self.verdict is not None or self.unable_to_decide_reason is None:
                raise ValueError("Unable to decide requires a reason and no truth verdict.")
        elif self.verdict is None or self.unable_to_decide_reason is not None:
            raise ValueError("A decided outcome requires a truth verdict and no undecided reason.")
        if (self.verdict == "almost") != (self.almost_correction is not None):
            raise ValueError("Only Almost requires a complete cited correction.")
        return self


class Finding(Decision):
    assertion_id: Literal["a1"] = "a1"
    evidence_ids: list[str]
    qualification_flags: list[QualificationFlag]
    qualification_check: Literal["assessed", "unknown"]
    limitations: list[str]


class InvestigationResult(Decision):
    assertion: Assertion
    scope_note: str
    finding: Finding
    explanation: list[ExplanationUnit]
    limitations: list[str]
    model: str
    prompt_version: str
    application_version: str
    configuration: dict[str, str | int | float | bool]
    budget_used: dict[str, int]
    # Safe adapter metadata only; no prompts or raw responses.
    provider_attempts: list[dict[str, str | int | float | None]]
    token_usage: dict[str, int]

    @model_validator(mode="after")
    def matches_finding(self):
        for field in Decision.model_fields:
            if getattr(self, field) != getattr(self.finding, field):
                raise ValueError("Result and finding decisions must agree.")
        return self


class SourceChange(Record):
    url: str
    change: Literal["new", "changed", "unchanged", "not_selected", "retrieval_failed"]
    metadata_changed: bool = False


class Comparison(Record):
    comparison_status: Literal["complete", "not_applicable", "pending", "unavailable"]
    baseline_id: str | None = None
    scope_changed: bool = False
    sources: list[SourceChange] = Field(default_factory=list)
    verdict_changed: bool = False
    decision_changed: bool = False
    same_relevant_evidence: bool = False
    consistency_status: Literal["inconsistent", "no_inconsistency_detected", "not_comparable"] = (
        "not_comparable"
    )
    recheck_status: Literal["disabled"] = "disabled"
    baseline_fingerprint: str | None = None
    current_fingerprint: str | None = None
    algorithm: str = "relevant-evidence-v2"
    configuration_changed: bool = False
    limitations: list[str] = Field(default_factory=list)
