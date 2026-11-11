// SAMPLE DATA for design concepts only. Products, sources and quotes are
// invented; URLs use reserved example domains. Shapes follow README §6/§9
// loosely; this is not the client's API contract.

export type Verdict = 'supported' | 'contradicted' | 'mixed' | 'insufficient_evidence'

export interface Source {
  id: string
  number: number
  title: string
  publisher: string
  published: string
  retrieved: string
  url: string
  relation: 'supports' | 'contradicts' | 'context'
  excerpt: string
  why: string
  limitations: string[]
  spans: string
}

export interface Sentence {
  text: string
  cites: string[]
}

export interface Caveat {
  label: string
  dimension: string
  text: string
  cites: string[]
}

export interface Sample {
  key: string
  label: string
  claim: string
  verdict: Verdict
  /** One-line answer shown next to the verdict. */
  headline: string
  caveat: Caveat | null
  summary: Sentence[]
  /** What would settle an unresolved claim (insufficient evidence only). */
  missing: string[]
  findings: Sentence[]
  limitations: string[]
  sources: Source[]
  steps: { at: string; text: string }[]
}

const northwind: Sample = {
  key: 'caveat',
  label: 'Supported, with a caveat',
  claim: 'The Northwind X2 battery lasts three times as long as earlier Northwind laptops.',
  verdict: 'supported',
  headline: 'True against the 2019 model, but not against the direct predecessor.',
  caveat: {
    label: 'Misleading comparison',
    dimension: 'baseline',
    text: 'The 3× figure compares the X2 with the 2019 X0. Against the 2023 X1, its direct predecessor, the gain is about 1.4×.',
    cites: ['s1', 's2'],
  },
  summary: [
    { text: 'Northwind’s launch notes report 18 hours for the X2 against 6 hours for the 2019 X0.', cites: ['s1'] },
    { text: 'An independent review measured 18 hours against 13 hours for the 2023 X1.', cites: ['s2'] },
  ],
  missing: [],
  findings: [
    { text: 'The maker’s figure comes from its own lab test at reduced screen brightness.', cites: ['s1'] },
    { text: 'The independent test used video playback at standard brightness.', cites: ['s2'] },
  ],
  limitations: ['Both measurements are single lab tests; real-world battery life was not assessed.'],
  sources: [
    {
      id: 's1',
      number: 1,
      title: 'Northwind X2 launch notes',
      publisher: 'Northwind (sample)',
      published: '15 Sep 2026',
      retrieved: '3 Nov 2026, 12:00',
      url: 'https://example.com/northwind/x2-launch-notes',
      relation: 'supports',
      excerpt:
        'In our lab tests the X2 ran for 18 hours on a single charge. The 2019 Northwind X0 ran for 6 hours under the same conditions.',
      why: 'Directly reports the 3× ratio, measured against the 2019 model.',
      limitations: ['Maker’s own test at 150-nit brightness.'],
      spans: 's14–s15',
    },
    {
      id: 's2',
      number: 2,
      title: 'Northwind X2 review: battery tested against the X1',
      publisher: 'Example Reviews (sample)',
      published: '2 Oct 2026',
      retrieved: '3 Nov 2026, 12:00',
      url: 'https://example.org/reviews/northwind-x2-vs-x1',
      relation: 'context',
      excerpt: 'In our video-playback test the X2 lasted 18 hours, compared with 13 hours for last year’s X1.',
      why: 'Shows the gain over the direct predecessor is about 1.4×.',
      limitations: [],
      spans: 's31',
    },
  ],
  steps: [
    { at: '12:00:01', text: 'Understood the claim as one checkable assertion' },
    { at: '12:00:06', text: 'Chose a quick check: a published test figure can settle it' },
    { at: '12:00:11', text: 'Searched “Northwind X2 battery life hours” — 7 results' },
    { at: '12:00:14', text: 'Searched “Northwind X2 vs X1 battery test” — 5 results' },
    { at: '12:00:20', text: 'Read 2 sources' },
    { at: '12:00:30', text: 'Checked 2 quotations against the stored pages' },
    { at: '12:00:41', text: 'Wrote the verdict' },
  ],
}

const degradation: Sample = {
  key: 'insufficient',
  label: 'Insufficient evidence',
  claim: 'The Northwind X2 battery keeps 95% of its capacity after 1,000 charge cycles.',
  verdict: 'insufficient_evidence',
  headline: 'Only the maker has published this figure, and no independent test covers 1,000 cycles.',
  caveat: null,
  summary: [
    { text: 'Northwind’s spec sheet states 95% capacity after 1,000 cycles but does not describe the test.', cites: ['s3'] },
    { text: 'The only independent review ran 300 cycles, so it cannot confirm or contradict the claim.', cites: ['s4'] },
  ],
  missing: [
    'An independent test that runs at least 1,000 charge cycles',
    'The maker’s test method (temperature, charge rate, depth of discharge)',
  ],
  findings: [],
  limitations: ['Two searches for long-term battery tests returned no relevant results.'],
  sources: [
    {
      id: 's3',
      number: 1,
      title: 'Northwind X2 technical specifications',
      publisher: 'Northwind (sample)',
      published: '15 Sep 2026',
      retrieved: '3 Nov 2026, 12:10',
      url: 'https://example.com/northwind/x2-specs',
      relation: 'context',
      excerpt: 'Battery: 72 Wh. Retains up to 95% capacity after 1,000 cycles.',
      why: 'States the figure, but as a marketing claim with no method.',
      limitations: ['“Up to” is a maximum, not a typical result.', 'No test conditions given.'],
      spans: 's8',
    },
    {
      id: 's4',
      number: 2,
      title: 'Six months with the Northwind X2',
      publisher: 'Example Reviews (sample)',
      published: '20 Oct 2026',
      retrieved: '3 Nov 2026, 12:10',
      url: 'https://example.org/reviews/northwind-x2-six-months',
      relation: 'context',
      excerpt: 'After 300 full cycles our unit reported 98% of its original capacity.',
      why: 'An independent measurement, but at 300 cycles rather than 1,000.',
      limitations: ['A single unit.'],
      spans: 's22',
    },
  ],
  steps: [
    { at: '12:10:01', text: 'Understood the claim as one checkable assertion' },
    { at: '12:10:05', text: 'Chose deeper research: long-term figures need independent tests' },
    { at: '12:10:12', text: 'Searched “Northwind X2 battery 1000 cycles” — 4 results' },
    { at: '12:10:19', text: 'Searched “Northwind X2 battery degradation test” — 3 results' },
    { at: '12:10:27', text: 'Read 2 sources; rejected 1 as a copy of the spec sheet' },
    { at: '12:10:36', text: 'Follow-up search for long-term independent tests — no relevant results' },
    { at: '12:10:48', text: 'Wrote the verdict' },
  ],
}

export const SAMPLES: Sample[] = [northwind, degradation]

export const VERDICT_LABEL: Record<Verdict, string> = {
  supported: 'Supported',
  contradicted: 'Contradicted',
  mixed: 'Mixed evidence',
  insufficient_evidence: 'Insufficient evidence',
}

export const RELATION_LABEL: Record<Source['relation'], string> = {
  supports: 'Supports the claim',
  contradicts: 'Contradicts the claim',
  context: 'Context',
}
