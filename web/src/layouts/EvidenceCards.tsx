import type { SourceRow } from './examples'
import { Icon } from './Icon'

export function EvidenceCards({ pages }: { pages: SourceRow[] }) {
  return <div className="evidence-grid">
    {pages.map((page, index) => {
      const number = index + 1
      const link = URL.canParse(page.url) ? new URL(page.url) : undefined
      const original = link && ['https:', 'http:'].includes(link.protocol) ? link : undefined
      const domain = original?.hostname.replace(/^www\./, '')
      const hasQuote = page.passages.some(p => p.quote)
      return <article className="evidence-card" id={'source-' + number} tabIndex={-1} key={number}>
        <header>
          <span className="evidence-number">[{number}]</span>
          {original ? <a href={original.href} target="_blank" rel="noopener noreferrer"
            aria-label={`Open ${page.title} on ${domain} in a new tab`}>
            <span>{domain}</span><Icon name="external" size={15} />
          </a> : <span className="meta">{page.title}</span>}
        </header>
        <ul><li>{page.takeaway || 'This page was retrieved, but no passage was used for the verdict.'}</li></ul>
        {hasQuote && <details className="card-quote">
          <summary><span className="show-quote">View quote</span><span className="hide-quote">Hide quote</span><Icon name="chevron" size={15} /></summary>
          {page.passages.map(p => <div key={p.id}>
            {p.quote && <blockquote>{p.quote}</blockquote>}
            {p.note && <p className="meta">Excluded from the verdict · {p.note}</p>}
          </div>)}
        </details>}
      </article>
    })}
  </div>
}
