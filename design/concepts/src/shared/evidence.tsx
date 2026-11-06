import { ExternalLink } from 'lucide-react'
import { RELATION_LABEL, VERDICT_LABEL, type Sample, type Sentence, type Source, type Verdict } from '@/data/samples'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { cn } from '@/lib/utils'

const VERDICT_CLASS: Record<Verdict, string> = {
  supported: 'text-supported',
  contradicted: 'text-contradicted',
  mixed: 'text-mixed',
  insufficient_evidence: 'text-insufficient',
}

export function VerdictText({ verdict, className }: { verdict: Verdict; className?: string }) {
  return <span className={cn('font-semibold', VERDICT_CLASS[verdict], className)}>{VERDICT_LABEL[verdict]}</span>
}

/** A numbered citation. Clicking (or Enter/Space) opens the source without leaving the answer. */
export function Cite({
  source,
  active,
  onOpen,
}: {
  source: Source
  active: boolean
  onOpen: (source: Source, trigger: HTMLElement) => void
}) {
  return (
    <button
      type="button"
      onClick={(e) => onOpen(source, e.currentTarget)}
      aria-label={`Source ${source.number}: ${source.title}`}
      aria-pressed={active}
      className={cn(
        'mx-0.5 inline-flex h-5 min-w-5 -translate-y-px items-center justify-center rounded border px-1 align-middle text-[11px] font-medium tabular-nums transition-colors',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
        active ? 'border-primary bg-primary text-primary-foreground' : 'border-border text-muted-foreground hover:border-foreground hover:text-foreground',
      )}
    >
      {source.number}
    </button>
  )
}

export function Sentences({
  items,
  sample,
  activeId,
  onOpen,
  className,
}: {
  items: Sentence[]
  sample: Sample
  activeId: string | null
  onOpen: (source: Source, trigger: HTMLElement) => void
  className?: string
}) {
  const byId = new Map(sample.sources.map((s) => [s.id, s]))
  return (
    <>
      {items.map((sentence, i) => (
        <p key={i} className={className}>
          {sentence.text}
          {sentence.cites.map((id) => {
            const source = byId.get(id)
            return source ? <Cite key={id} source={source} active={activeId === id} onOpen={onOpen} /> : null
          })}
        </p>
      ))}
    </>
  )
}

/** Everything needed to judge one source: identity, the exact excerpt, why it matters, limits. */
export function EvidenceDetail({ source, assertion }: { source: Source; assertion: string }) {
  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs text-muted-foreground">Source {source.number}</p>
        <h3 className="mt-0.5 leading-snug font-semibold">{source.title}</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          {source.publisher} · published {source.published}
        </p>
      </div>
      <p
        className={cn(
          'text-sm font-medium',
          source.relation === 'supports' && 'text-supported',
          source.relation === 'contradicts' && 'text-contradicted',
          source.relation === 'context' && 'text-muted-foreground',
        )}
      >
        {RELATION_LABEL[source.relation]}
      </p>
      <blockquote className="border-l-2 border-border pl-3 font-serif text-[15px] leading-relaxed">
        {source.excerpt}
      </blockquote>
      <p className="text-sm">
        <span className="text-muted-foreground">Why it matters: </span>
        {source.why}
      </p>
      <p className="text-sm">
        <span className="text-muted-foreground">For the claim: </span>
        {assertion}
      </p>
      {source.limitations.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          {source.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      )}
      <a
        href={source.url}
        target="_blank"
        rel="noreferrer noopener"
        className="inline-flex items-center gap-1 text-sm font-medium underline underline-offset-4"
      >
        Open the original page <ExternalLink className="size-3.5" aria-hidden />
      </a>
      <Collapsible>
        <CollapsibleTrigger className="text-xs text-muted-foreground underline-offset-4 hover:underline">
          Citation details
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 font-mono text-xs text-muted-foreground">
          <span>Spans</span>
          <span>{source.spans}</span>
          <span>Retrieved</span>
          <span>{source.retrieved}</span>
          <span>URL</span>
          <span className="break-all">{source.url}</span>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}

/** Visible on every screen: this is a design concept with simulated research. */
export function SimulationNote({ substituted, claim }: { substituted: boolean; claim: string }) {
  if (!substituted) return null
  return (
    <p className="rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
      <strong className="font-semibold text-foreground">Simulated.</strong> This concept plays back a sample instead of
      researching what you typed. Showing results for: “{claim}”
    </p>
  )
}
