// @vitest-environment jsdom
import { cleanup, render, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { EvidenceResponse, Investigation, InvestigationEvent } from '../api/types'
import { Home } from './Home'
import { Report } from './Report'

/**
 * Responses captured from the real backend (API, worker and SQLite) with synthetic
 * providers, by web/scripts/capture_backend_fixtures.py. Rendering them guards the
 * client against drifting from the shapes the backend actually returns.
 */
interface Captured {
  investigation: Investigation
  evidence: EvidenceResponse
  events: InvestigationEvent[]
}

const captured = import.meta.glob<Captured>('../fixtures/backend/*.json', { eager: true, import: 'default' })

function load(name: string): Captured {
  const response = captured[`../fixtures/backend/${name}.json`]
  if (!response) throw new Error(`No captured response named ${name}`)
  return response
}

function renderCaptured(name: string): HTMLElement {
  const { investigation, evidence, events } = load(name)
  render(
    <Report
      investigation={investigation}
      evidence={evidence}
      events={events}
      researchDone
      finished
      loadError={null}
      replay={false}
      reused={false}
      onRetry={() => {}}
    />,
  )
  return document.querySelector<HTMLElement>('section.conclusion')!
}

afterEach(cleanup)

describe('rendering captured backend responses', () => {
  it.each([
    ['true', 'True'],
    ['false', 'False'],
    ['almost', 'Almost'],
    ['insufficient', 'Insufficient evidence'],
    ['conflicting', 'Conflicting evidence'],
    ['finalization-timeout', 'True'],
  ])('%s renders the contracted label "%s"', (name, label) => {
    const conclusion = renderCaptured(name)
    expect(within(conclusion).getByRole('heading', { level: 2 }).textContent).toBe(label)
  })

  it('shows the three correction parts for Almost', () => {
    const conclusion = renderCaptured('almost')
    expect(within(conclusion).getAllByRole('term')).toHaveLength(3)
  })

  it('keeps the decision linked to its evidence when the explanation is empty', () => {
    const { investigation } = load('finalization-timeout')
    expect(investigation.status).toBe('partial')
    expect(investigation.result?.explanation).toEqual([])
    expect(investigation.result?.finding.evidence_ids.length).toBeGreaterThan(0)

    const conclusion = renderCaptured('finalization-timeout')
    expect(conclusion.textContent).toContain('No written explanation was saved')
    expect(within(conclusion).getAllByRole('link').length).toBe(investigation.result?.finding.evidence_ids.length)
  })

  it('describes a partial run without claiming fewer sources', () => {
    const conclusion = renderCaptured('finalization-timeout')
    expect(conclusion.textContent).toContain('Partial result')
    expect(conclusion.textContent).not.toMatch(/fewer sources/)
    // The backend's saved limitation says what was unfinished, and the report shows it.
    const limitations = document.querySelector('.limitations')!
    expect(limitations.textContent).toContain('The explanation could not be finalized')
  })

  it('adds no evidence fallback when the explanation already cites sources', () => {
    const conclusion = renderCaptured('true')
    expect(conclusion.textContent).not.toContain('The decision rests on this evidence')
  })
})

describe('sample rows on the home page', () => {
  it('keep the two undecided labels distinct', () => {
    const recordings = ['insufficient', 'conflicting'].map((name) => ({ label: name, sample: false, ...load(name) }))
    render(
      <Home submitting={false} error={null} recordings={recordings} onSubmit={() => {}} onOpen={() => {}} />,
    )
    const labels = [...document.querySelectorAll('.sample .verdict')].map((el) => el.textContent)
    expect(labels).toEqual(['Insufficient evidence', 'Conflicting evidence'])
  })
})
