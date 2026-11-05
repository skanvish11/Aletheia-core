import { useState, type FormEvent } from 'react'

const MAX_CLAIM_LENGTH = 500

export function ClaimForm({ onSubmit, busy }: { onSubmit: (claim: string) => void; busy: boolean }) {
  const [claim, setClaim] = useState('')
  const trimmed = claim.trim()

  function handle(event: FormEvent) {
    event.preventDefault()
    if (trimmed) onSubmit(trimmed)
  }

  return (
    <form className="claim-form" onSubmit={handle}>
      <label htmlFor="claim">Claim to check</label>
      <textarea
        id="claim"
        value={claim}
        maxLength={MAX_CLAIM_LENGTH}
        rows={3}
        placeholder="One factual claim, e.g. “Product X’s battery lasts three times as long as the previous model.”"
        onChange={(e) => setClaim(e.target.value)}
      />
      <button type="submit" disabled={!trimmed || busy}>
        Investigate
      </button>
    </form>
  )
}
