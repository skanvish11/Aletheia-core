import type { Recording } from '../fixtures'
import { FLAG_LABEL } from '../labels'
import { ClaimForm } from './ClaimForm'
import { DecisionLabel } from './Findings'

const INTRO =
  'Aletheia searches the web for a claim, checks every quotation against the stored source, and tells you whether it’s true, false or almost, including when a comparison is misleading.'

function SampleRow({ recording, onOpen }: { recording: Recording; onOpen: () => void }) {
  const result = recording.investigation.result
  const flags = [...new Set(result?.finding.qualification_flags.map((x) => x.type) ?? [])]
  return (
    <li>
      <button type="button" className="sample" onClick={onOpen}>
        <span className="sample-claim">{recording.investigation.claim}</span>
        <span className="meta">
          {result && <DecisionLabel decision={result} />}
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
  /** Why claims can't be submitted right now; undefined when they can. */
  unavailableReason?: string
  submitting: boolean
  error: string | null
  recordings: Recording[]
  onSubmit: (claim: string) => void
  onOpen: (id: string) => void
}

export function Home({ unavailableReason, submitting, error, recordings, onSubmit, onOpen }: Props) {
  return (
    <section className="home">
      <h1 className="claim">Check a claim</h1>
      <p className="lead">{INTRO}</p>

      <ClaimForm
        onSubmit={onSubmit}
        submitting={submitting}
        unavailableReason={unavailableReason}
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
