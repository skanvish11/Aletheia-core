import type { Recording } from './index'

// SAMPLE DATA for UI development. The product, sources and quotes are invented;
// URLs use reserved example domains. Replace with exported real recordings
// before any hosted demo (README section 11, companion demo client).

const id = '00000000-0000-4000-8000-000000000001'
const assertionId = 'a1'
const t = (seconds: number) => new Date(Date.UTC(2026, 10, 3, 18, 0, seconds)).toISOString()

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
    links: { self: `/investigations/${id}` },
    result: {
      overall_verdict: 'supported',
      summary: [
        {
          text: 'The 3× figure matches the maker’s lab test, but only against its 2019 model; against the 2023 model the gain is about 1.4×.',
          evidence_ids: ['ev1', 'ev2'],
        },
      ],
      conflicts: [],
      limitations: ['Both measurements are single lab tests; real-world battery life was not assessed.'],
      findings: [
        {
          assertion_id: assertionId,
          position: 1,
          scoped_text:
            'The Northwind X2 battery lasts three times as long as at least one earlier Northwind laptop.',
          route: 'quick',
          verdict: 'supported',
          explanation: [
            {
              text: 'Northwind’s launch notes report 18 hours for the X2 versus 6 hours for the 2019 X0.',
              evidence_ids: ['ev1'],
            },
            {
              text: 'An independent review measured the X2 at 18 hours against 13 hours for the 2023 X1, its direct predecessor.',
              evidence_ids: ['ev2'],
            },
          ],
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
      ],
    },
  },
  evidence: {
    investigation_id: id,
    sources: [
      {
        id: 'src1',
        url: 'https://example.com/northwind/x2-launch-notes',
        title: 'Northwind X2 launch notes',
        publisher: 'Northwind (sample)',
        author: null,
        published_date: '2026-09-15',
        retrieved_at: t(18),
        extraction_status: 'succeeded',
      },
      {
        id: 'src2',
        url: 'https://example.org/reviews/northwind-x2-vs-x1',
        title: 'Northwind X2 review: battery tested against the X1',
        publisher: 'Example Reviews (sample)',
        author: 'Sample Reviewer',
        published_date: '2026-10-02',
        retrieved_at: t(20),
        extraction_status: 'succeeded',
      },
    ],
    assessments: [
      {
        id: 'ev1',
        assertion_id: assertionId,
        snapshot_id: 'src1',
        relation: 'supports',
        excerpts: [
          {
            span_ids: ['s14', 's15'],
            text: 'In our lab tests the X2 ran for 18 hours on a single charge. The 2019 Northwind X0 ran for 6 hours under the same conditions.',
          },
        ],
        rationale: 'Directly reports a 3× ratio, against the 2019 model.',
        limitations: ['Maker’s own test at 150-nit brightness.'],
        admissible: true,
      },
      {
        id: 'ev2',
        assertion_id: assertionId,
        snapshot_id: 'src2',
        relation: 'context',
        excerpts: [
          {
            span_ids: ['s31'],
            text: 'In our video-playback test the X2 lasted 18 hours, compared with 13 hours for last year’s X1.',
          },
        ],
        rationale: 'Shows the gain over the direct predecessor is about 1.4×.',
        limitations: [],
        admissible: true,
      },
    ],
  },
  events: [
    ev(1, t(0), 'investigation_queued', null, {}),
    ev(2, t(1), 'investigation_started', 'interpreting', {}),
    ev(3, t(6), 'claim_interpreted', 'interpreting', { assertion_count: 1 }),
    ev(4, t(6), 'route_selected', 'planning', { route: 'quick', reason: 'A published test figure can settle it.' }),
    ev(5, t(9), 'search_started', 'searching', { query: 'Northwind X2 battery life hours' }),
    ev(6, t(11), 'search_completed', 'searching', { query: 'Northwind X2 battery life hours', result_count: 7 }),
    ev(7, t(12), 'search_started', 'searching', { query: 'Northwind X2 vs X1 battery test' }),
    ev(8, t(14), 'search_completed', 'searching', { query: 'Northwind X2 vs X1 battery test', result_count: 5 }),
    ev(9, t(18), 'source_extracted', 'extracting', { url: 'https://example.com/northwind/x2-launch-notes', outcome: 'succeeded' }),
    ev(10, t(20), 'source_extracted', 'extracting', { url: 'https://example.org/reviews/northwind-x2-vs-x1', outcome: 'succeeded' }),
    ev(11, t(29), 'evidence_checked', 'verifying', { check: 'span citations', result: 'passed', evidence_id: 'ev1' }),
    ev(12, t(30), 'evidence_checked', 'verifying', { check: 'span citations', result: 'passed', evidence_id: 'ev2' }),
    ev(13, t(41), 'investigation_completed', null, { verdict: 'supported' }),
  ],
}

function ev(
  sequence: number,
  timestamp: string,
  type: Recording['events'][number]['type'],
  stage: Recording['events'][number]['stage'],
  payload: Record<string, unknown>,
): Recording['events'][number] {
  return { investigation_id: id, sequence, timestamp, type, stage, payload }
}
