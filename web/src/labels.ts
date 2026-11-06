import type {
  EvidenceRelation,
  FlagDimension,
  FlagType,
  InvestigationEvent,
  InvestigationStatus,
  Stage,
  UndecidedReason,
  Verdict,
} from './api/types'

export const VERDICT_LABEL: Record<Verdict, string> = {
  true: 'True',
  false: 'False',
  almost: 'Almost',
}

export const UNDECIDED_LABEL = 'Unable to decide'

export const UNDECIDED_REASON: Record<UndecidedReason, string> = {
  insufficient_evidence: 'There wasn’t enough admissible evidence to decide either way.',
  conflicting_evidence: 'Admissible sources disagree, and the evidence doesn’t settle which is right.',
}

const STAGE_LABEL: Record<Stage, string> = {
  interpreting: 'Interpreting the claim',
  planning: 'Planning searches',
  searching: 'Searching',
  extracting: 'Reading sources',
  verifying: 'Checking evidence',
  synthesizing: 'Writing the answer',
  comparing: 'Comparing with the earlier version',
}

/** Machine reasons from the backend, in plain words. Unknown codes pass through. */
const REASON_LABEL: Record<string, string> = {
  evidence_sufficient: 'enough evidence',
  no_useful_query: 'no useful searches left',
  budget_exhausted: 'research budget used up',
  deadline_exceeded: 'time limit reached',
  provider_failure: 'a provider failed',
  storage_failure: 'storage failed',
  interrupted: 'interrupted',
  empty_content: 'no readable text',
  followup_round_limit: 'follow-up limit reached',
}

export function reason(code: string | null): string | null {
  return code ? (REASON_LABEL[code] ?? code.replaceAll('_', ' ')) : null
}

export const FLAG_LABEL: Record<FlagType, string> = {
  misleading_comparison: 'Misleading comparison',
  narrow_scope: 'Narrower than claimed',
}

export const DIMENSION_LABEL: Record<FlagDimension, string> = {
  population: 'population',
  timeframe: 'timeframe',
  units: 'units',
  baseline: 'baseline',
  condition: 'conditions',
  jurisdiction: 'jurisdiction',
  definition: 'definition',
  evaluation_setup: 'evaluation setup',
  benchmark_subset: 'benchmark subset',
}

export const RELATION_LABEL: Record<EvidenceRelation, string> = {
  supports: 'Supports the claim',
  contradicts: 'Contradicts the claim',
  context: 'Context',
  irrelevant: 'Not relevant',
}

export const STATUS_LABEL: Record<InvestigationStatus, string> = {
  queued: 'Queued',
  running: 'Researching',
  needs_clarification: 'Needs clarification',
  completed: 'Completed',
  partial: 'Partial result',
  failed: 'Failed',
}

function text(value: string | undefined): string | null {
  return value ? value : null
}

/** One plain line per event. Shows what actually happened; never a percentage. */
export function describeEvent(event: InvestigationEvent): string {
  const p = event.payload
  switch (event.type) {
    case 'investigation_queued':
      return 'Queued'
    case 'investigation_started':
      return 'Started research'
    case 'stage_started':
      return STAGE_LABEL[p.stage as Stage] ?? 'Started the next step'
    case 'claim_interpreted':
      return 'Scoped the claim to one checkable assertion'
    case 'clarification_required':
      return 'Needs clarification before researching'
    case 'route_selected':
      return `Chose ${p.route === 'deep' ? 'deeper research' : 'a quick check'}${text(p.reason) ? `: ${p.reason}` : ''}`
    case 'search_started':
      return `Searching “${text(p.query) ?? '…'}”`
    case 'search_completed':
      return `Search “${text(p.query) ?? '…'}” returned ${text(p.result_count) ?? '?'} results`
    case 'source_extracted':
      return `Read ${text(p.url) ?? 'a source'}${p.duplicate === 'true' ? ' (duplicate of a page already read)' : ''}`
    case 'source_rejected':
      return `Couldn’t use ${text(p.url) ?? 'a source'}${reason(text(p.reason)) ? `: ${reason(text(p.reason))}` : ''}`
    case 'sources_deferred':
      return `Left ${text(p.count) ?? 'some'} search results unread to stay within page limits`
    case 'research_gate':
      return p.action === 'followup'
        ? `Decided to search further${text(p.gap) ? `: ${p.gap}` : ''}`
        : `Decided to stop searching${reason(text(p.reason)) ? `: ${reason(text(p.reason))}` : ''}`
    case 'evidence_checked': {
      const relation = RELATION_LABEL[p.relation as EvidenceRelation]
      const verdict = p.admissible === 'true' ? 'admitted' : 'not admitted'
      return `Checked a passage: ${verdict}${relation ? ` (${relation.toLowerCase()})` : ''}`
    }
    case 'route_escalated':
      return `Escalated to deeper research${text(p.reason) ? `: ${p.reason}` : ''}`
    case 'followup_planned':
      return `Planned a follow-up search${text(p.gap) ? ` for: ${p.gap}` : ''}`
    case 'budget_reached':
      return `Stopped researching: ${reason(text(p.reason)) ?? 'limit reached'}`
    case 'task_output_rejected':
      return `Rejected a malformed model answer${text(p.task) ? ` (${(p.task ?? '').replaceAll('_', ' ')})` : ''}`
    case 'qualification_flag_dropped':
      return 'Dropped a qualification flag that didn’t pass validation'
    case 'comparison_completed':
      return 'Compared with the earlier version'
    case 'consistency_flagged':
      return 'Flagged an inconsistency with the earlier version'
    case 'investigation_completed':
      return 'Finished'
    case 'investigation_partial':
      return 'Finished with a partial result'
    case 'investigation_failed':
      return 'Failed before reaching a decision'
  }
}

export function formatTime(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}
