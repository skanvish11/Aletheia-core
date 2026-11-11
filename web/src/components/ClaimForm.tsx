import { useId, useState, type FormEvent } from 'react'

const MAX_CLAIM_LENGTH = 500

interface Props {
  onSubmit: (claim: string) => void
  /** A submission is in flight: keep the text, block resubmission. */
  submitting: boolean
  /** Investigation isn't available here (replay-only page). */
  unavailableReason?: string
  /** Offered while unavailable when checking the backend again could help. */
  onRetry?: () => void
}

export function ClaimForm({ onSubmit, submitting, unavailableReason, onRetry }: Props) {
  const [claim, setClaim] = useState('')
  const noteId = useId()
  const trimmed = claim.trim()
  const unavailable = Boolean(unavailableReason)

  function handle(event: FormEvent) {
    event.preventDefault()
    if (trimmed && !submitting && !unavailable) onSubmit(trimmed)
  }

  return (
    <form className="claim-form" onSubmit={handle} aria-busy={submitting}>
      <label htmlFor="claim">Claim to check</label>
      <textarea
        id="claim"
        value={claim}
        maxLength={MAX_CLAIM_LENGTH}
        rows={3}
        disabled={unavailable}
        aria-describedby={unavailable ? noteId : undefined}
        placeholder="One factual claim, e.g. “Model X scores 90% on MMLU, ahead of Model Y.”"
        onChange={(e) => setClaim(e.target.value)}
      />
      <div className="claim-form-actions">
        <button type="submit" disabled={unavailable || submitting || !trimmed}>
          {submitting ? 'Starting investigation…' : 'Investigate'}
        </button>
        {unavailable && (
          <p id={noteId} className="meta claim-form-note">
            {unavailableReason}
            {onRetry && (
              <>
                {' '}
                <button type="button" className="link-button" onClick={onRetry}>
                  Retry connection
                </button>
              </>
            )}
          </p>
        )}
      </div>
    </form>
  )
}
