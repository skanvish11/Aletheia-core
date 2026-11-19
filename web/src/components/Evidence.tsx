import type { EvidenceEntry } from '../evidenceIndex'
import { EVIDENCE_PANE_ID, useEvidenceIndex, useEvidenceSelection } from '../evidenceIndex'
import type { SourceSnapshot } from '../api/types'
import { RELATION_LABEL } from '../labels'
import { passageLink } from '../passageLink'

/** One piece of evidence: relation, source, the exact excerpt, why it counts, the link. */
function Detail({ entry: { number, evidence, source } }: { entry: EvidenceEntry }) {
  const a = evidence.assessment
  const passage = source && evidence.excerpts[0] ? passageLink(source.url, evidence.excerpts[0].text) : null
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
      {a.limitations.length > 0 && <p className="meta">Limitations: {a.limitations.join(' ')}</p>}
      {source && (
        <a className="open-original" href={passage ?? source.url} target="_blank" rel="noreferrer noopener">
          {passage ? 'Open the original at this passage' : 'Open the original'}
        </a>
      )}
      {a.rationale && (
        <details className="source-note">
          <summary>Why this passage matters</summary>
          <p className="source-rationale">{a.rationale}</p>
        </details>
      )}
    </article>
  )
}

function pageLabels(source: SourceSnapshot) {
  let website = ''
  let path = ''
  try {
    const url = new URL(source.url)
    website = url.hostname.replace(/^www\./, '')
    path = url.pathname.split('/').filter(Boolean).at(-1) ?? ''
  } catch {
    // Older snapshots may contain an incomplete page address.
  }
  const title = source.title?.trim()
  if (!title || title === source.url) {
    return { website, topic: path.replace(/[-_]/g, ' ') || 'Open page' }
  }
  const [pageTitle] = title.split(' | ')
  const parts = pageTitle.split(' - ')
  // Drop trailing site branding when its name matches the domain. Keep subtitles.
  const brand = parts.at(-1)?.toLowerCase().replace(/[^a-z0-9]/g, '') ?? ''
  const siteName = website.toLowerCase().replace(/[^a-z0-9]/g, '')
  const isBrand = parts.length > 1 && brand.length >= 3 && siteName.includes(brand)
  return { website, topic: (isBrand ? parts.slice(0, -1).join(' - ') : pageTitle) || title }
}

/** Every page the run read, quoted or not, so the reader can see what was consulted. */
function PagesRead({ sources, quoted }: { sources: SourceSnapshot[]; quoted: Set<string> }) {
  if (sources.length === 0) return null
  return (
    <details className="pane-rejected pane-sources">
      <summary>
        {sources.length} page{sources.length === 1 ? '' : 's'} read
      </summary>
      <table aria-label="Pages read">
        <thead>
          <tr><th scope="col">Website</th><th scope="col">Topic</th></tr>
        </thead>
        <tbody>
          {sources.map((source) => {
            const { website, topic } = pageLabels(source)
            return (
              <tr key={source.id}>
                <td>{website || 'Unknown website'}</td>
                <td>
                  <a href={source.url} title={source.title || undefined} target="_blank" rel="noreferrer noopener">
                    {topic}
                  </a>
                  {quoted.has(source.id) && <small className="page-quoted">quoted</small>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </details>
  )
}

export function EvidencePane({ sources = [] }: { sources?: SourceSnapshot[] }) {
  const index = useEvidenceIndex()
  const { selected, select } = useEvidenceSelection()
  const entries = [...index.values()]
  const quoted = new Set(entries.map((e) => e.evidence.assessment.citation.snapshot_id))
  if (entries.length === 0) {
    // No passage was quoted, but the pages that were read are still worth showing.
    if (sources.length === 0) return null
    return (
      <aside id={EVIDENCE_PANE_ID} className="evidence-pane" aria-labelledby="evidence-heading" tabIndex={-1}>
        <div className="pane-head">
          <h2 id="evidence-heading" className="section-label">
            Evidence
          </h2>
        </div>
        <div className="pane-body">
          <p className="meta">No passage was quoted as evidence.</p>
        </div>
        <PagesRead sources={sources} quoted={quoted} />
      </aside>
    )
  }
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
      <PagesRead sources={sources} quoted={quoted} />
    </aside>
  )
}
