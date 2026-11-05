import { useRef, useState } from 'react'
import { AlertTriangle, ArrowLeft, Check, Loader2, Search } from 'lucide-react'
import { SAMPLES, type Source } from '@/data/samples'
import { EvidenceDetail, Sentences, SimulationNote, VerdictText } from '@/shared/evidence'
import { useIsDesktop, useSimulatedRun } from '@/shared/simulation'
import {
  PromptInput,
  PromptInputBody,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
} from '@/components/ai-elements/prompt-input'
import { Suggestion } from '@/components/ai-elements/suggestion'
import { Task, TaskContent, TaskItem, TaskTrigger } from '@/components/ai-elements/task'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'

/**
 * Concept A — Focused claim checker with an editorial answer.
 * AI Elements: PromptInput, Suggestion, Task. shadcn/ui: Sheet, Button, Separator.
 * Evidence opens beside the answer on desktop, as a bottom sheet on mobile.
 */
export function ConceptA({ sampleKey }: { sampleKey: string }) {
  const run = useSimulatedRun(sampleKey)
  const { sample, phase } = run
  const desktop = useIsDesktop()
  const [selected, setSelected] = useState<Source | null>(null)
  const trigger = useRef<HTMLElement | null>(null)
  const panel = useRef<HTMLElement>(null)

  function openSource(source: Source, from: HTMLElement) {
    trigger.current = from
    setSelected(source)
    // Desktop panel: move focus into it so keyboard users land on the source.
    if (desktop) requestAnimationFrame(() => panel.current?.focus())
  }
  function closeSource() {
    setSelected(null)
    trigger.current?.focus()
  }
  function restart() {
    setSelected(null)
    run.reset()
  }

  if (phase === 'entry' || phase === 'submitting') {
    return (
      <div className="mx-auto max-w-2xl px-4 pt-14 pb-24 sm:pt-24">
        <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">Check a claim</h1>
        <p className="mt-3 max-w-lg text-muted-foreground">
          Aletheia researches the web and gives you a verdict linked to the exact source passages, including when a
          comparison is misleading.
        </p>
        <PromptInput className="mt-8" onSubmit={({ text }) => {
            if (text.trim()) run.start(text.trim())
          }}>
          <PromptInputBody>
            <PromptInputTextarea
              aria-label="Claim to check"
              placeholder="Paste or type one factual claim…"
              disabled={phase === 'submitting'}
            />
          </PromptInputBody>
          <PromptInputFooter>
            <PromptInputTools>
              <span className="px-2 text-xs text-muted-foreground">One claim at a time</span>
            </PromptInputTools>
            <PromptInputSubmit
              size="sm"
              aria-label="Investigate"
              status={phase === 'submitting' ? 'submitted' : undefined}
              disabled={phase === 'submitting'}
            >
              {phase === 'submitting' ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden /> Starting…
                </>
              ) : (
                'Investigate'
              )}
            </PromptInputSubmit>
          </PromptInputFooter>
        </PromptInput>

        <p className="mt-8 mb-2 text-sm text-muted-foreground">Or try an example</p>
        <div className="flex flex-col items-stretch gap-2">
          {SAMPLES.map((s) => (
            <Suggestion
              key={s.key}
              suggestion={s.claim}
              onClick={run.start}
              disabled={phase === 'submitting'}
              className="h-auto justify-start rounded-lg py-2.5 text-left whitespace-normal"
            />
          ))}
        </div>
      </div>
    )
  }

  const done = phase === 'done'
  const current = sample.steps[Math.max(0, run.steps - 1)]

  const report = (
    <article className="min-w-0">
      <button
        type="button"
        onClick={restart}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden /> Check another claim
      </button>

      <p className="mt-8 text-xs font-medium tracking-wide text-muted-foreground uppercase">Claim</p>
      <h1 className="mt-1 font-serif text-2xl leading-snug sm:text-3xl">{sample.claim}</h1>

      <div className="mt-4">
        <SimulationNote substituted={run.substituted} claim={sample.claim} />
      </div>

      {!done ? (
        <section aria-live="polite" className="mt-8">
          <p className="flex items-center gap-2 font-medium">
            <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden />
            Researching
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {run.steps === 0 ? 'Starting…' : `${current.text}.`} The answer appears when research finishes.
          </p>
          <Button variant="link" size="sm" className="mt-1 h-auto px-0" onClick={run.skip}>
            Skip to the answer (simulation only)
          </Button>
        </section>
      ) : (
        <section className="mt-8" aria-labelledby="answer">
          <h2 id="answer" className="font-serif text-2xl">
            <VerdictText verdict={sample.verdict} />
            {sample.caveat && <span className="text-foreground">, with a caveat</span>}
          </h2>
          <p className="mt-2 text-lg leading-relaxed">{sample.headline}</p>

          {sample.caveat && (
            <div role="note" className="mt-5 rounded-md border-l-4 border-caveat-border bg-caveat px-4 py-3">
              <p className="flex items-center gap-2 text-sm font-semibold">
                <AlertTriangle className="size-4" aria-hidden />
                {sample.caveat.label}
                <span className="font-normal text-muted-foreground">· {sample.caveat.dimension}</span>
              </p>
              <Sentences
                items={[{ text: sample.caveat.text, cites: sample.caveat.cites }]}
                sample={sample}
                activeId={selected?.id ?? null}
                onOpen={openSource}
                className="mt-1 text-[15px] leading-relaxed"
              />
            </div>
          )}

          <div className="mt-5 space-y-3">
            <Sentences
              items={sample.summary}
              sample={sample}
              activeId={selected?.id ?? null}
              onOpen={openSource}
              className="leading-relaxed"
            />
          </div>

          {sample.missing.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold">What would settle it</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                {sample.missing.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </div>
          )}

          <Separator className="my-8" />

          {sample.findings.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-semibold">How we reached this</h3>
              <Sentences
                items={sample.findings}
                sample={sample}
                activeId={selected?.id ?? null}
                onOpen={openSource}
                className="text-sm leading-relaxed text-muted-foreground"
              />
            </div>
          )}

          <div className="mt-6">
            <h3 className="text-sm font-semibold">Limitations</h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {sample.limitations.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </div>

          <div className="mt-6">
            <h3 className="text-sm font-semibold">Sources</h3>
            <ol className="mt-2 space-y-1 text-sm">
              {sample.sources.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    className={cn('text-left underline-offset-4 hover:underline', selected?.id === s.id && 'font-medium')}
                    onClick={(e) => openSource(s, e.currentTarget)}
                  >
                    {s.number}. {s.title}
                  </button>
                  <span className="text-muted-foreground"> · {s.publisher}</span>
                </li>
              ))}
            </ol>
          </div>
        </section>
      )}

      <Task className="mt-8" defaultOpen={!done} key={done ? 'done' : 'running'}>
        <TaskTrigger title={done ? `Research activity · ${sample.steps.length} steps` : 'Research activity'} />
        <TaskContent>
          {sample.steps.slice(0, run.steps).map((step) => (
            <TaskItem key={step.at} className="flex gap-3">
              <span className="w-16 shrink-0 font-mono text-xs tabular-nums">{step.at}</span>
              <span>{step.text}</span>
            </TaskItem>
          ))}
        </TaskContent>
      </Task>
    </article>
  )

  return (
    <div className="mx-auto max-w-6xl px-4 pt-6 pb-24">
      {desktop && done ? (
        <div className="grid grid-cols-[minmax(0,1fr)_360px] gap-12">
          <div className="max-w-2xl">{report}</div>
          <aside
            ref={panel}
            tabIndex={-1}
            aria-label="Evidence"
            onKeyDown={(e) => {
              if (e.key === 'Escape' && selected) closeSource()
            }}
            className="sticky top-6 self-start rounded-lg border bg-card p-5 outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {selected ? (
              <>
                <div className="mb-4 flex items-center justify-between">
                  <p className="text-sm font-semibold">Evidence</p>
                  <Button variant="ghost" size="sm" onClick={closeSource}>
                    Close
                  </Button>
                </div>
                <EvidenceDetail source={selected} assertion={sample.claim} />
              </>
            ) : (
              <div className="text-sm text-muted-foreground">
                <Search className="mb-3 size-5" aria-hidden />
                <p className="font-medium text-foreground">Inspect the evidence</p>
                <p className="mt-1">
                  Select a numbered citation to see the exact passage here. Your place in the answer stays put.
                </p>
                <p className="mt-4 flex items-center gap-2">
                  <Check className="size-4 text-supported" aria-hidden /> Every quotation is checked against the stored
                  page.
                </p>
              </div>
            )}
          </aside>
        </div>
      ) : (
        <div className="mx-auto max-w-2xl">{report}</div>
      )}

      {!desktop && (
        <Sheet open={selected !== null} onOpenChange={(open) => !open && closeSource()}>
          <SheetContent side="bottom" className="max-h-[85vh] overflow-y-auto rounded-t-xl">
            <SheetHeader className="px-5 pt-5 pb-0">
              <SheetTitle>Evidence</SheetTitle>
              <SheetDescription>The source behind this part of the answer.</SheetDescription>
            </SheetHeader>
            <div className="px-5 pb-8">{selected && <EvidenceDetail source={selected} assertion={sample.claim} />}</div>
          </SheetContent>
        </Sheet>
      )}
    </div>
  )
}
