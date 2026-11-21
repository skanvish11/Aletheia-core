// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from './App'
import { examples } from './examples'

beforeEach(() => {
  history.replaceState(null, '', '/')
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

it.each(examples)('opens $id and follows each citation to the correct passage', example => {
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: example.claim }))
  expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(example.claim)
  expect(screen.getByText(example.verdict)).toBeTruthy()
  for (const [i, page] of example.pages.entries()) {
    const row = document.getElementById('source-' + (i + 1)) as HTMLDetailsElement
    expect(row.open).toBe(false)
    fireEvent.click(screen.getByRole('link', { name: 'Open source ' + (i + 1) }))
    expect(row.open).toBe(true)
    expect(within(row).getByRole('link').getAttribute('href')).toBe(page.url)
  }
  fireEvent.click(screen.getByRole('button', { name: 'New Search' }))
  expect(screen.getByRole('textbox')).toBeTruthy()
})

it('submits a typed example and restores its report on refresh', () => {
  const view = render(<App />)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Venus is closest to the Sun.' } })
  fireEvent.click(screen.getByRole('button', { name: 'Verify' }))
  expect(location.search).toBe('?example=venus')
  view.unmount()
  render(<App />)
  expect(screen.getByText('false')).toBeTruthy()
})

it('explains when a custom claim cannot be researched', () => {
  render(<App />)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'A different claim' } })
  fireEvent.click(screen.getByRole('button', { name: 'Verify' }))
  expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('A different claim')
  expect(screen.getByText(/Live research is unavailable/)).toBeTruthy()
  expect(document.querySelector('.verdict')).toBeNull()
})

it.each(examples)('keeps layout C while navigating and reveals the cited $id quotes', example => {
  history.replaceState(null, '', '/?layout=c')
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: example.claim }))
  const cards = document.querySelectorAll<HTMLElement>('.evidence-card')
  expect(cards).toHaveLength(example.pages.length)
  for (const [i, card] of Array.from(cards).entries()) {
    const count = within(card).getByRole('listitem').textContent!.split(/\s+/).length
    expect(count).toBeGreaterThanOrEqual(10)
    expect(count).toBeLessThanOrEqual(15)
    const quote = card.querySelector('details')!
    expect(quote.open).toBe(false)
    fireEvent.click(screen.getByRole('link', { name: 'Open source ' + (i + 1) }))
    expect(quote.open).toBe(true)
    expect(quote.querySelector('blockquote')?.textContent).toBe(example.pages[i].passages[0].quote)
    expect(within(card).getByRole('link').getAttribute('href')).toBe(example.pages[i].url)
  }
  fireEvent.click(screen.getByRole('button', { name: 'New Search' }))
  expect(location.search).toBe('?layout=c')
  expect(screen.getByRole('textbox')).toBeTruthy()
})
