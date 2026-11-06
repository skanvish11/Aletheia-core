import type {
  EvidenceRelation,
  FlagDimension,
  FlagType,
  InvestigationEvent,
  InvestigationStatus,
  Verdict,
} from './api/types'

export const VERDICT_LABEL: Record<Verdict, string> = {
  supported: 'Supported',
  contradicted: 'Contradicted',
  mixed: 'Mixed evidence',
  insufficient_evidence: 'Insufficient evidence',
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
  not_relevant: 'Not relevant',
}

export const STATUS_LABEL: Record<InvestigationStatus, string> = {
  queued: 'Queued',
  running: 'Researching',
  needs_clarification: 'Needs clarification',
  completed: 'Completed',
  partial: 'Partial result',
  failed: 'Failed',
}

function text(value: unknown): string | null {
  return typeof value === 'string' || typeof value === 'number' ? String(value) : null
}

/** One plain line per event. Shows what actually happened; never a percentage. */
export function describeEvent(event: InvestigationEvent): string {
  const p = event.payload
  switch (event.type) {
    case 'investigation_queued':
      return 'Queued'
    case 'investigation_started':
      return 'Started research'
    case 'claim_interpreted': {
      const n = text(p.assertion_count)
      return n ? `Interpreted the claim as ${n} checkable assertion${n === '1' ? '' : 's'}` : 'Interpreted the claim'
    }
    case 'stage_started':
      return `Started ${text(p.stage) ?? 'the next step'}`
    case 'task_output_rejected':
      return 'Rejected a malformed model answer'
    case 'qualification_flag_dropped':
      return 'Dropped a qualification flag that didn’t pass validation'
    case 'clarification_required':
      return 'Needs clarification before researching'
    case 'route_selected':
      return `Chose ${text(p.route) === 'deep' ? 'deeper research' : 'a quick check'}${text(p.reason) ? `: ${text(p.reason)}` : ''}`
    case 'search_started':
      return `Searching “${text(p.query) ?? '…'}”`
    case 'search_completed':
      return `Search “${text(p.query) ?? '…'}” returned ${text(p.result_count) ?? '?'} results`
    case 'source_extracted':
      return `Read ${text(p.url) ?? 'a source'}`
    case 'source_rejected':
      return `Rejected ${text(p.url) ?? 'a source'}${text(p.reason) ? `: ${text(p.reason)}` : ''}`
    case 'evidence_checked':
      return `Checked ${text(p.check) ?? 'evidence'} for ${text(p.evidence_id) ?? 'a passage'}: ${text(p.result) ?? 'done'}`
    case 'route_escalated':
      return 'Escalated to deeper research'
    case 'followup_planned':
      return `Planned a follow-up search${text(p.gap) ? ` for: ${text(p.gap)}` : ''}`
    case 'sources_deferred':
      return `Left ${text(p.count) ?? 'some'} search results unread to stay within page limits`
    case 'research_gate':
      return p.action === 'followup'
        ? `Decided to search further${text(p.gap) ? `: ${p.gap}` : ''}`
        : 'Decided to stop searching'
    case 'budget_reached':
      return `Reached the ${text(p.budget) ?? 'research'} limit`
    case 'comparison_completed':
      return 'Compared with the earlier version'
    case 'consistency_flagged':
      return 'Flagged an inconsistency with the earlier version'
    case 'investigation_completed':
      return 'Finished'
    case 'investigation_partial':
      return 'Finished with a partial result'
    case 'investigation_failed':
      return 'Failed before reaching a verdict'
  }
}

export function formatTime(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}
