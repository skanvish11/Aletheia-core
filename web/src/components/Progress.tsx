import { useState } from 'react'
import type { InvestigationEvent } from '../api/types'
import { describeEvent, elapsed } from '../labels'

/** The research log: time since the first step, then what happened. */
function EventList({ events }: { events: InvestigationEvent[] }) {
  const start = events[0]?.timestamp
  return (
    <ol className="progress" aria-live="polite">
      {events.map((event) => (
        <li key={event.sequence}>
          <time dateTime={event.timestamp}>{start ? elapsed(event.timestamp, start) : ''}</time>
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
        Research log · {events.length} step{events.length === 1 ? '' : 's'}
      </summary>
      <EventList events={events} />
    </details>
  )
}
