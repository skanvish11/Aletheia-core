import type {
  AlmostCorrection,
  Decision,
  ExplanationUnit,
  InvestigationResult,
  QualificationFlag,
  Route,
  UndecidedReason,
} from '../api/types'
import { DIMENSION_LABEL, FLAG_LABEL, UNDECIDED_FALLBACK, UNDECIDED_LABEL, VERDICT_LABEL } from '../labels'
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

const UNDECIDED_CLASS: Record<UndecidedReason, string> = {
  insufficient_evidence: 'insufficient',
  conflicting_evidence: 'conflicting',
}

/** True / False / Almost, or Insufficient / Conflicting evidence. Never a score. */
export function DecisionLabel({ decision }: { decision: Decision }) {
  if (decision.outcome === 'unable_to_decide' || !decision.verdict) {
    const reason = decision.unable_to_decide_reason
    return (
      <span className={`verdict verdict-${reason ? UNDECIDED_CLASS[reason] : 'insufficient'}`}>
        {reason ? UNDECIDED_LABEL[reason] : UNDECIDED_FALLBACK}
      </span>
    )
  }
  return <span className={`verdict verdict-${decision.verdict}`}>{VERDICT_LABEL[decision.verdict]}</span>
}

/** A qualification: what the caveat is, on the caveat tint, with its citations. */
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

/** Almost: what holds, what doesn't, and the claim as the evidence supports it. */
export function Correction({ correction }: { correction: AlmostCorrection }) {
  const parts: [string, ExplanationUnit][] = [
    ['What’s correct', correction.what_is_correct],
    ['What needs correcting', correction.what_needs_correction],
    ['Corrected claim', correction.corrected_claim],
  ]
  return (
    <dl className="correction">
      {parts.map(([label, unit]) => (
        <div key={label} className={label === 'Corrected claim' ? 'correction-claim' : undefined}>
          <dt>{label}</dt>
          <dd>
            {unit.text}
            <Citations ids={unit.evidence_ids} />
          </dd>
        </div>
      ))}
    </dl>
  )
}

const ROUTE_LABEL: Record<Route, string> = { quick: 'Quick check', deep: 'Deeper research' }

/** What was actually checked: the scoped assertion and how it was researched. */
export function Findings({ result, route }: { result: InvestigationResult; route: Route | null }) {
  const { assertion, finding } = result
  return (
    <section className="section" aria-labelledby="findings-heading">
      <h2 id="findings-heading" className="section-label">
        What we checked
      </h2>
      <p>{assertion.text}</p>
      {!route && <p className="meta">Recommended: {ROUTE_LABEL[assertion.recommended_route]}</p>}
      {result.scope_note && <p className="meta">{result.scope_note}</p>}
      {finding.qualification_check === 'unknown' && (
        <p className="meta">Comparisons and scope were not assessed for this claim.</p>
      )}
    </section>
  )
}
