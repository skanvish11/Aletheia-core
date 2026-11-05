import type { AssertionFinding, ExplanationUnit, QualificationFlag } from '../api/types'
import { DIMENSION_LABEL, FLAG_LABEL, VERDICT_LABEL } from '../labels'
import { Citations } from './Cite'

export function Units({ units }: { units: ExplanationUnit[] }) {
  return (
    <>
      {units.map((unit, i) => (
        <p key={i}>
          {unit.text}
          <Citations ids={unit.evidence_ids} />
        </p>
      ))}
    </>
  )
}

export function Verdict({ verdict }: { verdict: AssertionFinding['verdict'] }) {
  return <span className={`verdict verdict-${verdict}`}>{VERDICT_LABEL[verdict]}</span>
}

/** A qualification: the one tinted surface on the page. */
export function Flag({ flag }: { flag: QualificationFlag }) {
  return (
    <div className="flag" role="note">
      <p className="flag-title">
        {FLAG_LABEL[flag.type]} <span className="flag-dimension">· {DIMENSION_LABEL[flag.dimension]}</span>
      </p>
      <p>
        {flag.explanation}
        <Citations ids={flag.evidence_ids} />
      </p>
    </div>
  )
}

/**
 * One assertion's finding. With a single assertion the conclusion above already
 * shows its verdict and flags, so they are repeated here only for compound claims.
 */
function Finding({ finding, compound }: { finding: AssertionFinding; compound: boolean }) {
  const route = finding.route === 'deep' ? 'Deeper research' : 'Quick check'
  return (
    <article className="finding">
      {compound ? (
        <p className="finding-head">
          <span className="meta">Assertion {finding.position} · </span>
          <Verdict verdict={finding.verdict} />
          <span className="meta"> · {route}</span>
        </p>
      ) : (
        <p className="meta">{route}</p>
      )}
      <p className="scoped">{finding.scoped_text}</p>
      {compound && finding.qualification_flags.map((flag, i) => <Flag key={i} flag={flag} />)}
      {finding.qualification_check === 'unknown' && (
        <p className="meta">Comparison and scope were not assessed for this finding.</p>
      )}
      <Units units={finding.explanation} />
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

export function Findings({ findings }: { findings: AssertionFinding[] }) {
  const sorted = findings.slice().sort((a, b) => a.position - b.position)
  return (
    <section className="section" aria-labelledby="findings-heading">
      <h2 id="findings-heading">How we reached this</h2>
      {sorted.map((finding) => (
        <Finding key={finding.assertion_id} finding={finding} compound={sorted.length > 1} />
      ))}
    </section>
  )
}
