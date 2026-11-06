// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { STREAM_UNAVAILABLE, UNREACHABLE, liveSource, type DataSource } from './source'
import type { InvestigationEvent } from './types'
import { HEALTH_TIMEOUT_MS, unavailableReason, useBackendStatus } from './useBackendStatus'

afterEach(() => {
  cleanup() // unmount hooks so their focus/online listeners don't leak between tests
  vi.unstubAllGlobals()
})

function respond(status: number, body: unknown = { detail: 'Sanitized backend message.' }) {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body), { status })))
}

describe('backend error responses', () => {
  it.each([
    [413, 'too long'],
    [422, 'couldn’t accept that claim'],
    [503, 'busy or its database is unavailable'],
    [404, 'wasn’t found'],
    [500, 'returned an error (500)'],
  ])('turns HTTP %i into a plain message', async (status, text) => {
    respond(status)
    await expect(liveSource.submit('A claim', {})).rejects.toThrow(text)
  })

  it('reports an unreachable backend for proxy errors and network failures', async () => {
    respond(502)
    await expect(liveSource.submit('A claim', {})).rejects.toThrow(UNREACHABLE)
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    await expect(liveSource.getInvestigation('x')).rejects.toThrow(UNREACHABLE)
  })
})

/** Minimal EventSource stand-in the test drives by hand. */
/**
 * Mirrors the browser: a named SSE event (`event: <type>`, as the backend sends)
 * reaches only listeners for that name, never onmessage.
 */
class FakeEventSource {
  static CLOSED = 2
  static last: FakeEventSource
  readyState = 0
  onmessage: ((e: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  listeners = new Map<string, ((e: { data: string }) => void)[]>()
  constructor() {
    FakeEventSource.last = this
  }
  addEventListener(type: string, listener: (e: { data: string }) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener])
  }
  close() {
    this.readyState = FakeEventSource.CLOSED
  }
  /** Deliver an event the way the backend does: named after its type. */
  emit(event: Partial<InvestigationEvent> & { type: string }) {
    for (const listener of this.listeners.get(event.type) ?? []) listener({ data: JSON.stringify(event) })
  }
  fail(closed: boolean) {
    this.readyState = closed ? FakeEventSource.CLOSED : 0
    this.onerror?.()
  }
}

describe('progress stream', () => {
  it('receives the named events the backend sends', () => {
    vi.stubGlobal('EventSource', FakeEventSource)
    const onEvent = vi.fn()
    liveSource.subscribe('id', onEvent, () => {})
    FakeEventSource.last.emit({ sequence: 1, type: 'investigation_queued' })
    FakeEventSource.last.emit({ sequence: 2, type: 'stage_started' })
    expect(onEvent.mock.calls.map(([e]) => e.type)).toEqual(['investigation_queued', 'stage_started'])
  })

  it('closes the stream after the terminal event so it does not reconnect and replay', () => {
    vi.stubGlobal('EventSource', FakeEventSource)
    liveSource.subscribe('id', () => {}, () => {})
    FakeEventSource.last.emit({ sequence: 1, type: 'investigation_completed' })
    expect(FakeEventSource.last.readyState).toBe(FakeEventSource.CLOSED)
  })

  it('reports an unavailable stream when it closes before research finishes', () => {
    vi.stubGlobal('EventSource', FakeEventSource)
    const onError = vi.fn()
    liveSource.subscribe('id', () => {}, onError)
    FakeEventSource.last.fail(true) // e.g. GET /events -> 404
    expect(onError).toHaveBeenCalledWith(STREAM_UNAVAILABLE)
  })

  it('treats closing after the terminal event as normal', () => {
    vi.stubGlobal('EventSource', FakeEventSource)
    const onError = vi.fn()
    liveSource.subscribe('id', () => {}, onError)
    FakeEventSource.last.emit({ sequence: 1, type: 'investigation_completed' })
    FakeEventSource.last.fail(true)
    expect(onError).not.toHaveBeenCalled()
  })
})

