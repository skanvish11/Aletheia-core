import { EVIDENCE_PANE_ID, useEvidenceIndex, useEvidenceSelection } from '../evidenceIndex'

/**
 * A numbered citation. Activating it shows that evidence in the evidence pane beside
 * the report, so checking a source never leaves the page.
 */
function Cite({ id }: { id: string }) {
  const entry = useEvidenceIndex().get(id)
  const { selected, select } = useEvidenceSelection()
  if (!entry) return <span className="cite cite-missing">[?]</span>
  const { number, source } = entry
  return (
    <button
      type="button"
      className="cite"
      aria-pressed={selected === id}
      aria-controls={EVIDENCE_PANE_ID}
      aria-label={`Show source ${number}${source?.title ? `: ${source.title}` : ''}`}
      onClick={() => select(id, true)}
    >
      {number}
    </button>
  )
}

export function Citations({ ids }: { ids: string[] }) {
  if (ids.length === 0) return null
  return (
    <span className="cites">
      {ids.map((id) => (
        <Cite key={id} id={id} />
      ))}
    </span>
  )
}
