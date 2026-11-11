import { useMemo, useState } from 'react'
import type { EvidenceResponse, Investigation, InvestigationEvent, InvestigationResult } from '../api/types'
import {
  EvidenceIndexContext,
  EvidenceSelectionContext,
  buildEvidenceIndex,
  defaultSelection,
  revealEvidencePane,
  type EvidenceIndex,
} from '../evidenceIndex'
import { STATUS_LABEL, UNDECIDED_REASON, formatDate, reason } from '../labels'
import { Citations } from './Cite'
import { EvidencePane } from './Evidence'
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

function sourceCount(index: EvidenceIndex): number {
  const ids = [...index.values()].filter((e) => e.evidence.admissible).map((e) => e.evidence.assessment.citation.snapshot_id)
  return new Set(ids).size
}

/** One line of run facts in mono: route, sources, date, and anything unusual about the run. */
function RunMeta({
  investigation,
  index,
  finished,
  reused,
  onReplay,
}: {
  investigation: Investigation
  index: EvidenceIndex
  finished: boolean
  reused: boolean
  onReplay?: () => void
}) {
  const sources = sourceCount(index)
  const facts = [
    !finished ? 'researching' : investigation.status !== 'completed' ? STATUS_LABEL[investigation.status].toLowerCase() : null,
    investigation.route,
    finished && investigation.result ? `${sources} source${sources === 1 ? '' : 's'}` : null,
    formatDate(investigation.started_at ?? investigation.created_at),
    reused ? 'saved result' : null,
    investigation.version > 1 ? `version ${investigation.version}` : null,
  ].filter(Boolean)
  return (
    <div className="run-meta">
      <p>{facts.join(' · ')}</p>
      {finished && onReplay && (
        <button type="button" className="secondary-button" onClick={onReplay}>
          Replay research steps
        </button>
      )}
    </div>
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

/** The written answer and its essential caveat or correction, before any detail. */
function Conclusion({ investigation, result }: { investigation: Investigation; result: InvestigationResult }) {
  const flags = result.finding.qualification_flags
  return (
    <section className="conclusion" aria-labelledby="result-label">
      {investigation.status === 'partial' && (
        <p className="notice-box">
          Partial result: the run stopped before every step finished
          {reason(investigation.stop_reason) ? ` (${reason(investigation.stop_reason)})` : ''}. The decision comes from
          the steps that completed; Limitations says what was left unfinished.
        </p>
      )}
      <div className="summary">
        <Units units={result.explanation} />
        <DecisionEvidence result={result} />
      </div>
      {result.almost_correction && <Correction correction={result.almost_correction} />}
      {flags.map((flag, i) => (
        <Flag key={i} flag={flag} />
      ))}
    </section>
  )
}

function Limitations({ result }: { result: InvestigationResult }) {
  const items = [...new Set([...result.limitations, ...result.finding.limitations])]
  if (items.length === 0) return null
  return (
    <section className="section" aria-labelledby="limitations-heading">
      <h2 id="limitations-heading" className="section-label">
        Limitations
      </h2>
      <ul className="limitations">
        {items.map((l, i) => (
          <li key={i}>{l}</li>
        ))}
      </ul>
    </section>
  )
}

function citedIds(result: InvestigationResult | null): string[] {
  if (!result) return []
  return [
    ...result.explanation.flatMap((u) => u.evidence_ids),
    ...result.finding.qualification_flags.flatMap((f) => f.evidence_ids),
    ...result.finding.evidence_ids,
  ]
}

export function Report(props: Props) {
  const { investigation, evidence, events, researchDone, finished, loadError, replay, reused, onRetry, onReplay } = props
  const result = finished ? investigation.result : null
  const index = useMemo(() => buildEvidenceIndex(evidence), [evidence])
  const [choice, setChoice] = useState<{ investigation: string; id: string } | null>(null)
  const selected =
    choice?.investigation === investigation.id && index.has(choice.id)
      ? choice.id
      : defaultSelection(index, citedIds(result))
  const selection = useMemo(
    () => ({
      selected,
      select: (id: string, reveal = false) => {
        setChoice({ investigation: investigation.id, id })
        if (reveal) revealEvidencePane()
      },
    }),
    [selected, investigation.id],
  )

  return (
    <EvidenceIndexContext.Provider value={index}>
      <EvidenceSelectionContext.Provider value={selection}>
        <article className="report">
          <header className="report-head">
            <p className="section-label">Claim</p>
            <h1 className="claim">{investigation.claim}</h1>
            {result && (
              <>
                <h2 id="result-label" className="result-label">
                  <DecisionLabel decision={result} />
                  {result.finding.qualification_flags.length > 0 && (
                    <span className="result-qualifier">, with a caveat</span>
                  )}
                </h2>
                {result.unable_to_decide_reason && (
                  <p className="result-reason">{UNDECIDED_REASON[result.unable_to_decide_reason]}</p>
                )}
              </>
            )}
            <RunMeta
              investigation={investigation}
              index={index}
              finished={finished}
              reused={reused}
              onReplay={onReplay}
            />
          </header>

          {!researchDone && <ResearchInProgress events={events} replay={replay} />}

          {researchDone && !finished && !loadError && (
            <p className="meta status-line" role="status">
              Research finished. Loading the results…
            </p>
          )}

          {loadError && (
            <section className="outcome" role="alert">
              <h2>Research finished, but the results didn’t load</h2>
              <p className="meta">{loadError}</p>
              <p className="meta">The investigation itself is saved; retrying only fetches it again.</p>
              <button type="button" className="secondary-button" onClick={onRetry}>
                Retry loading results
              </button>
            </section>
          )}

          {finished && investigation.clarification_questions && (
            <section className="outcome">
              <h2>Needs clarification before researching</h2>
              <ul>
                {investigation.clarification_questions.map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ul>
            </section>
          )}

          {finished && investigation.error && (
            <section className="outcome" role="alert">
              <h2>No decision</h2>
              <p>{investigation.error.message}</p>
              <p className="meta">A failed investigation is not evidence that the claim is false.</p>
            </section>
          )}

          {(result || (finished && events.length > 0)) && (
            <div className="report-body">
              <div className="report-main">
                {result && (
                  <>
                    <Conclusion investigation={investigation} result={result} />
                    <Findings result={result} route={investigation.route} />
                    <Limitations result={result} />
                  </>
                )}
                {finished && <ResearchActivity key={investigation.id} events={events} />}
              </div>
              {result && <EvidencePane />}
            </div>
          )}
        </article>
      </EvidenceSelectionContext.Provider>
    </EvidenceIndexContext.Provider>
  )
}
