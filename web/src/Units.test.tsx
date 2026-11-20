// @vitest-environment jsdom
import { render, within } from '@testing-library/react'
import { expect, it } from 'vitest'
import { Units } from './components/Findings'
import { buildEvidenceIndex, EvidenceIndexContext } from './evidenceIndex'
import { RECORDINGS } from './fixtures'

it('keeps both citations after the full paragraph even when neither quote matches a sentence', () => {
  const recording = RECORDINGS.find((run) => !run.sample && run.evidence.evidence.length >= 2)!
  const index = buildEvidenceIndex(recording.evidence)
  const ids = [...index.keys()].slice(0, 2).reverse()
  const text = 'Velvet cushions faded. Bronze hinges rattled.'
  const { getByRole } = render(
    <EvidenceIndexContext.Provider value={index}>
      <Units units={[{ text, evidence_ids: ids }]} />
    </EvidenceIndexContext.Provider>,
  )
  const paragraph = getByRole('paragraph')
  const buttons = within(paragraph).getAllByRole('button')
  expect(buttons.map((button) => button.textContent)).toEqual(ids.map((id) => String(index.get(id)!.number)))
  const beforeCitations = document.createRange()
  beforeCitations.setStart(paragraph, 0)
  beforeCitations.setEndBefore(buttons[0])
  expect(beforeCitations.toString()).toBe(text)
})
