"""Versioned direct-research contracts, independent of historical saved decisions."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Short = Annotated[str, Field(strict=True, min_length=1, max_length=400)]
ComponentId = Annotated[str, Field(strict=True, pattern=r"^c[1-8]$")]
Method = Literal[
    "record_lookup",
    "record_comparison",
    "causal",
    "prediction",
    "counterfactual",
    "scientific_inference",
    "interpretive",
    "mixed",
]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ComparisonSpec(Record):
    left: Short
    right: Short
    metric: Short
    operator: Literal["lt", "le", "eq", "ne", "ge", "gt"]
    units: Short
    period: Short
    population: Short
    definition: Short
    # A superlative requires coverage of the whole comparison set before True.
    exhaustive: bool


class Component(Record):
    id: ComponentId
    text: Annotated[str, Field(strict=True, min_length=1, max_length=8000)]
    # Exact substring of the submitted assertion, never a corrected paraphrase.
    role: Literal["essential", "modifier"]
    subject: Short
    predicate: Short
    timeframe: Short | None
    location_or_population: Short | None
    comparison: ComparisonSpec | None


class ClaimAnalysis(Record):
    contract_version: Literal["direct-v1"] = "direct-v1"
    primary_type: Literal[
        "direct_fact",
        "direct_comparison",
        "causal",
        "prediction",
        "counterfactual",
        "scientific_inference",
        "interpretive",
        "mixed",
    ]
    scope: Literal["complete", "missing"]
    required_method: Method
    supported: bool
    reason: Short
    missing_scope: Annotated[list[Short], Field(max_length=4)]
    components: Annotated[list[Component], Field(min_length=1, max_length=8)]

    @model_validator(mode="after")
    def consistent_route(self):
        expected = {"direct_fact": "record_lookup", "direct_comparison": "record_comparison"}
        if self.required_method != expected.get(self.primary_type, self.primary_type):
            raise ValueError("Claim type and required method disagree.")
        if self.supported != (self.required_method in {"record_lookup", "record_comparison"}):
            raise ValueError("Support is determined by the required method, not search success.")
        if (self.scope == "missing") != bool(self.missing_scope):
            raise ValueError("Missing scope requires specific missing fields.")
        if len({c.id for c in self.components}) != len(self.components):
            raise ValueError("Component IDs must be unique.")
        if not any(c.role == "essential" for c in self.components):
            raise ValueError("At least one essential component is required.")
        if self.primary_type == "direct_comparison" and not any(
            c.comparison for c in self.components
        ):
            raise ValueError("A direct comparison requires comparison fields.")
        return self


class UnsupportedMethod(Record):
    id: Literal["unsupported_method"] = "unsupported_method"
    outcome: Literal["unsupported_method"] = "unsupported_method"
    original_claim: str
    analysis: ClaimAnalysis
    explanation: str

    @model_validator(mode="after")
    def unsupported_only(self):
        if self.analysis.supported or self.analysis.scope != "complete":
            raise ValueError("Method limitation requires a clear unsupported claim.")
        return self


class SavedAnalysis(Record):
    id: Literal["claim_analysis"] = "claim_analysis"
    original_claim: str
    analysis: ClaimAnalysis


class RecordedValue(Record):
    side: Literal["left", "right"]
    entity: Short
    metric: Short
    # Numeric values use exact finite decimals; dates use ISO YYYY-MM-DD.
    value: Annotated[str, Field(strict=True, min_length=1, max_length=80)]
    kind: Literal["number", "date", "property"]
    units: Short
    period: Short
    population: Short
    definition: Short
    exact: bool
    # Literal source text anchoring the extraction; Python verifies it against citations.
    source_text: Short


class ComponentFinding(Record):
    component_id: ComponentId
    outcome: Literal["supported", "contradicted", "not_established", "conflicting"]
    evidence_ids: list[str]


class FinalCheckDiagnostic(Record):
    id: str
    code: Literal["semantic_rejection"] = "semantic_rejection"
    failed_conditions: list[str]
    affected_units: list[int]
    component_ids: list[str]
    evidence_ids: list[str]
    check: dict[str, bool | list[int] | list[str]]
    # Only the bounded proposed public explanation, never raw responses or reasoning.
    rejected_explanation: list[dict]
