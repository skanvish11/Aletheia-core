import {
  EVENT_TYPES,
  TERMINAL_EVENTS,
  type ClaimContext,
  type EvidenceResponse,
  type HealthStatus,
  type Investigation,
  type InvestigationEvent,
} from './types'
import { RECORDINGS, type Recording } from '../fixtures'

export interface Unsubscribe {
  (): void
}

/**
 * Where the UI gets investigations from.
 * - live: the local backend (README section 9), localhost only.
 * - replay: exported recordings bundled with the client; never calls a backend.
 */
export interface DataSource {
  kind: 'live' | 'replay'
  canSubmit: boolean
  recordings: Recording[]
  submit(claim: string, context: ClaimContext): Promise<Investigation>
  getInvestigation(id: string): Promise<Investigation>
  getEvidence(id: string): Promise<EvidenceResponse>
  /** All stored events at once. Replay only: lets a saved report open without animation. */
  getEvents?(id: string): Promise<InvestigationEvent[]>
  /** Live only: backend reachability and whether research is enabled. */
  health?(): Promise<HealthStatus>
  subscribe(
    id: string,
    onEvent: (event: InvestigationEvent) => void,
    onError: (message: string) => void,
  ): Unsubscribe
}

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

export const UNREACHABLE =
  'Couldn’t reach the Aletheia backend. Start it on this computer (see the README), then try again.'

/** Shown when the progress stream ends before research does (e.g. the backend has no /events yet). */
export const STREAM_UNAVAILABLE =
  'Live progress isn’t available from this backend yet. Your claim was saved; check back once research is enabled.'

/** Plain-language messages for statuses the backend documents (docs/backend-foundation.md). */
const STATUS_MESSAGES: Record<number, string> = {
  404: 'That investigation wasn’t found.',
  413: 'The claim and context are too long to submit. Shorten them and try again.',
  422: 'The backend couldn’t accept that claim. Check that it isn’t empty and is within the length limits.',
  503: 'The backend is busy or its database is unavailable. Try again in a moment.',
}

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, init)
  } catch {
    throw new Error(UNREACHABLE)
  }
  // The dev proxy answers 502/504 when nothing is listening behind it.
  if (response.status === 502 || response.status === 504) throw new Error(UNREACHABLE)
  if (!response.ok) {
    // The backend's own `detail` is sanitized (never echoes input), but our wording is friendlier.
    throw new Error(STATUS_MESSAGES[response.status] ?? `The backend returned an error (${response.status}).`)
  }
  return (await response.json()) as T
}

export const liveSource: DataSource = {
  kind: 'live',
  canSubmit: true,
  recordings: [],
  submit: (claim, context) =>
    getJson<Investigation>('/investigations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ claim, context }),
    }),
  getInvestigation: (id) => getJson<Investigation>(`/investigations/${id}`),
  getEvidence: (id) => getJson<EvidenceResponse>(`/investigations/${id}/evidence`),
  health: () => getJson<HealthStatus>('/health'),
  subscribe(id, onEvent, onError) {
    // EventSource resends Last-Event-ID on reconnect; the server replays from there.
    const stream = new EventSource(`${API_BASE}/investigations/${id}/events`)
    let finished = false
    const receive = (message: MessageEvent<string>) => {
      try {
        const event = JSON.parse(message.data) as InvestigationEvent
        if (TERMINAL_EVENTS.has(event.type)) {
          finished = true
          // The server ends the response after the terminal event; without closing,
          // EventSource would reconnect and replay the whole run.
          stream.close()
        }
        onEvent(event)
      } catch {
        onError('Received a progress event the client could not read.')
      }
    }
    // The backend names every event (`event: <type>`), and EventSource only routes
    // unnamed events to onmessage, so listen for each name.
    for (const type of EVENT_TYPES) stream.addEventListener(type, receive)
    stream.onmessage = receive
    stream.onerror = () => {
      if (stream.readyState === EventSource.CLOSED) {
        // Closing after the terminal event is normal. Closing before it means the
        // stream is unavailable (a 404 or non-SSE response never reconnects), so say
        // so instead of leaving the page on "Researching" forever.
        if (!finished) onError(STREAM_UNAVAILABLE)
        return
      }
      onError('Lost the progress stream; the browser is reconnecting.')
    }
    return () => stream.close()
  },
}

/** Delay between replayed events. Replay shows original timestamps, so pacing is cosmetic. */
const REPLAY_STEP_MS = 350

function findRecording(id: string): Recording {
  const recording = RECORDINGS.find((r) => r.investigation.id === id)
  if (!recording) throw new Error(`No recording with id ${id}`)
  return recording
}

export const replaySource: DataSource = {
  kind: 'replay',
  canSubmit: false,
  recordings: RECORDINGS,
  submit: () => Promise.reject(new Error('Recorded investigations cannot start new research.')),
  getInvestigation: async (id) => findRecording(id).investigation,
  getEvidence: async (id) => findRecording(id).evidence,
  getEvents: async (id) => findRecording(id).events,
  subscribe(id, onEvent) {
    const { events } = findRecording(id)
    const timers = events.map((event, index) =>
      window.setTimeout(() => onEvent(event), (index + 1) * REPLAY_STEP_MS),
    )
    return () => timers.forEach((timer) => window.clearTimeout(timer))
  },
}

export const dataSource: DataSource =
  import.meta.env.VITE_DATA_SOURCE === 'live' ? liveSource : replaySource