describe('backend status', () => {
  const withHealth = (health: DataSource['health']): DataSource => ({ ...liveSource, health })

  it.each<[string, DataSource['health'], string]>([
    ['research enabled', async () => ({ status: 'ok', database: 'ok', research_enabled: true }), 'ready'],
    ['research disabled', async () => ({ status: 'ok', database: 'ok', research_enabled: false }), 'research_disabled'],
    ['unreachable', async () => Promise.reject(new Error('down')), 'unreachable'],
  ])('%s', async (_label, health, expected) => {
    const source = withHealth(health)
    const { result } = renderHook(() => useBackendStatus(source))
    expect(result.current.status).toBe('checking')
    await act(async () => {})
    expect(result.current.status).toBe(expected)
  })

  it('stays on replay when the source has no health check', () => {
    const { result } = renderHook(() => useBackendStatus({ ...liveSource, health: undefined }))
    expect(result.current.status).toBe('replay')
  })

  const ENABLED = { status: 'ok', database: 'ok', research_enabled: true }

  it('recovers on retry once the backend starts (backend started after the page)', async () => {
    const health = vi.fn().mockRejectedValueOnce(new Error('down')).mockResolvedValue(ENABLED)
    const source = withHealth(health)
    const { result } = renderHook(() => useBackendStatus(source))
    await act(async () => {})
    expect(result.current.status).toBe('unreachable')

    act(() => result.current.recheck())
    expect(result.current.status).toBe('checking')
    await act(async () => {})
    expect(result.current.status).toBe('ready')
    expect(health).toHaveBeenCalledTimes(2)
  })

  it('rechecks on window focus while unavailable, and stops once ready', async () => {
    const health = vi
      .fn()
      .mockResolvedValueOnce({ ...ENABLED, research_enabled: false })
      .mockResolvedValue(ENABLED)
    const source = withHealth(health)
    const { result } = renderHook(() => useBackendStatus(source))
    await act(async () => {})
    expect(result.current.status).toBe('research_disabled')

    await act(async () => void window.dispatchEvent(new Event('focus')))
    expect(result.current.status).toBe('ready')
    await act(async () => void window.dispatchEvent(new Event('focus')))
    expect(health).toHaveBeenCalledTimes(2)
  })

  describe('stalled health check', () => {
    afterEach(() => vi.useRealTimers())

    it('times out to a retryable state, aborts the request, and recovers on retry', async () => {
      vi.useFakeTimers()
      const signals: AbortSignal[] = []
      const health = vi
        .fn()
        .mockImplementationOnce((signal: AbortSignal) => {
          signals.push(signal)
          return new Promise(() => {}) // connection accepted, response never finishes
        })
        .mockResolvedValue(ENABLED)
      const source = withHealth(health)
      const { result } = renderHook(() => useBackendStatus(source))
      expect(result.current.status).toBe('checking')

      await act(async () => void vi.advanceTimersByTime(HEALTH_TIMEOUT_MS))
      expect(result.current.status).toBe('unreachable')
      expect(signals[0].aborted).toBe(true)

      act(() => result.current.recheck())
      await act(async () => {})
      expect(result.current.status).toBe('ready')
    })

    it('ignores a late answer from an abandoned attempt', async () => {
      vi.useFakeTimers()
      let lateAnswer: (value: unknown) => void = () => {}
      const health = vi
        .fn()
        .mockImplementationOnce(() => new Promise((resolve) => (lateAnswer = resolve)))
        .mockRejectedValue(new Error('down'))
      const source = withHealth(health)
      const { result } = renderHook(() => useBackendStatus(source))
      await act(async () => void vi.advanceTimersByTime(HEALTH_TIMEOUT_MS))
      act(() => result.current.recheck())
      await act(async () => {})
      expect(result.current.status).toBe('unreachable')

      await act(async () => lateAnswer(ENABLED))
      expect(result.current.status).toBe('unreachable')
    })

    it('aborts the pending request when the page unmounts', () => {
      const signals: AbortSignal[] = []
      const source = withHealth((signal) => {
        if (signal) signals.push(signal)
        return new Promise(() => {})
      })
      const { unmount } = renderHook(() => useBackendStatus(source))
      unmount()
      expect(signals[0].aborted).toBe(true)
    })
  })

  it('only allows submitting when research is enabled', () => {
    expect(unavailableReason('ready')).toBeUndefined()
    expect(unavailableReason('research_disabled')).toContain('research is turned off')
    expect(unavailableReason('checking')).toContain('Checking')
  })
})
