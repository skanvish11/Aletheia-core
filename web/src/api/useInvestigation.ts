import { useCallback, useEffect, useRef, useState } from 'react'
import type { DataSource } from './source'
import {
  TERMINAL_EVENTS,
  type ClaimContext,
  type EvidenceResponse,
  type Investigation,
  type InvestigationEvent,
} from './types'

export interface InvestigationState {
  investigation: Investigation | null
  evidence: EvidenceResponse | null
  events: InvestigationEvent[]
  /** True once the terminal event has arrived and the final record is loaded. */
  finished: boolean
  error: string | null
}

const EMPTY: InvestigationState = {
  investigation: null,
  evidence: null,
  events: [],
  finished: false,
  error: null,
}

/** Insert an event, dropping redelivered sequences (README section 9: clients deduplicate). */
function addEvent(events: InvestigationEvent[], event: InvestigationEvent): InvestigationEvent[] {
  if (events.some((e) => e.sequence === event.sequence)) return events
  return [...events, event].sort((a, b) => a.sequence - b.sequence)
}

export function useInvestigation(source: DataSource) {
  const [state, setState] = useState<InvestigationState>(EMPTY)
  const unsubscribe = useRef<(() => void) | null>(null)
  // Guards against a slow response from a previous investigation overwriting the current one.
  const currentId = useRef<string | null>(null)

  const stop = useCallback(() => {
    unsubscribe.current?.()
    unsubscribe.current = null
  }, [])

  useEffect(() => stop, [stop])

  const fail = useCallback((id: string, message: string) => {
    if (currentId.current === id) setState((s) => ({ ...s, error: message }))
  }, [])

  const loadFinal = useCallback(
    async (id: string) => {
      try {
        const [investigation, evidence] = await Promise.all([
          source.getInvestigation(id),
          source.getEvidence(id),
        ])
        if (currentId.current !== id) return
        setState((s) => ({ ...s, investigation, evidence, finished: true }))
      } catch (err) {
        fail(id, err instanceof Error ? err.message : 'Could not load the final result.')
      }
    },
    [source, fail],
  )

  const open = useCallback(
    async (id: string) => {
      stop()
      currentId.current = id
      setState(EMPTY)
      try {
        const investigation = await source.getInvestigation(id)
        if (currentId.current !== id) return
        // Hide the final result until progress has played through, so the page
        // reads in the order the research happened.
        setState((s) => ({ ...s, investigation: { ...investigation, result: null } }))
      } catch (err) {
        fail(id, err instanceof Error ? err.message : 'Could not load the investigation.')
        return
      }
      unsubscribe.current = source.subscribe(
        id,
        (event) => {
          if (currentId.current !== id) return
          setState((s) => ({ ...s, events: addEvent(s.events, event) }))
          if (TERMINAL_EVENTS.has(event.type)) {
            stop()
            void loadFinal(id)
          }
        },
        (message) => fail(id, message),
      )
    },
    [source, stop, fail, loadFinal],
  )

  const submit = useCallback(
    async (claim: string, context: ClaimContext) => {
      try {
        const created = await source.submit(claim, context)
        await open(created.id)
      } catch (err) {
        setState({ ...EMPTY, error: err instanceof Error ? err.message : 'Could not submit the claim.' })
      }
    },
    [source, open],
  )

  return { state, open, submit }
}
