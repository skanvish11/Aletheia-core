import type { SourceRow } from './examples'
import { createContext, useContext } from 'react'
import type { Evidence, EvidenceResponse, ExplanationUnit, SourceSnapshot } from '../api/types'

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
  const numbers = new Map<string, number>()
  return new Map(ordered.map(evidence => {
    const id = evidence.assessment.citation.snapshot_id
    const number = numbers.get(id) ?? numbers.size + 1
    numbers.set(id, number)
    return [evidence.id, { number, evidence, source: sources.get(id) }]
  }))

}

export const EvidenceIndexContext = createContext<EvidenceIndex>(new Map())

export function useEvidenceIndex(): EvidenceIndex {
  return useContext(EvidenceIndexContext)
}

function pageTakeaway(entries: EvidenceEntry[], explanations: ExplanationUnit[]): string | undefined {
  if (!entries.length) return undefined
  const admitted = entries.map(entry => entry.evidence).filter(evidence => evidence.admissible)
  if (!admitted.length) return 'The checked passages from this page were excluded from the verdict.'

  const ids = new Set(admitted.map(evidence => evidence.id))
  const units = explanations.filter(unit => unit.evidence_ids.length && unit.evidence_ids.every(id => ids.has(id)))
  const relations = new Set(admitted.map(evidence => evidence.assessment.relation))
  if (relations.has('supports') && relations.has('contradicts')) {
    return 'Different passages on this page offer conflicting evidence about the claim.'
  }
  // Prefer complete, page-specific findings. Cutting a sentence can drop a crucial qualifier.
  for (const text of [...units.map(unit => unit.text), ...admitted.map(item => item.assessment.rationale)]) {
    const words = text.trim().split(/\s+/).length
    if (words >= 10 && words <= 15) return text.trim()
    if (words >= 5 && words < 10) return 'The finding from this source: ' + text.trim()
  }
  if (relations.has('supports')) return 'The retrieved evidence from this page supports the claim under review.'
  if (relations.has('contradicts')) return 'The retrieved evidence from this page contradicts the claim under review.'
  return 'This page supplies background information without independently resolving the claim under review.'
}

export function reportPages(response: EvidenceResponse, explanations: ExplanationUnit[] = []): SourceRow[] {
  const groups = new Map<string, EvidenceEntry[]>()
  const sources = new Map(response.sources.map(source => [source.id, source]))
  for (const entry of buildEvidenceIndex(response).values()) {
    const key = entry.evidence.assessment.citation.snapshot_id
    const group = groups.get(key) ?? []
    group.push(entry)
    groups.set(key, group)
  }
  for (const id of sources.keys()) {
    if (!groups.has(id)) groups.set(id, [])
  }
  return [...groups].map(([id, entries]) => {
    const source = sources.get(id)
    return {
      title: source?.title || 'Untitled source',
      url: source?.url || '',
      takeaway: pageTakeaway(entries, explanations),
      passages: entries.map(({ evidence }) => ({
        id: evidence.id,
        quote: evidence.excerpts.map(excerpt => excerpt.text).join(' … '),
        note: evidence.admissible ? undefined : evidence.rejection_reason || 'This passage was excluded from the verdict.',
      })),
    }
  })
}
