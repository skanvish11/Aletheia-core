"""Bounded model tasks and saved research records for one scoped assertion."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Text = Annotated[str, Field(strict=True, min_length=1, max_length=2000)]
Short = Annotated[str, Field(strict=True, min_length=1, max_length=400)]
Identifier = Annotated[str, Field(strict=True, min_length=1, max_length=80)]
Verdict = Literal["supported", "contradicted", "mixed", "insufficient_evidence"]
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


class Snapshot(Record):
    id: str
    url: str
    canonical_url: str
    title: str
    published_date: str | None
    retrieved_at: AwareDatetime
    original_text: str
    normalized_text: str
    normalization_version: str = "whitespace-v1"
    splitter_version: str = "blocks-sentences-v1"
    content_hash: str
    spans: list[Span]
    duplicate_group: str
    limitations: list[str]


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


class Synthesis(Record):
    units: Annotated[list[ExplanationUnit], Field(min_length=1, max_length=6)]


class Finding(Record):
    assertion_id: Literal["a1"] = "a1"
    verdict: Verdict
    evidence_ids: list[str]
    qualification_flags: list[QualificationFlag]
    qualification_check: Literal["assessed", "unknown"]
    limitations: list[str]


class InvestigationResult(Record):
    assertion: Assertion
    scope_note: str
    verdict: Verdict
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
    same_relevant_evidence: bool = False
    consistency_status: Literal["inconsistent", "no_inconsistency_detected", "not_comparable"] = (
        "not_comparable"
    )
    recheck_status: Literal["disabled"] = "disabled"
    baseline_fingerprint: str | None = None
    current_fingerprint: str | None = None
    algorithm: str = "relevant-evidence-v1"
    configuration_changed: bool = False
    limitations: list[str] = Field(default_factory=list)
