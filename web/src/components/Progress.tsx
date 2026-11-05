import { useState } from 'react'
import type { InvestigationEvent } from '../api/types'
import { describeEvent } from '../labels'

function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function EventList({ events }: { events: InvestigationEvent[] }) {
  return (
    <ol className="progress" aria-live="polite">
      {events.map((event) => (
        <li key={event.sequence}>
          <time dateTime={event.timestamp}>{clock(event.timestamp)}</time>
          <span>{describeEvent(event)}</span>
        </li>
      ))}
    </ol>
  )
}

/** Shown in place of the answer while research runs. */
export function ResearchInProgress({ events, replay }: { events: InvestigationEvent[]; replay: boolean }) {
  const latest = events.at(-1)
  return (
    <section className="researching" aria-labelledby="researching-heading">
      <h2 id="researching-heading">
        <span className="pulse" aria-hidden="true" />
        {replay ? 'Replaying research' : 'Researching'}
      </h2>
      <p className="meta">
        {latest ? `${describeEvent(latest)}.` : 'Waiting for the first step.'} The answer appears when research finishes.
        {replay && ' Times are from the original run.'}
      </p>
      <EventList events={events} />
    </section>
  )
}

/** After research: the full log, collapsed below the answer. Key it by investigation ID. */
export function ResearchActivity({ events }: { events: InvestigationEvent[] }) {
  const [open, setOpen] = useState(false)
  if (events.length === 0) return null
  return (
    <details className="section activity" open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>
        <h2>Research activity</h2>
        <span className="meta"> {events.length} steps, original timestamps</span>
      </summary>
      <EventList events={events} />
    </details>
  )
}
