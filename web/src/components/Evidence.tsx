import type { EvidenceEntry } from '../evidenceIndex'
import { evidenceAnchor, useEvidenceIndex } from '../evidenceIndex'
import { RELATION_LABEL, formatTime } from '../labels'

function Entry({ entry: { number, evidence, source } }: { entry: EvidenceEntry }) {
  const a = evidence.assessment
  return (
    <li id={evidenceAnchor(evidence.id)} className="evidence" tabIndex={-1}>
      <div className="evidence-head">
        <span className="evidence-number" aria-hidden="true">
          {number}
        </span>
        <div>
          <p className="evidence-title">
            {source ? (
              <a href={source.url} target="_blank" rel="noreferrer noopener">
                {source.title || source.url}
              </a>
            ) : (
              'Source unavailable'
            )}
          </p>
          <p className="meta">
            {[a.publisher, source?.published_date && `Published ${source.published_date}`]
              .filter(Boolean)
              .join(' · ')}
          </p>
        </div>
      </div>
      <p className={`relation relation-${a.relation}`}>
        {RELATION_LABEL[a.relation]}
        {!evidence.admissible &&
          ` · not admitted${evidence.rejection_reason ? `: ${evidence.rejection_reason}` : ''}`}
      </p>
      {evidence.excerpts.map((excerpt) => (
        <blockquote key={excerpt.start}>{excerpt.text}</blockquote>
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
          <dd>{evidence.excerpts.map((e) => e.span_ids.join(', ')).join(' | ')}</dd>
          <dt>Snapshot</dt>
          <dd>{a.citation.snapshot_id}</dd>
          <dt>Evidence ID</dt>
          <dd>{evidence.id}</dd>
          {a.origin && (
            <>
              <dt>Origin</dt>
              <dd>{a.origin}</dd>
            </>
          )}
          <dt>Independence</dt>
          <dd>{a.independence}</dd>
          {source && (
            <>
              <dt>Retrieved</dt>
              <dd>{formatTime(source.retrieved_at)}</dd>
              <dt>URL</dt>
              <dd>{source.url}</dd>
              <dt>Content hash</dt>
              <dd>{source.content_hash}</dd>
            </>
          )}
        </dl>
      </details>
    </li>
  )
}

/** Admitted evidence first; passages checked but not admitted sit collapsed below. */
export function Evidence() {
  const entries = [...useEvidenceIndex().values()]
  if (entries.length === 0) return null
  const admitted = entries.filter((e) => e.evidence.admissible)
  const rejected = entries.filter((e) => !e.evidence.admissible)
  return (
    <section className="section" aria-labelledby="evidence-heading">
      <h2 id="evidence-heading">Sources</h2>
      {admitted.length === 0 && <p className="meta">No passage was admitted as evidence.</p>}
      <ol className="evidence-list">
        {admitted.map((entry) => (
          <Entry key={entry.evidence.id} entry={entry} />
        ))}
      </ol>
      {rejected.length > 0 && (
        <details className="trace">
          <summary>
            {rejected.length} more passage{rejected.length === 1 ? '' : 's'} checked but not admitted
          </summary>
          <ol className="evidence-list" start={admitted.length + 1}>
            {rejected.map((entry) => (
              <Entry key={entry.evidence.id} entry={entry} />
            ))}
          </ol>
        </details>
      )}
    </section>
  )
}
