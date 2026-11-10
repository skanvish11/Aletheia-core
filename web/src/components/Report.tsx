import type { EvidenceResponse, Investigation, InvestigationEvent, InvestigationResult } from '../api/types'
import { EvidenceIndexContext, buildEvidenceIndex } from '../evidenceIndex'
import { STATUS_LABEL, UNDECIDED_REASON, formatTime, reason } from '../labels'
import { Evidence } from './Evidence'
import { Citations } from './Cite'
import { Correction, DecisionLabel, Findings, Flag, Units } from './Findings'
import { ResearchActivity, ResearchInProgress } from './Progress'

interface Props {
  investigation: Investigation
  evidence: EvidenceResponse | null
  events: InvestigationEvent[]
  researchDone: boolean
  finished: boolean
  loadError: string | null
  replay: boolean
  /** The submission returned an existing investigation rather than starting one. */
  reused: boolean
  onRetry: () => void
  /** Replay only: play the recorded research steps again. */
  onReplay?: () => void
}

function ClaimHeader({
  investigation,
  finished,
  reused,
  onReplay,
}: {
  investigation: Investigation
  finished: boolean
  reused: boolean
  onReplay?: () => void
}) {
  const meta = [
    finished ? STATUS_LABEL[investigation.status] : 'Researching',
    `researched ${formatTime(investigation.started_at ?? investigation.created_at)}`,
    reused ? 'saved result' : null,
    investigation.version > 1 ? `version ${investigation.version}` : null,
  ].filter(Boolean)
  return (
    <header className="claim-header">
      <p className="eyebrow">Claim</p>
      <h1 className="claim">{investigation.claim}</h1>
      <p className="meta">
        {meta.join(' · ')}
        {finished && onReplay && (
          <>
            {' · '}
            <button type="button" className="link-button" onClick={onReplay}>
              Replay research steps
            </button>
          </>
        )}
      </p>
    </header>
  )
}

/**
 * Keeps the decision checkable when the explanation cites nothing, for example a
 * partial result saved with an empty explanation: link the finding's own evidence.
 */
function DecisionEvidence({ result }: { result: InvestigationResult }) {
  const ids = result.finding.evidence_ids
  if (ids.length === 0 || result.explanation.some((unit) => unit.evidence_ids.length > 0)) return null
  return (
    <p>
      {result.explanation.length === 0 ? 'No written explanation was saved. ' : ''}
      The decision rests on this evidence:
      <Citations ids={ids} />
    </p>
  )
}

/** The answer and its essential caveat, before any detail. */
function Conclusion({ investigation, result }: { investigation: Investigation; result: InvestigationResult }) {
  const flags = result.finding.qualification_flags
  return (
    <section className="conclusion" aria-labelledby="conclusion-heading">
      <h2 id="conclusion-heading" className="conclusion-verdict">
        <DecisionLabel decision={result} />
        {flags.length > 0 && <span className="conclusion-but">, with a caveat</span>}
      </h2>
      {result.unable_to_decide_reason && (
        <p className="meta">{UNDECIDED_REASON[result.unable_to_decide_reason]}</p>
      )}
      {investigation.status === 'partial' && (
        <p className="meta">
          Partial result: the run stopped before every step finished
          {reason(investigation.stop_reason) ? ` (${reason(investigation.stop_reason)})` : ''}. The decision comes from
          the steps that completed; Limitations says what was left unfinished.
        </p>
      )}
      {result.almost_correction && <Correction correction={result.almost_correction} />}
      {flags.map((flag, i) => (
        <Flag key={i} flag={flag} />
      ))}
      <div className="summary">
        <Units units={result.explanation} />
        <DecisionEvidence result={result} />
      </div>
    </section>
  )
}

function Limitations({ result }: { result: InvestigationResult }) {
  const items = [...new Set([...result.limitations, ...result.finding.limitations])]
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

export function Report(props: Props) {
  const { investigation, evidence, events, researchDone, finished, loadError, replay, reused, onRetry, onReplay } = props
  const result = finished ? investigation.result : null
  return (
    <EvidenceIndexContext.Provider value={buildEvidenceIndex(evidence)}>
      <article className="report">
        <ClaimHeader investigation={investigation} finished={finished} reused={reused} onReplay={onReplay} />

        {!researchDone && <ResearchInProgress events={events} replay={replay} />}

        {researchDone && !finished && !loadError && (
          <p className="meta conclusion" role="status">
            Research finished. Loading the results…
          </p>
        )}

        {loadError && (
          <section className="conclusion" role="alert">
            <h2>Research finished, but the results didn’t load</h2>
            <p className="meta">{loadError}</p>
            <p className="meta">The investigation itself is saved; retrying only fetches it again.</p>
            <button type="button" className="secondary-button" onClick={onRetry}>
              Retry loading results
            </button>
          </section>
        )}

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
            <h2>No decision</h2>
            <p>{investigation.error.message}</p>
            <p className="meta">A failed investigation is not evidence that the claim is false.</p>
          </section>
        )}

        {result && (
          <>
            <Conclusion investigation={investigation} result={result} />
            <Findings result={result} route={investigation.route} />
            <Limitations result={result} />
            <Evidence />
          </>
        )}

        {finished && <ResearchActivity key={investigation.id} events={events} />}
      </article>
    </EvidenceIndexContext.Provider>
  )
}
