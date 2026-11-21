import type { SourceRow } from './examples'
import { EvidenceCards } from './EvidenceCards'
import { Icon } from './Icon'

function original(url: string) {
  try {
    const link = new URL(url)
    return /^https?:$/.test(link.protocol) ? link : undefined
  } catch { return undefined }
}

export function Evidence({ pages }: { pages: SourceRow[] }) {
  const cards = document.documentElement.dataset.layout === 'c' || new URLSearchParams(location.search).get('layout') === 'c'
  return (
    <section className="sources" aria-labelledby="evidence-heading">
      <div className="section-title"><h2 id="evidence-heading">Evidence</h2><span className="meta">{pages.length} {pages.length === 1 ? 'page' : 'pages'} read</span></div>
      {pages.length === 0 && <p className="meta">No source pages were retrieved.</p>}
      {cards ? <EvidenceCards pages={pages} /> : pages.map((page, i) => {
        const link = original(page.url)
        const preview = page.passages.find(p => !p.note && p.quote) ?? page.passages.find(p => p.quote)
        return <details className="source-row" id={`source-${i + 1}`} key={i}>
          <summary>
            <span className="evidence-number">[{i + 1}]</span>
            <span className="source-name">{page.title}</span>
            {link && <span className="domain">{link.hostname.replace(/^www\./, '')}</span>}
            <span className="quote-preview">{preview ? '“' + preview.quote + '”' : 'No saved passage'}</span>
            <Icon name="chevron" size={17} />
          </summary>
          <div className="source-detail">
            {page.passages.map(p => <div key={p.id}>
              {p.quote && <blockquote>{p.quote}</blockquote>}
              {p.note && <p className="meta">Excluded from the verdict · {p.note}</p>}
            </div>)}
            {!page.passages.length && <p className="meta">No passage from this page was used for the verdict.</p>}
            {link && <a href={link.href} rel="noopener noreferrer" target="_blank">Open original source ↗</a>}
          </div>
        </details>
      })}
    </section>
  )
}
