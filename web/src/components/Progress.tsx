import type { InvestigationEvent } from '../api/types'
import { describeEvent } from '../labels'

function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function Progress({ events, replay }: { events: InvestigationEvent[]; replay: boolean }) {
  return (
    <section aria-labelledby="progress-heading">
      <h2 id="progress-heading">Progress</h2>
      {replay && <p className="muted">Replaying recorded progress. Times are from the original run.</p>}
      <ol className="progress" aria-live="polite">
        {events.map((event) => (
          <li key={event.sequence}>
            <time dateTime={event.timestamp}>{clock(event.timestamp)}</time>
            <span>{describeEvent(event)}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}
