import { createContext, useContext, useMemo, useRef, useState } from 'react'
import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type AppendMessage,
  type DataMessagePartProps,
  type ThreadMessageLike,
} from '@assistant-ui/react'
import { AlertTriangle, ArrowUp, Loader2, ShieldCheck } from 'lucide-react'
import { SAMPLES, type Source } from '@/data/samples'
import { EvidenceDetail, Sentences, SimulationNote, VerdictText } from '@/shared/evidence'
import { useIsDesktop, useSimulatedRun } from '@/shared/simulation'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'

/**
 * Concept B — Conversational investigation (assistant-ui primitives).
 * The claim is a message; the answer is an app-defined report component
 * rendered as a data part, never model-invented layout.
 */

type RunState = ReturnType<typeof useSimulatedRun>
interface Ctx {
  run: RunState
  selectedId: string | null
  openSource: (source: Source, trigger: HTMLElement) => void
}
const ConceptBContext = createContext<Ctx | null>(null)
const useConceptB = () => {
  const ctx = useContext(ConceptBContext)
  if (!ctx) throw new Error('ConceptB context missing')
  return ctx
}

function textOf(message: AppendMessage): string {
  return message.content
    .map((part) => (part.type === 'text' ? part.text : ''))
    .join(' ')
    .trim()
}

export function ConceptB({ sampleKey }: { sampleKey: string }) {
  const run = useSimulatedRun(sampleKey)
  const { phase } = run
  const desktop = useIsDesktop()
  const [selected, setSelected] = useState<Source | null>(null)
  const trigger = useRef<HTMLElement | null>(null)

  const messages = useMemo<ThreadMessageLike[]>(() => {
    if (phase === 'entry') return []
    return [
      { id: 'claim', role: 'user', content: [{ type: 'text', text: run.typed }] },
      {
        id: 'investigation',
        role: 'assistant',
        content: [{ type: 'data-investigation', data: { phase, steps: run.steps } }],
        status: phase === 'done' ? { type: 'complete', reason: 'stop' } : { type: 'running' },
      },
    ]
  }, [phase, run.typed, run.steps])

  const runtime = useExternalStoreRuntime<ThreadMessageLike>({
    messages,
    isRunning: phase === 'submitting' || phase === 'researching',
    convertMessage: (m) => m,
    // Each message starts a fresh investigation; follow-up chat is out of scope.
    onNew: async (message) => {
      const text = textOf(message)
      if (!text) return
      setSelected(null)
      run.start(text)
    },
  })

  function openSource(source: Source, from: HTMLElement) {
    trigger.current = from
    setSelected(source)
  }

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ConceptBContext.Provider value={{ run, selectedId: selected?.id ?? null, openSource }}>
        <ThreadPrimitive.Root className="mx-auto flex h-full max-w-3xl flex-col px-4">
          <ThreadPrimitive.Viewport className="flex-1 overflow-y-auto pt-6 pb-4">
            <ThreadPrimitive.Empty>
              <Welcome />
            </ThreadPrimitive.Empty>
            <ThreadPrimitive.Messages components={{ UserMessage, AssistantMessage }} />
          </ThreadPrimitive.Viewport>

          <ComposerPrimitive.Root className="mb-4 flex items-end gap-2 rounded-2xl border bg-background p-2 shadow-sm focus-within:ring-2 focus-within:ring-ring">
            <ComposerPrimitive.Input
              rows={1}
              aria-label="Claim to check"
              placeholder={phase === 'done' ? 'Check another claim…' : 'Type one factual claim to check…'}
              className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-[15px] outline-none placeholder:text-muted-foreground"
            />
            <ComposerPrimitive.Send asChild>
              <Button size="icon" className="rounded-full" aria-label="Investigate">
                <ArrowUp className="size-4" aria-hidden />
              </Button>
            </ComposerPrimitive.Send>
          </ComposerPrimitive.Root>
          <p className="-mt-2 mb-3 text-center text-xs text-muted-foreground">
            Each message starts a new investigation. Follow-up questions aren’t supported yet.
          </p>
        </ThreadPrimitive.Root>

        <Sheet open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
          <SheetContent
            side={desktop ? 'right' : 'bottom'}
            className={desktop ? 'w-[420px] overflow-y-auto sm:max-w-[420px]' : 'max-h-[85vh] overflow-y-auto rounded-t-xl'}
            onCloseAutoFocus={(e) => {
              e.preventDefault()
              trigger.current?.focus()
            }}
          >
            <SheetHeader className="px-5 pt-5 pb-0">
              <SheetTitle>Evidence</SheetTitle>
              <SheetDescription>The source behind this part of the answer.</SheetDescription>
            </SheetHeader>
            <div className="px-5 pb-8">
              {selected && <EvidenceDetail source={selected} assertion={run.sample.claim} />}
            </div>
          </SheetContent>
        </Sheet>
      </ConceptBContext.Provider>
    </AssistantRuntimeProvider>
  )
}

