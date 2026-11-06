import { useCallback, useEffect, useState } from 'react'
import { UNREACHABLE, type DataSource } from './source'

export type BackendStatus = 'replay' | 'checking' | 'ready' | 'research_disabled' | 'unreachable'

export const REPLAY_UNAVAILABLE =
  'Live investigation isn’t available in this demo yet: the Aletheia backend is still being built. Until then, explore the sample investigations below.'

const REASONS: Record<Exclude<BackendStatus, 'ready'>, string> = {
  replay: REPLAY_UNAVAILABLE,
  checking: 'Checking for the Aletheia backend…',
  research_disabled:
    'The Aletheia backend is running, but research is turned off on it, so claims can’t be investigated. Restart it with ALETHEIA_RESEARCH_ENABLED=true, then retry.',
  unreachable: UNREACHABLE,
}

/** Why the claim field is disabled, or undefined when it can submit. */
export function unavailableReason(status: BackendStatus): string | undefined {
  return status === 'ready' ? undefined : REASONS[status]
}

/** States where checking again can help: the backend may have started or been reconfigured. */
export function canRecheck(status: BackendStatus): boolean {
  return status === 'unreachable' || status === 'research_disabled'
}

export interface BackendStatusState {
  status: BackendStatus
  /** Ask GET /health again. Does nothing in replay mode. */
  recheck: () => void
}

/**
 * Live mode: ask GET /health whether a backend is there and research is on.
 * A queued claim never progresses while research is disabled, so submitting is
 * only offered when research_enabled is true. While the backend is unreachable or
 * research is off, the check reruns on retry, when the window regains focus, and
 * when the browser comes back online.
 */
export function useBackendStatus(source: DataSource): BackendStatusState {
  const [status, setStatus] = useState<BackendStatus>(source.health ? 'checking' : 'replay')
  // Each increment starts a new check; the effect below ignores older responses.
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!source.health) return
    let current = true
    source
      .health()
      .then((health) => {
        if (current) setStatus(health.research_enabled ? 'ready' : 'research_disabled')
      })
      .catch(() => {
        if (current) setStatus('unreachable')
      })
    return () => {
      current = false
    }
  }, [source, attempt])

  const recheck = useCallback(() => {
    if (!source.health) return
    setStatus('checking')
    setAttempt((n) => n + 1)
  }, [source])

  useEffect(() => {
    if (!canRecheck(status)) return
    window.addEventListener('focus', recheck)
    window.addEventListener('online', recheck)
    return () => {
      window.removeEventListener('focus', recheck)
      window.removeEventListener('online', recheck)
    }
  }, [status, recheck])

  return { status, recheck }
}
