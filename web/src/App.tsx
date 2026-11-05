import { useEffect } from 'react'
import { dataSource } from './api/source'
import { useInvestigation } from './api/useInvestigation'
import { ClaimForm } from './components/ClaimForm'
import { Evidence } from './components/Evidence'
import { Findings, VerdictBadge } from './components/Findings'
import { Progress } from './components/Progress'
import type { FlagType, InvestigationResult } from './api/types'
import { FLAG_LABEL, STATUS_LABEL, formatTime } from './labels'

const replay = dataSource.kind === 'replay'

/** Distinct flag types across all findings, for the headline next to the overall verdict. */
function flagTypes(result: InvestigationResult): FlagType[] {
  return [...new Set(result.findings.flatMap((f) => f.qualification_flags.map((flag) => flag.type)))]
}

export default function App() {
  const { state, open, submit } = useInvestigation(dataSource)
  const { investigation, evidence, events, finished, error } = state
  const recording = dataSource.recordings.find((r) => r.investigation.id === investigation?.id)

  // In replay mode, open the first recording so the page is never empty.
  useEffect(() => {
    const first = dataSource.recordings[0]
    if (replay && first) void open(first.investigation.id)
  }, [open])

  const result = finished ? investigation?.result : null

  return (
    <main>
      <header className="site-head">
        <h1>Aletheia</h1>
        <p className="muted">Evidence-first claim investigation</p>
      </header>

      {replay && (
        <div className="banner" role="status">
          <strong>Recorded investigation.</strong> This page replays a saved run and cannot start new research.
          {recording?.sample && ' The data below is invented sample data for development, not a real investigation.'}
        </div>
      )}

      {replay ? (
        dataSource.recordings.length > 1 && (
          <nav className="recordings" aria-label="Recorded investigations">
            {dataSource.recordings.map((r) => (
              <button key={r.investigation.id} type="button" onClick={() => void open(r.investigation.id)}>
                {r.label}
              </button>
            ))}
          </nav>
        )
      ) : (
        <ClaimForm busy={!!investigation && !finished && !error} onSubmit={(claim) => void submit(claim, {})} />
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {investigation && (
        <>
          <section className="card claim" aria-label="Claim">
            <p className="claim-text">“{investigation.claim}”</p>
            <p className="muted">
              {finished ? STATUS_LABEL[investigation.status] : 'Researching'}
              {investigation.reused && ' · saved result'}
              {investigation.version > 1 && ` · version ${investigation.version}`}
              {' · researched '}
              {formatTime(investigation.started_at ?? investigation.created_at)}
            </p>
            {result && (
              <p className="overall">
                Overall: <VerdictBadge verdict={result.overall_verdict} />
                {flagTypes(result).map((type) => (
                  <a key={type} className="badge flag-badge" href="#findings-heading">
                    {FLAG_LABEL[type]}
                  </a>
                ))}
              </p>
            )}
          </section>

          <div className="columns">
            <Progress events={events} replay={replay} />
            <div className="results">
              {result && <Findings result={result} evidence={evidence} />}
              {finished && investigation.clarification_questions && (
                <section className="card">
                  <h2>Needs clarification</h2>
                  <ul>
                    {investigation.clarification_questions.map((q, i) => (
                      <li key={i}>{q}</li>
                    ))}
                  </ul>
                </section>
              )}
              {finished && investigation.error && (
                <p className="error" role="alert">
                  No verdict: {investigation.error.message}
                </p>
              )}
              {result && evidence && <Evidence evidence={evidence} />}
            </div>
          </div>
        </>
      )}
    </main>
  )
}
