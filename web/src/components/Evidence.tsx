import type { EvidenceRelation, EvidenceResponse } from '../api/types'
import { formatTime } from '../labels'

const RELATION_LABEL: Record<EvidenceRelation, string> = {
  supports: 'Supports',
  contradicts: 'Contradicts',
  context: 'Context',
  not_relevant: 'Not relevant',
}

export function Evidence({ evidence }: { evidence: EvidenceResponse }) {
  const sources = new Map(evidence.sources.map((s) => [s.id, s]))
  return (
    <section aria-labelledby="evidence-heading">
      <h2 id="evidence-heading">Evidence</h2>
      <ol className="evidence-list">
        {evidence.assessments.map((a) => {
          const source = sources.get(a.snapshot_id)
          return (
            <li key={a.id} id={`evidence-${a.id}`} className="card evidence">
              <header className="evidence-head">
                <span className={`relation relation-${a.relation}`}>{RELATION_LABEL[a.relation]}</span>
                {!a.admissible && <span className="badge verdict-insufficient_evidence">Not admissible</span>}
              </header>
              {a.excerpts.map((excerpt) => (
                <blockquote key={excerpt.span_ids.join('-')}>
                  {excerpt.text}
                  <span className="spans muted"> (spans {excerpt.span_ids.join(', ')})</span>
                </blockquote>
              ))}
              <p className="muted">{a.rationale}</p>
              {source && (
                <p className="source">
                  <a href={source.url} target="_blank" rel="noreferrer noopener">
                    {source.title ?? source.url}
                  </a>
                  <span className="muted">
                    {[source.publisher, source.published_date && `published ${source.published_date}`]
                      .filter(Boolean)
                      .join(' · ')}
                    {' · retrieved '}
                    {formatTime(source.retrieved_at)}
                  </span>
                </p>
              )}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
