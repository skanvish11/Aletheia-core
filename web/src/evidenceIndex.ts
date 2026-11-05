import { createContext, useContext } from 'react'
import type { EvidenceAssessment, EvidenceResponse, SourceSnapshot } from './api/types'

/** One citable evidence entry, numbered in the order the evidence endpoint returns it. */
export interface EvidenceEntry {
  number: number
  assessment: EvidenceAssessment
  source: SourceSnapshot | undefined
}

export type EvidenceIndex = Map<string, EvidenceEntry>

export function buildEvidenceIndex(evidence: EvidenceResponse | null): EvidenceIndex {
  const sources = new Map((evidence?.sources ?? []).map((s) => [s.id, s]))
  return new Map(
    (evidence?.assessments ?? []).map((assessment, i) => [
      assessment.id,
      { number: i + 1, assessment, source: sources.get(assessment.snapshot_id) },
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
