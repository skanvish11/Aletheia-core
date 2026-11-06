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

export function evidenceAnchor(id: string): string {
  return `evidence-${id}`
}
