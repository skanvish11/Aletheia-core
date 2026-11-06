import type { Assessment, Evidence, Excerpt, InvestigationEvent, SourceSnapshot } from '../api/types'
import type { Recording } from './index'

// SAMPLE DATA for UI development. The product, sources and quotes are invented;
// URLs use reserved example domains. Shapes and event payloads follow the step 3
// backend (#11). Replace with exported real recordings before any hosted demo.

const id = '00000000-0000-4000-8000-000000000001'
const t = (seconds: number) => new Date(Date.UTC(2026, 10, 3, 18, 0, seconds)).toISOString()

function source(snapshotId: string, url: string, title: string, published: string, at: number): SourceSnapshot {
  return {
    id: snapshotId,
    url,
    canonical_url: url,
    title,
    published_date: published,
    retrieved_at: t(at),
    normalization_version: 'whitespace-v1',
    splitter_version: 'blocks-sentences-v1',
    content_hash: `sample-hash-${snapshotId}`,
    duplicate_group: snapshotId,
    limitations: [],
  }
}

function excerpt(spanIds: number[], start: number, text: string): Excerpt {
  return { span_ids: spanIds, start, end: start + text.length, text, quote_hash: `sample-quote-${start}` }
}

function assessment(
  snapshotId: string,
  spanIds: number[],
  fields: Pick<Assessment, 'relation' | 'publisher' | 'rationale' | 'limitations'> & Partial<Assessment>,
): Assessment {
  return {
    citation: { snapshot_id: snapshotId, span_ids: spanIds },
    scope_match: true,
    authoritative_record: false,
    credible_synthesis: false,
    synthesis_coverage: null,
    origin: null,
    independence: 'unknown',
    provenance_span_ids: [],
    provenance_note: null,
    flags: [],
    ...fields,
  }
}

const evidence: Evidence[] = [
  {
    id: 'ev1',
    assertion_id: 'a1',
    assessment: assessment('snap1', [14, 15], {
      relation: 'supports',
      publisher: 'Northwind (sample)',
      authoritative_record: true,
      rationale: 'Directly reports a 3× ratio, but against the 2019 model.',
      limitations: ['Maker’s own test at 150-nit brightness.'],
    }),
    excerpts: [
      excerpt(
        [14, 15],
        2210,
        'In our lab tests the X2 ran for 18 hours on a single charge. The 2019 Northwind X0 ran for 6 hours under the same conditions.',
      ),
    ],
    admissible: true,
    rejection_reason: null,
  },
  {
    id: 'ev2',
    assertion_id: 'a1',
    assessment: assessment('snap2', [31], {
      relation: 'context',
      publisher: 'Example Reviews (sample)',
      independence: 'established',
      rationale: 'Shows the gain over the direct predecessor is about 1.4×.',
      limitations: [],
    }),
    excerpts: [
      excerpt([31], 4120, 'In our video-playback test the X2 lasted 18 hours, compared with 13 hours for last year’s X1.'),
    ],
    admissible: true,
    rejection_reason: null,
  },
  {
    id: 'ev3',
    assertion_id: 'a1',
    assessment: assessment('snap3', [7], {
      relation: 'irrelevant',
      publisher: 'Example Deals (sample)',
      scope_match: false,
      rationale: 'A retailer listing that repeats the 3× claim without a test.',
      limitations: [],
    }),
    excerpts: [excerpt([7], 610, 'Up to 3x the battery life of previous Northwind laptops!')],
    admissible: false,
    rejection_reason: 'Repeats the claim without independent measurement.',
  },
]

