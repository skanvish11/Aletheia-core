import { useEffect, useState } from 'react'
import { SAMPLES } from '@/data/samples'
import { ConceptA } from '@/concepts/ConceptA'
import { ConceptB } from '@/concepts/ConceptB'
import { TooltipProvider } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

const CONCEPTS = [
  { key: 'a', label: 'A · Focused checker', hint: 'AI Elements + shadcn/ui' },
  { key: 'b', label: 'B · Conversational', hint: 'assistant-ui' },
] as const
type ConceptKey = (typeof CONCEPTS)[number]['key']

/** State lives in the URL hash (#a/caveat) so reviewers can share a specific view. */
function readHash(): { concept: ConceptKey; sample: string } {
  const [c, s] = window.location.hash.replace('#', '').split('/')
  return {
    concept: c === 'b' ? 'b' : 'a',
    sample: SAMPLES.some((x) => x.key === s) ? s : SAMPLES[0].key,
  }
}

function useSystemDarkMode() {
  useEffect(() => {
    const mql = window.matchMedia('(prefers-color-scheme: dark)')
    const apply = () => document.documentElement.classList.toggle('dark', mql.matches)
    apply()
    mql.addEventListener('change', apply)
    return () => mql.removeEventListener('change', apply)
  }, [])
}

function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: T
  options: readonly { key: T; label: string; hint?: string }[]
  onChange: (key: T) => void
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border bg-background p-0.5">
      {options.map((o) => (
        <button
          key={o.key}
          type="button"
          role="radio"
          aria-checked={value === o.key}
          title={o.hint}
          onClick={() => onChange(o.key)}
          className={cn(
            'rounded-md px-2.5 py-1 text-xs font-medium whitespace-nowrap transition-colors',
            value === o.key ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export default function App() {
  useSystemDarkMode()
  const [state, setState] = useState(readHash)

  useEffect(() => {
    const onHash = () => setState(readHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const go = (next: Partial<typeof state>) => {
    const merged = { ...state, ...next }
    window.location.hash = `${merged.concept}/${merged.sample}`
  }

  return (
    <TooltipProvider>
      <div className="flex h-dvh flex-col bg-background text-foreground">
        <header className="z-10 shrink-0 border-b bg-background/95 backdrop-blur">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5">
            <span className="font-serif text-lg font-semibold">Aletheia</span>
            <span className="rounded border border-dashed px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
              Design concept · simulated research · invented sample data
            </span>
            <div className="ml-auto flex flex-wrap items-center gap-2">
              <Segmented
                label="Concept"
                value={state.concept}
                options={CONCEPTS}
                onChange={(concept) => go({ concept })}
              />
              <Segmented
                label="Sample outcome"
                value={state.sample}
                options={SAMPLES.map((s) => ({ key: s.key, label: s.label }))}
                onChange={(sample) => go({ sample })}
              />
            </div>
          </div>
        </header>

        {/* The page scrolls inside main, so Concept B's thread can fill exactly the space below the header. */}
        <main className={cn('min-h-0 flex-1', state.concept === 'a' ? 'overflow-y-auto' : 'overflow-hidden')}>
          {state.concept === 'a' ? (
            <ConceptA key={`a-${state.sample}`} sampleKey={state.sample} />
          ) : (
            <ConceptB key={`b-${state.sample}`} sampleKey={state.sample} />
          )}
        </main>
      </div>
    </TooltipProvider>
  )
}
