// @vitest-environment node
/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { EVENT_TYPES } from './types'

// The backend sends named SSE events and EventSource only delivers names the client
// listens for, so an event type missing here is silently dropped. Keep this list in
// step with InvestigationEvent.type in src/aletheia/contracts.py.
const CONTRACTS = new URL('../../../src/aletheia/contracts.py', import.meta.url)

function backendEventTypes(): string[] {
  const source = readFileSync(CONTRACTS, 'utf-8')
  const block = source.match(/class InvestigationEvent\b[\s\S]*?type: Literal\[([\s\S]*?)\]/)
  if (!block) throw new Error('InvestigationEvent.type not found in contracts.py')
  return [...block[1].matchAll(/"([a-z_]+)"/g)].map((m) => m[1])
}

describe('event types', () => {
  it('match the backend contract exactly', () => {
    expect([...EVENT_TYPES].sort()).toEqual(backendEventTypes().sort())
  })
})
