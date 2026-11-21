import { useEvidenceIndex } from './evidenceIndex'

export function SourceCitation({ number }: { number: number }) {
  const target = 'source-' + number
  return <a className="cite" href={'#' + target} aria-label={`Open source ${number}`} onClick={event => {
    const row = document.getElementById(target)
    if (!row) return
    event.preventDefault()
    const quote = row instanceof HTMLDetailsElement ? row : row.querySelector('details')
    if (quote) quote.open = true
    const focusTarget = quote?.querySelector('summary') ?? row
    focusTarget.focus({ preventScroll: true })
    row.scrollIntoView?.({ block: 'nearest' })
  }}>{number}</a>
}

export function Citations({ ids }: { ids: string[] }) {
  const index = useEvidenceIndex()
  const numbers = [...new Set(ids.map(id => index.get(id)?.number))]
  return <span className="cites">{numbers.map(n => n
    ? <SourceCitation key={n} number={n} />
    : <span key="missing" aria-label="Source unavailable">[?]</span>)}</span>
}
