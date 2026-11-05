import { useId, useRef, type MouseEvent } from 'react'
import { createPortal } from 'react-dom'
import { evidenceAnchor, useEvidenceIndex } from '../evidenceIndex'
import { RELATION_LABEL } from '../labels'

/**
 * A numbered citation. Activating it opens a preview of the source and excerpt
 * (native popover: Esc and outside-click close it, focus returns to the link).
 * Without popover support it behaves as a plain link to the evidence entry.
 */
function Cite({ id }: { id: string }) {
  const entry = useEvidenceIndex().get(id)
  const popoverId = useId()
  const popover = useRef<HTMLDivElement>(null)

  if (!entry) return <span className="cite cite-missing">[?]</span>
  const { number, assessment, source } = entry

  function open(event: MouseEvent<HTMLAnchorElement>) {
    const el = popover.current
    if (!el || typeof el.showPopover !== 'function') return // fall back to the anchor jump
    event.preventDefault()
    el.showPopover()
    el.querySelector<HTMLElement>('.cite-preview-close')?.focus()
  }

  return (
    <>
      <a
        className="cite"
        href={`#${evidenceAnchor(id)}`}
        onClick={open}
        aria-haspopup="dialog"
        aria-label={`Source ${number}${source?.title ? `: ${source.title}` : ''}`}
      >
        {number}
      </a>
      {/* Portaled: citations sit inside <p>, which cannot contain block content. */}
      {createPortal(
      <div
        ref={popover}
        id={popoverId}
        popover="auto"
        role="dialog"
        aria-label={`Source ${number}`}
        className="cite-preview"
      >
        <div className="cite-preview-head">
          <span className="evidence-number">{number}</span>
          <div>
            <p className="cite-preview-title">{source?.title ?? source?.url ?? 'Source'}</p>
            <p className="meta">
              {[source?.publisher, source?.published_date].filter(Boolean).join(' · ')}
            </p>
          </div>
          <button
            type="button"
            className="cite-preview-close"
            popoverTarget={popoverId}
            popoverTargetAction="hide"
            aria-label="Close source preview"
          >
            ×
          </button>
        </div>
        <p className="meta">{RELATION_LABEL[assessment.relation]}</p>
        {assessment.excerpts.map((excerpt) => (
          <blockquote key={excerpt.span_ids.join('-')}>{excerpt.text}</blockquote>
        ))}
        <a
          href={`#${evidenceAnchor(id)}`}
          onClick={() => popover.current?.hidePopover()}
        >
          View full evidence entry
        </a>
      </div>,
      document.body,
      )}
    </>
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
