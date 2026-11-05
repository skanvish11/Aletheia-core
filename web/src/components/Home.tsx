import type { Recording } from '../fixtures'
import { FLAG_LABEL } from '../labels'
import { ClaimForm } from './ClaimForm'
import { Verdict } from './Findings'

const INTRO =
  'Aletheia searches the web for a claim, checks every quotation against the stored source, and tells you whether the evidence supports it, including when a comparison is misleading.'

const REPLAY_UNAVAILABLE =
  'Live investigation isn’t available in this demo yet: the Aletheia backend is still being built. Until then, explore the sample investigations below.'

function SampleRow({ recording, onOpen }: { recording: Recording; onOpen: () => void }) {
  const result = recording.investigation.result
  const flags = [...new Set(result?.findings.flatMap((f) => f.qualification_flags.map((x) => x.type)) ?? [])]
  return (
    <li>
      <button type="button" className="sample" onClick={onOpen}>
        <span className="sample-claim">{recording.investigation.claim}</span>
        <span className="meta">
          {result && <Verdict verdict={result.overall_verdict} />}
          {flags.map((f) => ` · ${FLAG_LABEL[f]}`).join('')}
          {recording.sample && ' · invented sample'}
        </span>
        <span className="sample-open" aria-hidden="true">
          View investigation →
        </span>
      </button>
    </li>
  )
}

interface Props {
  canSubmit: boolean
  submitting: boolean
  error: string | null
  recordings: Recording[]
  onSubmit: (claim: string) => void
  onOpen: (id: string) => void
}

export function Home({ canSubmit, submitting, error, recordings, onSubmit, onOpen }: Props) {
  return (
    <section className="home">
      <h1 className="claim">Check a claim</h1>
      <p className="lead">{INTRO}</p>

      <ClaimForm
        onSubmit={onSubmit}
        submitting={submitting}
        unavailableReason={canSubmit ? undefined : REPLAY_UNAVAILABLE}
      />
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {recordings.length > 0 && (
        <>
          <h2>Sample investigations</h2>
          <ul className="samples">
            {recordings.map((r) => (
              <SampleRow key={r.investigation.id} recording={r} onOpen={() => onOpen(r.investigation.id)} />
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
