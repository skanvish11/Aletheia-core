// Client-side view of the backend contract.
//
// RECONCILED with src/aletheia/contracts.py and the running backend's
// /openapi.json at dcb4179 (backend foundation, #8): Investigation, ClaimContext,
// InvestigationLinks, the error body and /health.
//
// STILL PROVISIONAL (not served by the backend yet): InvestigationResult and its
// findings, the /evidence response, and most event types and payloads. Those
// follow README sections 6 and 9 until the research pipeline ships them.

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
  | 'interrupted'

export type Route = 'quick' | 'deep'

export type Verdict = 'supported' | 'contradicted' | 'mixed' | 'insufficient_evidence'

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

/** A sentence of explanation tied to the evidence that backs it. */
export interface ExplanationUnit {
  text: string
  evidence_ids: string[]
}

export interface AssertionFinding {
  assertion_id: string
  position: number
  scoped_text: string
  route: Route
  verdict: Verdict
  explanation: ExplanationUnit[]
  qualification_check: 'assessed' | 'unknown'
  qualification_flags: QualificationFlag[]
  limitations: string[]
}

export interface InvestigationResult {
  overall_verdict: Verdict
  summary: ExplanationUnit[]
  findings: AssertionFinding[]
  conflicts: string[]
  limitations: string[]
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
}

export interface Investigation {
  id: string
  claim: string
  context: ClaimContext
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
  /** Always null in the backend foundation; populated once synthesis ships. */
  result: InvestigationResult | null
  clarification_questions: string[] | null
  error: { message: string } | null
  links: InvestigationLinks
}

/** GET /health. research_enabled is false until the research worker exists. */
export interface HealthStatus {
  status: string
  database: string
  research_enabled: boolean
}

/** Every 4xx/5xx body from the backend: a sanitized message that never echoes input. */
export interface ErrorBody {
  detail: string
}

export interface SourceSnapshot {
  id: string
  url: string
  title: string | null
  publisher: string | null
  author: string | null
  published_date: string | null
  retrieved_at: string
  extraction_status: 'succeeded' | 'failed'
}

/** A contiguous excerpt rebuilt by code from stored spans; never model-written text. */
export interface Excerpt {
  span_ids: string[]
  text: string
}

export type EvidenceRelation = 'supports' | 'contradicts' | 'context' | 'not_relevant'

export interface EvidenceAssessment {
  id: string
  assertion_id: string
  snapshot_id: string
  relation: EvidenceRelation
  excerpts: Excerpt[]
  rationale: string
  limitations: string[]
  admissible: boolean
}

export interface EvidenceResponse {
  investigation_id: string
  sources: SourceSnapshot[]
  assessments: EvidenceAssessment[]
}

/**
 * Every event type the backend emits (contracts.py InvestigationEvent.type). The
 * backend sends each as a named SSE event, so the client must listen for each name.
 */
export const EVENT_TYPES = [
  'investigation_queued',
  'investigation_started',
  'stage_started',
  'claim_interpreted',
  'clarification_required',
  'route_selected',
  'search_started',
  'search_completed',
  'source_extracted',
  'source_rejected',
  'evidence_checked',
  'route_escalated',
  'followup_planned',
  'budget_reached',
  'task_output_rejected',
  'qualification_flag_dropped',
  'comparison_completed',
  'consistency_flagged',
  'investigation_completed',
  'investigation_partial',
  'investigation_failed',
] as const

export type EventType = (typeof EVENT_TYPES)[number]

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
  /** Typed per event on the backend; read defensively here until contracts.py exists. */
  payload: Record<string, unknown>
}
