import type { Recording } from '../fixtures'
import { FLAG_LABEL } from '../labels'
import { ClaimForm } from './ClaimForm'
import { Verdict } from './Findings'

const INTRO =
  'Aletheia searches the web for a claim, checks every quotation against the stored source, and tells you whether the evidence supports it, including when a comparison is misleading.'

export function LiveHome({ onSubmit, error }: { onSubmit: (claim: string) => void; error: string | null }) {
  return (
    <section className="home">
      <h1 className="claim">Check a claim</h1>
      <p className="lead">{INTRO}</p>
      <ClaimForm onSubmit={onSubmit} busy={false} />
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  )
}

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

export function ReplayHome({ recordings, onOpen }: { recordings: Recording[]; onOpen: (id: string) => void }) {
  return (
    <section className="home">
      <h1 className="claim">See how Aletheia checks a claim</h1>
      <p className="lead">{INTRO}</p>

      <h2>Browse sample investigations</h2>
      <ul className="samples">
        {recordings.map((r) => (
          <SampleRow key={r.investigation.id} recording={r} onOpen={() => onOpen(r.investigation.id)} />
        ))}
      </ul>

      <h2>Investigate your own claim</h2>
      <p>
        This page only replays saved investigations. To check a new claim, run the Aletheia backend and this client on
        your own computer, then start the client in live mode:
      </p>
      <pre>
        <code>VITE_DATA_SOURCE=live npm run dev</code>
      </pre>
    </section>
  )
}