export const sampleMisleadingComparison: Recording = {
  label: 'Sample: battery-life comparison',
  sample: true,
  investigation: {
    id,
    claim: 'The Northwind X2 battery lasts three times as long as earlier Northwind laptops.',
    context: {},
    version: 1,
    parent_id: null,
    status: 'completed',
    stage: null,
    route: 'quick',
    stop_reason: 'evidence_sufficient',
    reused: false,
    created_at: t(0),
    started_at: t(1),
    finished_at: t(41),
    clarification_questions: null,
    error: null,
    links: {
      self: `/investigations/${id}`,
      events: `/investigations/${id}/events`,
      evidence: `/investigations/${id}/evidence`,
      comparison: `/investigations/${id}/comparison`,
      refresh: `/investigations/${id}/refresh`,
    },
    result: {
      outcome: 'decided',
      verdict: 'true',
      unable_to_decide_reason: null,
      almost_correction: null,
      assertion: {
        id: 'a1',
        text: 'The Northwind X2 battery lasts three times as long as at least one earlier Northwind laptop.',
        kind: 'direct_record',
        consequential: false,
        recommended_route: 'quick',
      },
      scope_note: '“Earlier Northwind laptops” is read as any earlier model, since the claim names none.',
      finding: {
        outcome: 'decided',
        verdict: 'true',
        unable_to_decide_reason: null,
        almost_correction: null,
        assertion_id: 'a1',
        evidence_ids: ['ev1', 'ev2'],
        qualification_check: 'assessed',
        qualification_flags: [
          {
            type: 'misleading_comparison',
            dimension: 'baseline',
            explanation:
              'Compares the X2 with the 2019 X0 rather than the 2023 X1; against the X1 the gain is about 1.4×, not 3×.',
            evidence_ids: ['ev1', 'ev2'],
          },
        ],
        limitations: ['The maker’s figure is from its own lab test at reduced screen brightness.'],
      },
      explanation: [
        {
          text: 'Northwind’s launch notes report 18 hours for the X2 versus 6 hours for the 2019 X0, a 3× gain.',
          evidence_ids: ['ev1'],
        },
        {
          text: 'An independent review measured the X2 at 18 hours against 13 hours for the 2023 X1, its direct predecessor.',
          evidence_ids: ['ev2'],
        },
      ],
      limitations: ['Both measurements are single lab tests; real-world battery life was not assessed.'],
      model: 'sample-model',
      prompt_version: 'sample',
      application_version: 'sample',
      configuration: {},
      budget_used: { search: 2, extract: 3, model: 6 },
      provider_attempts: [],
      token_usage: {},
    },
  },
  evidence: {
    sources: [
      source('snap1', 'https://example.com/northwind/x2-launch-notes', 'Northwind X2 launch notes', '2026-09-15', 18),
      source(
        'snap2',
        'https://example.org/reviews/northwind-x2-vs-x1',
        'Northwind X2 review: battery tested against the X1',
        '2026-10-02',
        20,
      ),
      source('snap3', 'https://example.net/deals/northwind-x2', 'Northwind X2 deals', '2026-10-20', 22),
    ],
    evidence,
  },
  events: [
    ev(1, t(0), 'investigation_queued', null, {}),
    ev(2, t(1), 'investigation_started', null, {}),
    ev(3, t(1), 'stage_started', 'interpreting', { stage: 'interpreting' }),
    ev(4, t(6), 'claim_interpreted', 'interpreting', { assertion_id: 'a1' }),
    ev(5, t(6), 'route_selected', 'interpreting', { route: 'quick', reason: 'A published test figure can settle it.' }),
    ev(6, t(7), 'stage_started', 'planning', { stage: 'planning' }),
    ev(7, t(9), 'search_started', 'searching', { query: 'Northwind X2 battery life hours', purpose: 'support' }),
    ev(8, t(11), 'search_completed', 'searching', { query: 'Northwind X2 battery life hours', result_count: '5' }),
    ev(9, t(12), 'search_started', 'searching', { query: 'Northwind X2 vs X1 battery test', purpose: 'contradiction' }),
    ev(10, t(14), 'search_completed', 'searching', { query: 'Northwind X2 vs X1 battery test', result_count: '5' }),
    ev(11, t(18), 'source_extracted', 'extracting', {
      snapshot_id: 'snap1',
      url: 'https://example.com/northwind/x2-launch-notes',
      duplicate: 'false',
    }),
    ev(12, t(18), 'stage_started', 'verifying', { stage: 'verifying' }),
    ev(13, t(24), 'evidence_checked', 'verifying', {
      evidence_id: 'ev1',
      snapshot_id: 'snap1',
      admissible: 'true',
      relation: 'supports',
    }),
    ev(14, t(25), 'source_extracted', 'extracting', {
      snapshot_id: 'snap2',
      url: 'https://example.org/reviews/northwind-x2-vs-x1',
      duplicate: 'false',
    }),
    ev(15, t(25), 'stage_started', 'verifying', { stage: 'verifying' }),
    ev(16, t(30), 'evidence_checked', 'verifying', {
      evidence_id: 'ev2',
      snapshot_id: 'snap2',
      admissible: 'true',
      relation: 'context',
    }),
    ev(17, t(31), 'source_extracted', 'extracting', {
      snapshot_id: 'snap3',
      url: 'https://example.net/deals/northwind-x2',
      duplicate: 'false',
    }),
    ev(18, t(31), 'stage_started', 'verifying', { stage: 'verifying' }),
    ev(19, t(34), 'evidence_checked', 'verifying', {
      evidence_id: 'ev3',
      snapshot_id: 'snap3',
      admissible: 'false',
      relation: 'irrelevant',
    }),
    ev(20, t(35), 'stage_started', 'synthesizing', { stage: 'synthesizing' }),
    ev(21, t(41), 'investigation_completed', null, {}),
  ],
}

function ev(
  sequence: number,
  timestamp: string,
  type: InvestigationEvent['type'],
  stage: InvestigationEvent['stage'],
  payload: Record<string, string>,
): InvestigationEvent {
  return { investigation_id: id, sequence, timestamp, type, stage, payload }
}