function Welcome() {
  return (
    <div className="mx-auto max-w-xl pt-10 text-center sm:pt-20">
      <ShieldCheck className="mx-auto size-8 text-muted-foreground" aria-hidden />
      <h1 className="mt-4 text-2xl font-semibold tracking-tight">What claim should I check?</h1>
      <p className="mt-2 text-muted-foreground">
        I’ll research it and answer with a verdict, any caveat that changes it, and the exact passages behind it.
      </p>
      <div className="mt-8 flex flex-col gap-2">
        {SAMPLES.map((s) => (
          <ThreadPrimitive.Suggestion
            key={s.key}
            prompt={s.claim}
            send
            className="rounded-xl border px-4 py-3 text-left text-sm transition-colors hover:bg-muted"
          >
            {s.claim}
          </ThreadPrimitive.Suggestion>
        ))}
      </div>
    </div>
  )
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="flex justify-end py-3">
      <div className="max-w-[85%] rounded-2xl bg-muted px-4 py-2.5 text-[15px]">
        <span className="sr-only">Claim: </span>
        <MessagePrimitive.Parts />
      </div>
    </MessagePrimitive.Root>
  )
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="py-3">
      {/* Our report shows its own progress, so hide the library's running-dot placeholder. */}
      <MessagePrimitive.Parts
        components={{ data: { by_name: { investigation: InvestigationPart } } }}
        unstable_showEmptyOnNonTextEnd={false}
      />
    </MessagePrimitive.Root>
  )
}

/** The investigation, rendered by the app from structured data. */
function InvestigationPart(_props: DataMessagePartProps<{ phase: string; steps: number }>) {
  const { run, selectedId, openSource } = useConceptB()
  const { sample, phase } = run
  const done = phase === 'done'

  return (
    <div className="space-y-4">
      <SimulationNote substituted={run.substituted} claim={sample.claim} />

      <div aria-live="polite">
        {/* Visible while researching; folded into one line once the answer is ready. */}
        <details open={!done} key={done ? 'done' : 'running'} className="group text-sm text-muted-foreground">
          <summary className={done ? 'cursor-pointer' : 'sr-only'}>Research activity · {sample.steps.length} steps</summary>
          <ol className="mt-1.5 space-y-1.5">
            {sample.steps.slice(0, run.steps).map((step, i) => (
              <li key={step.at} className="flex items-start gap-2">
                {!done && i === run.steps - 1 ? (
                  <Loader2 className="mt-0.5 size-3.5 shrink-0 animate-spin" aria-hidden />
                ) : (
                  <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-muted-foreground/50" aria-hidden />
                )}
                {step.text}
              </li>
            ))}
          </ol>
        </details>
        {!done && (
          <div className="mt-2 flex items-center gap-3 text-sm">
            {run.steps === 0 && (
              <span className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" aria-hidden /> Starting investigation…
              </span>
            )}
            <Button variant="link" size="sm" className="h-auto px-0" onClick={run.skip}>
              Skip to the answer (simulation only)
            </Button>
          </div>
        )}
      </div>

      {done && (
        <section aria-label="Answer" className="rounded-xl border bg-card p-5">
          <p className="text-lg">
            <VerdictText verdict={sample.verdict} />
            {sample.caveat && <span>, with a caveat</span>}
          </p>
          <p className="mt-1 text-[15px]">{sample.headline}</p>

          {sample.caveat && (
            <div role="note" className="mt-4 rounded-lg bg-caveat px-4 py-3">
              <p className="flex items-center gap-2 text-sm font-semibold">
                <AlertTriangle className="size-4" aria-hidden /> {sample.caveat.label}
                <span className="font-normal text-muted-foreground">· {sample.caveat.dimension}</span>
              </p>
              <Sentences
                items={[{ text: sample.caveat.text, cites: sample.caveat.cites }]}
                sample={sample}
                activeId={selectedId}
                onOpen={openSource}
                className="mt-1 text-sm leading-relaxed"
              />
            </div>
          )}

          <div className="mt-4 space-y-2">
            <Sentences
              items={sample.summary}
              sample={sample}
              activeId={selectedId}
              onOpen={openSource}
              className="text-[15px] leading-relaxed"
            />
          </div>

          {sample.missing.length > 0 && (
            <div className="mt-4">
              <p className="text-sm font-semibold">What would settle it</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm">
                {sample.missing.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </div>
          )}

          <details className="mt-4 text-sm">
            <summary className="cursor-pointer text-muted-foreground">Limitations and all sources</summary>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
              {sample.limitations.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
            <ol className="mt-3 space-y-1">
              {sample.sources.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    className="text-left underline-offset-4 hover:underline"
                    onClick={(e) => openSource(s, e.currentTarget)}
                  >
                    {s.number}. {s.title}
                  </button>
                  <span className="text-muted-foreground"> · {s.publisher}</span>
                </li>
              ))}
            </ol>
          </details>
        </section>
      )}
    </div>
  )
}
