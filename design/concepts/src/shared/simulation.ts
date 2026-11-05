import { useCallback, useEffect, useRef, useState } from 'react'
import { SAMPLES, type Sample } from '@/data/samples'

export type Phase = 'entry' | 'submitting' | 'researching' | 'done'

const SUBMIT_MS = 700
const STEP_MS = 650

/**
 * SIMULATED research run for design review. Whatever the user types, it plays
 * back the selected sample. Every concept labels this on screen.
 */
export function useSimulatedRun(sampleKey: string) {
  const [phase, setPhase] = useState<Phase>('entry')
  const [steps, setSteps] = useState(0)
  const [typed, setTyped] = useState('')
  const timers = useRef<number[]>([])
  // Play the sample whose claim was typed or picked; otherwise the toolbar's sample.
  const matched = SAMPLES.find((s) => s.claim === typed.trim())
  const sample: Sample = matched ?? SAMPLES.find((s) => s.key === sampleKey) ?? SAMPLES[0]

  const clear = () => {
    timers.current.forEach((t) => window.clearTimeout(t))
    timers.current = []
  }
  useEffect(() => clear, [])

  const reset = useCallback(() => {
    clear()
    setPhase('entry')
    setSteps(0)
    setTyped('')
  }, [])

  const start = useCallback(
    (text: string) => {
      clear()
      const playing = SAMPLES.find((s) => s.claim === text.trim()) ?? SAMPLES.find((s) => s.key === sampleKey) ?? SAMPLES[0]
      setTyped(text)
      setSteps(0)
      setPhase('submitting')
      timers.current.push(window.setTimeout(() => setPhase('researching'), SUBMIT_MS))
      playing.steps.forEach((_, i) => {
        timers.current.push(window.setTimeout(() => setSteps(i + 1), SUBMIT_MS + (i + 1) * STEP_MS))
      })
      timers.current.push(
        window.setTimeout(() => setPhase('done'), SUBMIT_MS + (playing.steps.length + 1) * STEP_MS),
      )
    },
    [sampleKey],
  )

  /** Jump straight to the answer, for reviewers who don't want to wait. */
  const skip = useCallback(() => {
    clear()
    setSteps(sample.steps.length)
    setPhase('done')
  }, [sample])

  // Changing the sample remounts the concept (App keys it by sample), which restarts it.

  /** Whether what was typed differs from the sample being played back. */
  const substituted = typed.trim() !== '' && typed.trim() !== sample.claim

  return { phase, steps, sample, typed, substituted, start, reset, skip }
}

/** True at the desktop breakpoint, where evidence opens in a side panel. */
export function useIsDesktop(query = '(min-width: 1024px)') {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const mql = window.matchMedia(query)
    const onChange = () => setMatches(mql.matches)
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [query])
  return matches
}
