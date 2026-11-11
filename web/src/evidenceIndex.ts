import { createContext, useContext } from 'react'
import type { Evidence, EvidenceResponse, SourceSnapshot } from './api/types'

/** One citable evidence entry. Admitted evidence is numbered first, in endpoint order. */
export interface EvidenceEntry {
  number: number
  evidence: Evidence
  source: SourceSnapshot | undefined
}

export type EvidenceIndex = Map<string, EvidenceEntry>

export function buildEvidenceIndex(response: EvidenceResponse | null): EvidenceIndex {
  const sources = new Map((response?.sources ?? []).map((s) => [s.id, s]))
  const all = response?.evidence ?? []
  const ordered = [...all.filter((e) => e.admissible), ...all.filter((e) => !e.admissible)]
  return new Map(
    ordered.map((evidence, i) => [
      evidence.id,
      { number: i + 1, evidence, source: sources.get(evidence.assessment.citation.snapshot_id) },
    ]),
  )
}

export const EvidenceIndexContext = createContext<EvidenceIndex>(new Map())

export function useEvidenceIndex(): EvidenceIndex {
  return useContext(EvidenceIndexContext)
}

/** Which evidence entry the evidence pane shows. Citations and pane tabs both set it. */
export interface EvidenceSelection {
  selected: string | null
  /** `reveal` brings the pane into view when it sits below the report (narrow screens). */
  select: (id: string, reveal?: boolean) => void
}

export const EvidenceSelectionContext = createContext<EvidenceSelection>({ selected: null, select: () => {} })

export function useEvidenceSelection(): EvidenceSelection {
  return useContext(EvidenceSelectionContext)
}

export const EVIDENCE_PANE_ID = 'evidence-pane'

/** Matches the CSS breakpoint where the pane stops sitting beside the report. */
const STACKED = '(max-width: 899px)'

export function revealEvidencePane(): void {
  if (typeof window.matchMedia !== 'function' || !window.matchMedia(STACKED).matches) return
  const pane = document.getElementById(EVIDENCE_PANE_ID)
  pane?.scrollIntoView({ block: 'start' })
  pane?.focus({ preventScroll: true })
}

/** The entry to show first: the first one the report cites, else the first admitted. */
export function defaultSelection(index: EvidenceIndex, cited: string[]): string | null {
  return cited.find((id) => index.has(id)) ?? index.keys().next().value ?? null
}
