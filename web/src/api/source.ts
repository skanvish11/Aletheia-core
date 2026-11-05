import type {
  ClaimContext,
  EvidenceResponse,
  Investigation,
  InvestigationEvent,
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
  subscribe(
    id: string,
    onEvent: (event: InvestigationEvent) => void,
    onError: (message: string) => void,
  ): Unsubscribe
}

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  if (!response.ok) {
    throw new Error(`${init?.method ?? 'GET'} ${path} failed with ${response.status}`)
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
  subscribe(id, onEvent, onError) {
    // EventSource resends Last-Event-ID on reconnect; the server replays from there.
    const stream = new EventSource(`${API_BASE}/investigations/${id}/events`)
    stream.onmessage = (message) => {
      try {
        onEvent(JSON.parse(message.data) as InvestigationEvent)
      } catch {
        onError('Received a progress event the client could not read.')
      }
    }
    stream.onerror = () => {
      // The server closes the stream after the terminal event, which also fires onerror.
      if (stream.readyState === EventSource.CLOSED) return
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
