import type { EvidenceEntry } from '../evidenceIndex'
import { EVIDENCE_PANE_ID, useEvidenceIndex, useEvidenceSelection } from '../evidenceIndex'
import { RELATION_LABEL, formatTime } from '../labels'

/** One piece of evidence: relation, source, the exact excerpt, why it counts, the link. */
function Detail({ entry: { number, evidence, source } }: { entry: EvidenceEntry }) {
  const a = evidence.assessment
  return (
    <article className="evidence" aria-label={`Source ${number}`}>
      <p className={`relation relation-${a.relation}`}>
        {RELATION_LABEL[a.relation]}
        {!evidence.admissible && ' · not admitted'}
      </p>
      <h3 className="evidence-title">{source ? source.title || source.url : 'Source unavailable'}</h3>
      {a.publisher && <p className="evidence-meta">{a.publisher}</p>}
      {source?.published_date && <p className="evidence-meta">Published {source.published_date}</p>}
      {evidence.excerpts.map((excerpt) => (
        <blockquote key={excerpt.start}>{excerpt.text}</blockquote>
      ))}
      {!evidence.admissible && evidence.rejection_reason && (
        <p>
          <span className="inline-label">Not admitted</span>
          {evidence.rejection_reason}
        </p>
      )}
      <p>
        <span className="inline-label">Why it counts</span>
        {a.rationale}
      </p>
      {a.limitations.length > 0 && <p className="meta">Limitations: {a.limitations.join(' ')}</p>}
      {source && (
        <a className="open-original" href={source.url} target="_blank" rel="noreferrer noopener">
          Open the original
        </a>
      )}
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
    </article>
  )
}

/**
 * The evidence pane: one entry at a time, numbered as cited. Beside the report on wide
 * screens, below it on narrow ones. Passages checked but not admitted sit collapsed.
 */
export function EvidencePane() {
  const index = useEvidenceIndex()
  const { selected, select } = useEvidenceSelection()
  const entries = [...index.values()]
  if (entries.length === 0) return null
  const admitted = entries.filter((e) => e.evidence.admissible)
  const rejected = entries.filter((e) => !e.evidence.admissible)
  const current = (selected ? index.get(selected) : undefined) ?? entries[0]
  return (
    <aside id={EVIDENCE_PANE_ID} className="evidence-pane" aria-labelledby="evidence-heading" tabIndex={-1}>
      <div className="pane-head">
        <h2 id="evidence-heading" className="section-label">
          Evidence
        </h2>
        {admitted.length > 0 && (
          <div className="pane-tabs" role="group" aria-label="Admitted evidence">
            {admitted.map((entry) => (
              <button
                key={entry.evidence.id}
                type="button"
                className="pane-tab"
                aria-pressed={entry === current}
                aria-label={`Source ${entry.number}`}
                onClick={() => select(entry.evidence.id)}
              >
                {entry.number}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="pane-body" aria-live="polite">
        {admitted.length === 0 && <p className="meta">No passage was admitted as evidence.</p>}
        <Detail entry={current} />
      </div>
      {rejected.length > 0 && (
        <details className="pane-rejected">
          <summary>
            {rejected.length} more passage{rejected.length === 1 ? '' : 's'} checked but not admitted
          </summary>
          <ul>
            {rejected.map((entry) => (
              <li key={entry.evidence.id}>
                <button
                  type="button"
                  className="rejected-entry"
                  aria-pressed={entry === current}
                  onClick={() => select(entry.evidence.id)}
                >
                  <span className="rejected-number">{entry.number}</span>
                  <span>
                    {entry.source?.title || entry.source?.url || 'Source unavailable'}
                    {entry.evidence.rejection_reason && (
                      <span className="meta"> · {entry.evidence.rejection_reason}</span>
                    )}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </aside>
  )
}
