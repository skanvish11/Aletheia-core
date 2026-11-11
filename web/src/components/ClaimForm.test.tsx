// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { liveSource, type DataSource } from '../api/source'
import { HEALTH_TIMEOUT_MS, canRecheck, unavailableReason, useBackendStatus } from '../api/useBackendStatus'
import { ClaimForm } from './ClaimForm'

afterEach(cleanup)

/** The same wiring App uses for the home page's claim form. */
function Harness({ source }: { source: DataSource }) {
  const backend = useBackendStatus(source)
  return (
    <ClaimForm
      onSubmit={() => {}}
      submitting={false}
      unavailableReason={unavailableReason(backend.status)}
      onRetry={canRecheck(backend.status) ? backend.recheck : undefined}
    />
  )
}

describe('claim form backend retry', () => {
  it('enables the claim field after retrying a backend that started late', async () => {
    const health = vi
      .fn()
      .mockRejectedValueOnce(new Error('down'))
      .mockResolvedValue({ status: 'ok', database: 'ok', research_enabled: true })
    render(<Harness source={{ ...liveSource, health }} />)
    await act(async () => {})
    expect(screen.getByLabelText('Claim to check')).toHaveProperty('disabled', true)

    await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Retry connection' })))
    expect(screen.getByLabelText('Claim to check')).toHaveProperty('disabled', false)
    expect(screen.queryByRole('button', { name: 'Retry connection' })).toBeNull()
  })

  it('offers retry again after a stalled check times out, and the retry enables the field', async () => {
    vi.useFakeTimers()
    try {
      const health = vi
        .fn()
        .mockRejectedValueOnce(new Error('down'))
        .mockImplementationOnce(() => new Promise(() => {}))
        .mockResolvedValue({ status: 'ok', database: 'ok', research_enabled: true })
      render(<Harness source={{ ...liveSource, health }} />)
      await act(async () => {})
      await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Retry connection' })))
      expect(screen.queryByRole('button', { name: 'Retry connection' })).toBeNull() // checking

      await act(async () => void vi.advanceTimersByTime(HEALTH_TIMEOUT_MS))
      await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Retry connection' })))
      expect(screen.getByLabelText('Claim to check')).toHaveProperty('disabled', false)
    } finally {
      vi.useRealTimers()
    }
  })

  it('offers no retry while checking or in replay mode', () => {
    render(<Harness source={{ ...liveSource, health: undefined }} />)
    expect(screen.queryByRole('button', { name: 'Retry connection' })).toBeNull()
  })
})
