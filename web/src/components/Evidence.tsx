import { evidenceAnchor, useEvidenceIndex } from '../evidenceIndex'
import { RELATION_LABEL, formatTime } from '../labels'

export function Evidence() {
  const entries = [...useEvidenceIndex().values()]
  if (entries.length === 0) return null
  return (
    <section className="section" aria-labelledby="evidence-heading">
      <h2 id="evidence-heading">Sources</h2>
      <ol className="evidence-list">
        {entries.map(({ number, assessment: a, source }) => (
          <li key={a.id} id={evidenceAnchor(a.id)} className="evidence" tabIndex={-1}>
            <div className="evidence-head">
              <span className="evidence-number" aria-hidden="true">
                {number}
              </span>
              <div>
                <p className="evidence-title">
                  {source ? (
                    <a href={source.url} target="_blank" rel="noreferrer noopener">
                      {source.title ?? source.url}
                    </a>
                  ) : (
                    'Source unavailable'
                  )}
                </p>
                <p className="meta">
                  {[source?.publisher, source?.published_date && `Published ${source.published_date}`]
                    .filter(Boolean)
                    .join(' · ')}
                </p>
              </div>
            </div>
            <p className={`relation relation-${a.relation}`}>
              {RELATION_LABEL[a.relation]}
              {!a.admissible && ' · not admissible, not used for the verdict'}
            </p>
            {a.excerpts.map((excerpt) => (
              <blockquote key={excerpt.span_ids.join('-')}>{excerpt.text}</blockquote>
            ))}
            <p>
              <span className="meta">Why it matters: </span>
              {a.rationale}
            </p>
            {a.limitations.length > 0 && <p className="meta">Limitations: {a.limitations.join(' ')}</p>}
            <details className="trace">
              <summary>Citation details</summary>
              <dl>
                <dt>Spans</dt>
                <dd>{a.excerpts.map((e) => e.span_ids.join(', ')).join(' | ')}</dd>
                <dt>Snapshot</dt>
                <dd>{a.snapshot_id}</dd>
                <dt>Evidence ID</dt>
                <dd>{a.id}</dd>
                {source && (
                  <>
                    <dt>Retrieved</dt>
                    <dd>{formatTime(source.retrieved_at)}</dd>
                    <dt>URL</dt>
                    <dd>{source.url}</dd>
                  </>
                )}
              </dl>
            </details>
          </li>
        ))}
      </ol>
    </section>
  )
}
