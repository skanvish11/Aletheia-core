import { useEffect, useState } from 'react'
import { UNREACHABLE, type DataSource } from './source'

export type BackendStatus = 'replay' | 'checking' | 'ready' | 'research_disabled' | 'unreachable'

export const REPLAY_UNAVAILABLE =
  'Live investigation isn’t available in this demo yet: the Aletheia backend is still being built. Until then, explore the sample investigations below.'

const REASONS: Record<Exclude<BackendStatus, 'ready'>, string> = {
  replay: REPLAY_UNAVAILABLE,
  checking: 'Checking for the Aletheia backend…',
  research_disabled:
    'The Aletheia backend is running, but research isn’t enabled on it yet, so claims can’t be investigated. This will turn on once the research pipeline is installed.',
  unreachable: UNREACHABLE,
}

/** Why the claim field is disabled, or undefined when it can submit. */
export function unavailableReason(status: BackendStatus): string | undefined {
  return status === 'ready' ? undefined : REASONS[status]
}

/**
 * Live mode: ask GET /health once whether a backend is there and research is on.
 * A queued claim never progresses while research is disabled, so submitting is
 * only offered when research_enabled is true.
 */
export function useBackendStatus(source: DataSource): BackendStatus {
  const [status, setStatus] = useState<BackendStatus>(source.health ? 'checking' : 'replay')

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
  }, [source])

  return status
}
