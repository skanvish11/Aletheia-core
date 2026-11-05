"""Public contracts; execution status is distinct from a future factual verdict."""

import hashlib
import json
import unicodedata
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

Status = Literal["queued", "running", "needs_clarification", "completed", "partial", "failed"]
Stage = Literal[
    "interpreting", "planning", "searching", "extracting", "verifying", "synthesizing", "comparing"
]
ACTIVE_STATUSES = {"queued", "running"}
ContextText = Annotated[str, Field(strict=True, max_length=4000)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaimContext(Contract):
    timeframe: ContextText | None = None
    location: ContextText | None = None
    definitions: ContextText | None = None
    notes: ContextText | None = None

    def supplied(self) -> dict[str, str | None]:
        return self.model_dump(exclude_unset=True)


class InvestigationRequest(Contract):
    claim: Annotated[str, Field(strict=True, min_length=1, max_length=8000)]
    context: ClaimContext = Field(default_factory=ClaimContext)

    @field_validator("claim")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Claim must contain non-whitespace text.")
        return value

    def request_key(self) -> str:
        # Preserve original text in storage; normalize only the matching representation.
        payload = {
            "claim": unicodedata.normalize("NFC", self.claim.strip()),
            "context": self.context.supplied(),
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class PublicError(Contract):
    message: str


class InvestigationLinks(Contract):
    self: str


class Investigation(Contract):
    id: UUID
    claim: str
    context: dict[str, str | None]
    version: int = Field(ge=1)
    parent_id: UUID | None = None
    status: Status
    stage: Stage | None = None
    route: Literal["quick", "deep"] | None = None
    stop_reason: (
        Literal[
            "evidence_sufficient",
            "no_useful_query",
            "budget_exhausted",
            "deadline_exceeded",
            "provider_failure",
            "interrupted",
        ]
        | None
    ) = None
    reused: bool
    created_at: AwareDatetime
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None
    # This milestone has no synthesis or public write path for results.
    result: None = None
    clarification_questions: list[str] | None = None
    error: PublicError | None = None
    links: InvestigationLinks


class InvestigationEvent(Contract):
    investigation_id: UUID
    sequence: int = Field(ge=1)
    timestamp: AwareDatetime
    type: Literal["investigation_queued", "investigation_failed"]
    stage: Stage | None = None
    payload: dict[str, str]
