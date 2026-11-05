import type {
  AssertionFinding,
  EvidenceResponse,
  ExplanationUnit,
  InvestigationResult,
} from '../api/types'
import { DIMENSION_LABEL, FLAG_LABEL, VERDICT_LABEL } from '../labels'

/** Citation numbers follow the order of assessments in the evidence response. */
function citationNumbers(evidence: EvidenceResponse | null): Map<string, number> {
  return new Map((evidence?.assessments ?? []).map((a, i) => [a.id, i + 1]))
}

function Citations({ ids, numbers }: { ids: string[]; numbers: Map<string, number> }) {
  return (
    <>
      {ids.map((id) => (
        <a key={id} className="cite" href={`#evidence-${id}`} title={`Evidence ${id}`}>
          [{numbers.get(id) ?? '?'}]
        </a>
      ))}
    </>
  )
}

function Units({ units, numbers }: { units: ExplanationUnit[]; numbers: Map<string, number> }) {
  return (
    <>
      {units.map((unit, i) => (
        <p key={i}>
          {unit.text} <Citations ids={unit.evidence_ids} numbers={numbers} />
        </p>
      ))}
    </>
  )
}

export function VerdictBadge({ verdict }: { verdict: AssertionFinding['verdict'] }) {
  return <span className={`badge verdict-${verdict}`}>{VERDICT_LABEL[verdict]}</span>
}

function FindingCard({ finding, numbers }: { finding: AssertionFinding; numbers: Map<string, number> }) {
  return (
    <article className="card finding">
      <header className="finding-head">
        <VerdictBadge verdict={finding.verdict} />
        <span className="muted">{finding.route === 'deep' ? 'Deeper research' : 'Quick check'}</span>
      </header>
      <p className="scoped">{finding.scoped_text}</p>

      {finding.qualification_flags.map((flag, i) => (
        <div key={i} className="flag" role="note">
          <strong>
            {FLAG_LABEL[flag.type]} · {DIMENSION_LABEL[flag.dimension]}
          </strong>
          <p>
            {flag.explanation} <Citations ids={flag.evidence_ids} numbers={numbers} />
          </p>
        </div>
      ))}
      {finding.qualification_check === 'unknown' && (
        <p className="muted">Comparison and scope were not assessed for this finding.</p>
      )}

      <Units units={finding.explanation} numbers={numbers} />

      {finding.limitations.length > 0 && (
        <ul className="limitations">
          {finding.limitations.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
      )}
    </article>
  )
}

export function Findings({
  result,
  evidence,
}: {
  result: InvestigationResult
  evidence: EvidenceResponse | null
}) {
  const numbers = citationNumbers(evidence)
  return (
    <section aria-labelledby="findings-heading">
      <h2 id="findings-heading">Findings</h2>
      <div className="summary">
        <Units units={result.summary} numbers={numbers} />
      </div>
      {result.findings
        .slice()
        .sort((a, b) => a.position - b.position)
        .map((finding) => (
          <FindingCard key={finding.assertion_id} finding={finding} numbers={numbers} />
        ))}
      {result.conflicts.length + result.limitations.length > 0 && (
        <div className="card">
          <h3>Limitations</h3>
          <ul className="limitations">
            {[...result.conflicts, ...result.limitations].map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
