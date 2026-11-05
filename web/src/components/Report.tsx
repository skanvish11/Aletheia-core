import type { EvidenceResponse, Investigation, InvestigationEvent, InvestigationResult } from '../api/types'
import { EvidenceIndexContext, buildEvidenceIndex } from '../evidenceIndex'
import { STATUS_LABEL, formatTime } from '../labels'
import { Evidence } from './Evidence'
import { Findings, Flag, Units, Verdict } from './Findings'
import { ResearchActivity, ResearchInProgress } from './Progress'

interface Props {
  investigation: Investigation
  evidence: EvidenceResponse | null
  events: InvestigationEvent[]
  finished: boolean
  replay: boolean
}

function ClaimHeader({ investigation, finished }: { investigation: Investigation; finished: boolean }) {
  const meta = [
    finished ? STATUS_LABEL[investigation.status] : 'Researching',
    `researched ${formatTime(investigation.started_at ?? investigation.created_at)}`,
    investigation.reused ? 'saved result' : null,
    investigation.version > 1 ? `version ${investigation.version}` : null,
  ].filter(Boolean)
  return (
    <header className="claim-header">
      <p className="eyebrow">Claim</p>
      <h1 className="claim">{investigation.claim}</h1>
      <p className="meta">{meta.join(' · ')}</p>
    </header>
  )
}

/** The answer and its essential caveat, before any detail. */
function Conclusion({ result }: { result: InvestigationResult }) {
  const flags = result.findings.flatMap((f) => f.qualification_flags)
  return (
    <section className="conclusion" aria-labelledby="conclusion-heading">
      <h2 id="conclusion-heading" className="conclusion-verdict">
        <Verdict verdict={result.overall_verdict} />
        {flags.length > 0 && <span className="conclusion-but">, with a caveat</span>}
      </h2>
      {flags.map((flag, i) => (
        <Flag key={i} flag={flag} />
      ))}
      <div className="summary">
        <Units units={result.summary} />
      </div>
    </section>
  )
}

function Limitations({ result }: { result: InvestigationResult }) {
  const items = [...result.conflicts, ...result.limitations]
  if (items.length === 0) return null
  return (
    <section className="section" aria-labelledby="limitations-heading">
      <h2 id="limitations-heading">Limitations</h2>
      <ul className="limitations">
        {items.map((l, i) => (
          <li key={i}>{l}</li>
        ))}
      </ul>
    </section>
  )
}

export function Report({ investigation, evidence, events, finished, replay }: Props) {
  const result = finished ? investigation.result : null
  return (
    <EvidenceIndexContext.Provider value={buildEvidenceIndex(evidence)}>
      <article className="report">
        <ClaimHeader investigation={investigation} finished={finished} />

        {!finished && <ResearchInProgress events={events} replay={replay} />}

        {finished && investigation.clarification_questions && (
          <section className="conclusion">
            <h2>Needs clarification before researching</h2>
            <ul>
              {investigation.clarification_questions.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ul>
          </section>
        )}

        {finished && investigation.error && (
          <section className="conclusion" role="alert">
            <h2>No verdict</h2>
            <p>{investigation.error.message}</p>
            <p className="meta">A failed investigation is not evidence that the claim is false.</p>
          </section>
        )}

        {result && (
          <>
            <Conclusion result={result} />
            <Findings findings={result.findings} />
            <Limitations result={result} />
            <Evidence />
          </>
        )}

        {finished && <ResearchActivity key={investigation.id} events={events} />}
      </article>
    </EvidenceIndexContext.Provider>
  )
}
