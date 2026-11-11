// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { Decision, Investigation, InvestigationResult } from '../api/types'
import { sampleMisleadingComparison as sample } from '../fixtures/sample-misleading-comparison'
import { Report } from './Report'

afterEach(cleanup)

/** Render the sample report with a different decision on both the result and its finding. */
function renderWith(decision: Decision, status: Investigation['status'] = 'completed'): HTMLElement {
  const base = sample.investigation.result as InvestigationResult
  const result: InvestigationResult = { ...base, ...decision, finding: { ...base.finding, ...decision } }
  render(
    <Report
      investigation={{ ...sample.investigation, status, result }}
      evidence={sample.evidence}
      events={sample.events}
      researchDone
      finished
      loadError={null}
      replay
      reused={false}
      onRetry={() => {}}
    />,
  )
  return document.querySelector<HTMLElement>('section.conclusion')!
}

/** The result label: True, False, Almost or an undecided reason, plus any caveat. */
function resultLabel(): HTMLElement {
  return document.getElementById('result-label')!
}

const decided = { unable_to_decide_reason: null, almost_correction: null } as const

describe('Report conclusion', () => {
  it('shows True with the misleading-comparison caveat and its citations', () => {
    const conclusion = renderWith({ outcome: 'decided', verdict: 'true', ...decided })
    expect(resultLabel().textContent).toBe('True, with a caveat')
    const flag = within(conclusion).getByRole('note')
    expect(flag.textContent).toContain('Misleading comparison')
    expect(flag.textContent).toContain('baseline')
    expect(within(flag).getAllByRole('button').map((a) => a.textContent)).toEqual(['1', '2'])
  })

  it('shows the three-part correction for Almost', () => {
    const unit = (text: string) => ({ text, evidence_ids: ['ev2'] })
    const conclusion = renderWith({
      outcome: 'decided',
      verdict: 'almost',
      unable_to_decide_reason: null,
      almost_correction: {
        what_is_correct: unit('The X2 lasts 18 hours.'),
        what_needs_correction: unit('The gain over the X1 is 1.4x, not 3x.'),
        corrected_claim: unit('The X2 lasts about 1.4 times as long as the X1.'),
      },
    })
    expect(resultLabel().textContent).toContain('Almost')
    const terms = within(conclusion)
      .getAllByRole('term')
      .map((dt) => dt.textContent)
    expect(terms).toEqual(['What’s correct', 'What needs correcting', 'Corrected claim'])
    expect(conclusion.textContent).toContain('about 1.4 times as long as the X1')
  })

  it('shows Conflicting evidence with its reason and a neutral partial-run note', () => {
    const conclusion = renderWith(
      {
        outcome: 'unable_to_decide',
        verdict: null,
        unable_to_decide_reason: 'conflicting_evidence',
        almost_correction: null,
      },
      'partial',
    )
    const heading = resultLabel()
    expect(heading.textContent).toMatch(/^Conflicting evidence/)
    expect(document.querySelector('.report-head')?.textContent).toContain('sources disagree')
    expect(conclusion.textContent).toContain('Partial result')
    expect(conclusion.textContent).not.toContain('fewer sources')
  })

  it('labels insufficient evidence distinctly from conflicting evidence', () => {
    renderWith({
      outcome: 'unable_to_decide',
      verdict: null,
      unable_to_decide_reason: 'insufficient_evidence',
      almost_correction: null,
    })
    expect(resultLabel().textContent).toMatch(/^Insufficient evidence/)
  })
})

describe('Report evidence pane', () => {
  it('numbers admitted evidence first and collapses passages that were not admitted', () => {
    renderWith({ outcome: 'decided', verdict: 'true', ...decided })
    const pane = screen.getByRole('complementary', { name: 'Evidence' })
    const tabs = within(within(pane).getByRole('group', { name: 'Admitted evidence' })).getAllByRole('button')
    expect(tabs.map((t) => t.textContent)).toEqual(['1', '2'])
    const rejected = pane.querySelector('details.pane-rejected') as HTMLDetailsElement
    expect(rejected.open).toBe(false)
    expect(rejected.querySelector('summary')?.textContent).toBe('1 more passage checked but not admitted')
    expect(rejected.textContent).toContain('Repeats the claim without independent measurement.')
    expect(rejected.querySelector('.rejected-number')?.textContent).toBe('3')
  })

  it('shows the cited evidence when a citation is chosen', () => {
    renderWith({ outcome: 'decided', verdict: 'true', ...decided })
    const pane = screen.getByRole('complementary', { name: 'Evidence' })
    const cite = within(screen.getByRole('note')).getAllByRole('button')[1]
    fireEvent.click(cite)
    expect(cite.getAttribute('aria-pressed')).toBe('true')
    expect(within(pane).getByRole('article').getAttribute('aria-label')).toBe('Source 2')
    const tab = within(pane).getByRole('button', { name: 'Source 2' })
    expect(tab.getAttribute('aria-pressed')).toBe('true')
  })
})
