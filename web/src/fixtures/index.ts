import type { EvidenceResponse, Investigation, InvestigationEvent } from '../api/types'
import { sampleMisleadingComparison } from './sample-misleading-comparison'

/** An exported investigation the client can replay without a backend. */
export interface Recording {
  label: string
  /** True for invented development data; the UI says so on screen. */
  sample: boolean
  investigation: Investigation
  evidence: EvidenceResponse
  events: InvestigationEvent[]
}

export const RECORDINGS: Recording[] = [sampleMisleadingComparison]
