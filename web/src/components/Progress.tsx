import type { InvestigationEvent } from '../api/types'
import { describeEvent, elapsed, runCounts } from '../labels'

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

/** Steps that only announce the next line: the finished call and the page read follow. */
const ANNOUNCEMENTS = new Set<InvestigationEvent['type']>(['provider_attempt_started', 'source_selected'])

/** After research: the log, collapsed below the answer. Key it by investigation ID. */
export function ResearchActivity({ events }: { events: InvestigationEvent[] }) {
  if (events.length === 0) return null
  const steps = events.filter((event) => !ANNOUNCEMENTS.has(event.type))
  const { searches, pages, modelCalls } = runCounts(events)
  const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`
  // Only what the run reported: older recordings carry no provider events.
  const facts = [
    searches > 0 ? plural(searches, 'search', 'searches') : null,
    pages > 0 ? plural(pages, 'page read', 'pages read') : null,
    modelCalls > 0 ? plural(modelCalls, 'model call', 'model calls') : null,
    events.length > 1 ? `${elapsed(events.at(-1)!.timestamp, events[0].timestamp)} elapsed` : null,
  ].filter(Boolean)
  return (
    <details className="activity">
      <summary>Research log <span className="step-count">{plural(steps.length, 'step', 'steps')}</span></summary>
      {facts.length > 0 && <p className="meta">{facts.join(' · ')}</p>}
      <EventList events={steps} />
    </details>
  )
}
