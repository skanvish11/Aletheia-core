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
  /** A claim was submitted and the backend hasn't returned an investigation yet. */
  submitting: boolean
  /** The terminal event arrived: research is over, whether or not the report has loaded. */
  researchDone: boolean
  /** The final investigation and evidence are loaded. */
  finished: boolean
  /** Research finished but loading the report failed; retryLoad() tries again. */
  loadError: string | null
  /** Submitting, opening or following progress failed. */
  error: string | null
  /**
   * True when submitting returned an existing investigation of the same claim instead
   * of starting research. Only the submit response defines this; a plain GET always
   * reports reused, so the investigation's own field is not used for display.
   */
  reused: boolean
}

const EMPTY: InvestigationState = {
  investigation: null,
  evidence: null,
  events: [],
  submitting: false,
  researchDone: false,
  finished: false,
  loadError: null,
  error: null,
  reused: false,
}

export interface OpenOptions {
  /** Play progress events as they arrive. Replay defaults to false (show the saved report at once). */
  animate?: boolean
}

/** Insert an event, dropping redelivered sequences (README section 9: clients deduplicate). */
function addEvent(events: InvestigationEvent[], event: InvestigationEvent): InvestigationEvent[] {
  if (events.some((e) => e.sequence === event.sequence)) return events
  return [...events, event].sort((a, b) => a.sequence - b.sequence)
}

function message(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

export function useInvestigation(source: DataSource) {
  const [state, setState] = useState<InvestigationState>(EMPTY)
  const unsubscribe = useRef<(() => void) | null>(null)
  // Every open/submit/close starts a new session. Async results from an older
  // session (a slow response, a superseded submission) are ignored.
  const session = useRef(0)
  const currentId = useRef<string | null>(null)
  const submitting = useRef(false)

  const stop = useCallback(() => {
    unsubscribe.current?.()
    unsubscribe.current = null
  }, [])

  useEffect(() => stop, [stop])

  const isCurrent = (token: number) => session.current === token

  const loadFinal = useCallback(
    async (id: string, token: number) => {
      setState((s) => ({ ...s, loadError: null }))
      try {
        const [investigation, evidence] = await Promise.all([
          source.getInvestigation(id),
          source.getEvidence(id),
        ])
        if (!isCurrent(token)) return
        setState((s) => ({ ...s, investigation, evidence, finished: true }))
      } catch (err) {
        if (isCurrent(token)) setState((s) => ({ ...s, loadError: message(err, 'Could not load the results.') }))
      }
    },
    [source],
  )

  const follow = useCallback(
    async (id: string, token: number, animate: boolean) => {
      stop()
      currentId.current = id
      try {
        const investigation = await source.getInvestigation(id)
        if (!isCurrent(token)) return
        // Hide the final result until research is over, so the page reads in order.
        setState((s) => ({ ...s, investigation: { ...investigation, result: null } }))

        if (!animate && source.getEvents) {
          const events = await source.getEvents(id)
          if (!isCurrent(token)) return
          setState((s) => ({ ...s, events, researchDone: true }))
          await loadFinal(id, token)
          return
        }
      } catch (err) {
        if (isCurrent(token)) setState((s) => ({ ...s, error: message(err, 'Could not load the investigation.') }))
        return
      }

      unsubscribe.current = source.subscribe(
        id,
        (event) => {
          if (!isCurrent(token)) return
          setState((s) => ({ ...s, events: addEvent(s.events, event) }))
          if (TERMINAL_EVENTS.has(event.type)) {
            stop()
            setState((s) => ({ ...s, researchDone: true }))
            void loadFinal(id, token)
          }
        },
        (msg) => {
          if (isCurrent(token)) setState((s) => ({ ...s, error: msg }))
        },
      )
    },
    [source, stop, loadFinal],
  )

  const open = useCallback(
    async (id: string, options: OpenOptions = {}) => {
      const token = ++session.current
      submitting.current = false
      setState(EMPTY)
      await follow(id, token, options.animate ?? source.kind === 'live')
    },
    [source, follow],
  )

  const submit = useCallback(
    async (claim: string, context: ClaimContext) => {
      if (submitting.current) return // one submission at a time
      submitting.current = true
      const token = ++session.current
      stop()
      setState({ ...EMPTY, submitting: true })
      try {
        const created = await source.submit(claim, context)
        if (!isCurrent(token)) return // the user left or submitted again
        setState((s) => ({ ...s, submitting: false, reused: created.reused }))
        await follow(created.id, token, true)
      } catch (err) {
        if (isCurrent(token)) setState({ ...EMPTY, error: message(err, 'Could not submit the claim.') })
      } finally {
        if (isCurrent(token)) submitting.current = false
      }
    },
    [source, stop, follow],
  )

  /** Retry loading the report after research finished; never starts a new investigation. */
  const retryLoad = useCallback(() => {
    const id = currentId.current
    if (id) void loadFinal(id, session.current)
  }, [loadFinal])

  /** Leave the current investigation; pending responses for it are ignored. */
  const close = useCallback(() => {
    session.current++
    submitting.current = false
    stop()
    currentId.current = null
    setState(EMPTY)
  }, [stop])

  return { state, open, submit, retryLoad, close }
}
