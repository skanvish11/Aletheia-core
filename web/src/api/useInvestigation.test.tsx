// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Home } from '../components/Home'
import { RECORDINGS } from '../fixtures'
import type { DataSource } from './source'
import type { EvidenceResponse, Investigation, InvestigationEvent } from './types'
import { useInvestigation } from './useInvestigation'

const sample = RECORDINGS[0]
const terminal = sample.events.at(-1) as InvestigationEvent

/** A promise the test resolves or rejects by hand, to simulate a slow backend. */
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

/** A live-style source whose calls the test controls. */
function fakeSource(overrides: Partial<DataSource> = {}) {
  let push: ((event: InvestigationEvent) => void) | null = null
  const source: DataSource = {
    kind: 'live',
    canSubmit: true,
    recordings: [],
    submit: vi.fn(async () => sample.investigation),
    getInvestigation: vi.fn(async () => sample.investigation),
    getEvidence: vi.fn(async () => sample.evidence),
    subscribe: vi.fn((_id, onEvent) => {
      push = onEvent
      return () => {
        push = null
      }
    }),
    ...overrides,
  }
  return { source, emit: (event: InvestigationEvent) => push?.(event) }
}

afterEach(cleanup)

describe('submitting a claim', () => {
  it('ignores repeated submissions while one is pending', async () => {
    const pending = deferred<Investigation>()
    const { source } = fakeSource({ submit: vi.fn(() => pending.promise) })
    const { result } = renderHook(() => useInvestigation(source))

    act(() => {
      void result.current.submit('Claim one', {})
      void result.current.submit('Claim one', {})
      void result.current.submit('Claim one', {})
    })
    expect(source.submit).toHaveBeenCalledTimes(1)
    expect(result.current.state.submitting).toBe(true)

    await act(async () => pending.resolve(sample.investigation))
    expect(result.current.state.submitting).toBe(false)
    expect(result.current.state.investigation?.id).toBe(sample.investigation.id)
  })

  it('ignores the response of a submission the user abandoned', async () => {
    const pending = deferred<Investigation>()
    const { source } = fakeSource({ submit: vi.fn(() => pending.promise) })
    const { result } = renderHook(() => useInvestigation(source))

    act(() => void result.current.submit('Claim one', {}))
    act(() => result.current.close())
    await act(async () => pending.resolve(sample.investigation))

    expect(result.current.state.investigation).toBeNull()
    expect(source.getInvestigation).not.toHaveBeenCalled()
  })

  it('keeps the typed claim and re-enables the button when submission fails', async () => {
    const pending = deferred<Investigation>()
    const { source } = fakeSource({ submit: vi.fn(() => pending.promise) })
    function Harness() {
      const { state, submit } = useInvestigation(source)
      return (
        <Home
          submitting={state.submitting}
          error={state.error}
          recordings={[]}
          onSubmit={(claim) => void submit(claim, {})}
          onOpen={() => {}}
        />
      )
    }
    render(<Harness />)
    const field = screen.getByLabelText('Claim to check') as HTMLTextAreaElement
    fireEvent.change(field, { target: { value: 'Model X beats Model Y' } })
    fireEvent.click(screen.getByRole('button', { name: 'Investigate' }))

    const button = screen.getByRole('button', { name: 'Starting investigation…' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)

    await act(async () => pending.reject(new Error('Couldn’t reach the Aletheia backend.')))
    expect(screen.getByRole('alert').textContent).toContain('Couldn’t reach')
    expect(field.value).toBe('Model X beats Model Y')
    expect((screen.getByRole('button', { name: 'Investigate' }) as HTMLButtonElement).disabled).toBe(false)
  })
})

describe('loading the final report', () => {
  it('shows a load error after research ends, and retry recovers without a new investigation', async () => {
    const getEvidence = vi
      .fn<(id: string) => Promise<EvidenceResponse>>()
      .mockRejectedValueOnce(new Error('GET /investigations/x/evidence failed with 500'))
      .mockResolvedValue(sample.evidence)
    const { source, emit } = fakeSource({ getEvidence })
    const { result } = renderHook(() => useInvestigation(source))

    await act(async () => result.current.open(sample.investigation.id))
    await act(async () => emit(terminal))

    expect(result.current.state.researchDone).toBe(true)
    expect(result.current.state.finished).toBe(false)
    expect(result.current.state.loadError).toContain('500')

    await act(async () => result.current.retryLoad())
    expect(result.current.state.finished).toBe(true)
    expect(result.current.state.loadError).toBeNull()
    expect(source.submit).not.toHaveBeenCalled()
  })
})

describe('replay', () => {
  it('opens a saved report immediately, and can replay the steps on request', async () => {
    const { source } = fakeSource({ kind: 'replay', getEvents: async () => sample.events })
    const { result } = renderHook(() => useInvestigation(source))

    await act(async () => result.current.open(sample.investigation.id))
    expect(result.current.state.finished).toBe(true)
    expect(result.current.state.events).toHaveLength(sample.events.length)
    expect(source.subscribe).not.toHaveBeenCalled()

    await act(async () => result.current.open(sample.investigation.id, { animate: true }))
    expect(result.current.state.finished).toBe(false)
    expect(source.subscribe).toHaveBeenCalledTimes(1)
  })
})
