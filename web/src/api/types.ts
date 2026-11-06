// Client-side view of the backend contract.
//
// RECONCILED with src/aletheia/contracts.py and research_contracts.py at 6b1dc23
// (step 3 research pipeline, #11): Investigation, the decision and result models,
// the /evidence response, events, /health and the error body. Keep this file in
// step with those modules; the backend forbids extra fields, so nothing here is
// optional unless the backend makes it so.

export type InvestigationStatus =
  | 'queued'
  | 'running'
  | 'needs_clarification'
  | 'completed'
  | 'partial'
  | 'failed'

export type Stage =
  | 'interpreting'
  | 'planning'
  | 'searching'
  | 'extracting'
  | 'verifying'
  | 'synthesizing'
  | 'comparing'

export type StopReason =
  | 'evidence_sufficient'
  | 'no_useful_query'
  | 'budget_exhausted'
  | 'deadline_exceeded'
  | 'provider_failure'
  | 'storage_failure'
  | 'interrupted'

export type Route = 'quick' | 'deep'

/** A truth verdict. Only present when the outcome is decided. */
export type Verdict = 'true' | 'false' | 'almost'

export type Outcome = 'decided' | 'unable_to_decide'

export type UndecidedReason = 'insufficient_evidence' | 'conflicting_evidence'

export type FlagType = 'misleading_comparison' | 'narrow_scope'

export type FlagDimension =
  | 'population'
  | 'timeframe'
  | 'units'
  | 'baseline'
  | 'condition'
  | 'jurisdiction'
  | 'definition'
  | 'evaluation_setup'
  | 'benchmark_subset'

export interface QualificationFlag {
  type: FlagType
  dimension: FlagDimension
  explanation: string
  evidence_ids: string[]
}

/** A sentence of explanation tied to the evidence that backs it (at least one ID). */
export interface ExplanationUnit {
  text: string
  evidence_ids: string[]
}

/** Required exactly when the verdict is Almost; every part is cited. */
export interface AlmostCorrection {
  what_is_correct: ExplanationUnit
  what_needs_correction: ExplanationUnit
  corrected_claim: ExplanationUnit
}

/**
 * decided → verdict set, reason null; unable_to_decide → verdict null, reason set.
 * almost_correction is set exactly when verdict is 'almost'.
 */
export interface Decision {
  outcome: Outcome
  verdict: Verdict | null
  unable_to_decide_reason: UndecidedReason | null
  almost_correction: AlmostCorrection | null
}

export type AssertionKind =
  | 'direct_record'
  | 'causal'
  | 'predictive'
  | 'generalized'
  | 'interpretive'
  | 'value'

/** The one checkable assertion the claim was scoped to. */
export interface Assertion {
  id: string
  text: string
  kind: AssertionKind
  consequential: boolean
  recommended_route: Route
}

export interface Finding extends Decision {
  assertion_id: string
  evidence_ids: string[]
  qualification_flags: QualificationFlag[]
  qualification_check: 'assessed' | 'unknown'
  limitations: string[]
}

/** The result's decision always equals its finding's decision. */
export interface InvestigationResult extends Decision {
  assertion: Assertion
  scope_note: string
  finding: Finding
  explanation: ExplanationUnit[]
  limitations: string[]
  model: string
  prompt_version: string
  application_version: string
  configuration: Record<string, string | number | boolean>
  budget_used: Record<string, number>
  provider_attempts: Record<string, string | number | null>[]
  token_usage: Record<string, number>
}

/** Each field may be omitted or explicitly null; at most 4,000 characters (contracts.py). */
export interface ClaimContext {
  timeframe?: string | null
  location?: string | null
  definitions?: string | null
  notes?: string | null
}

export interface InvestigationLinks {
  /** API path of this investigation, e.g. /investigations/{id}. */
  self: string
  events?: string | null
  evidence?: string | null
  comparison?: string | null
  refresh?: string | null
}

export interface Investigation {
  id: string
  claim: string
  /** The supplied context fields only. */
  context: Record<string, string | null>
  version: number
  parent_id: string | null
  status: InvestigationStatus
  stage: Stage | null
  route: Route | null
  stop_reason: StopReason | null
  reused: boolean
  created_at: string
  started_at: string | null
  finished_at: string | null
  /** Set when research reached a decision (completed or partial). */
  result: InvestigationResult | null
  clarification_questions: string[] | null
  error: { message: string } | null
  links: InvestigationLinks
}

/** GET /health. research_enabled is false when the API keys are not configured. */
export interface HealthStatus {
  status: string
  database: string
  research_enabled: boolean
}

/** Every 4xx/5xx body from the backend: a sanitized message that never echoes input. */
export interface ErrorBody {
  detail: string
}

/** Metadata of a retrieved page; the stored text itself is not served. */
export interface SourceSnapshot {
  id: string
  url: string
  canonical_url: string
  title: string
  published_date: string | null
  retrieved_at: string
  normalization_version: string
  splitter_version: string
  content_hash: string
  duplicate_group: string
  limitations: string[]
}

/** A contiguous excerpt rebuilt by code from stored spans; never model-written text. */
export interface Excerpt {
  span_ids: number[]
  start: number
  end: number
  text: string
  quote_hash: string
}

export type EvidenceRelation = 'supports' | 'contradicts' | 'context' | 'irrelevant'

/** The model's reading of one cited passage, checked by code before admission. */
export interface Assessment {
  citation: { snapshot_id: string; span_ids: number[] }
  relation: EvidenceRelation
  scope_match: boolean
  authoritative_record: boolean
  credible_synthesis: boolean
  synthesis_coverage: string | null
  publisher: string | null
  origin: string | null
  independence: 'established' | 'shared' | 'unknown'
  provenance_span_ids: number[]
  provenance_note: string | null
  rationale: string
  limitations: string[]
  flags: { type: string; dimension: string; explanation: string }[]
}

export interface Evidence {
  id: string
  assertion_id: string
  assessment: Assessment
  excerpts: Excerpt[]
  admissible: boolean
  rejection_reason: string | null
}

/** GET /investigations/{id}/evidence: every checked passage, admitted or not. */
export interface EvidenceResponse {
  sources: SourceSnapshot[]
  evidence: Evidence[]
}

export type EventType =
  | 'investigation_queued'
  | 'investigation_started'
  | 'claim_interpreted'
  | 'clarification_required'
  | 'route_selected'
  | 'search_started'
  | 'search_completed'
  | 'source_extracted'
  | 'source_rejected'
  | 'evidence_checked'
  | 'route_escalated'
  | 'followup_planned'
  | 'budget_reached'
  | 'comparison_completed'
  | 'consistency_flagged'
  | 'task_output_rejected'
  | 'qualification_flag_dropped'
  | 'stage_started'
  | 'investigation_completed'
  | 'investigation_partial'
  | 'investigation_failed'

export const TERMINAL_EVENTS: ReadonlySet<EventType> = new Set([
  'investigation_completed',
  'investigation_partial',
  'investigation_failed',
  'clarification_required',
])

export interface InvestigationEvent {
  investigation_id: string
  sequence: number
  timestamp: string
  type: EventType
  stage: Stage | null
  /** String values only; keys vary by event type, so read them defensively. */
  payload: Record<string, string>
}
