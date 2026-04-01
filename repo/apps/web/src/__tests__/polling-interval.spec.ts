import { effectScope, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { usePollingInterval } from '@/composables/usePollingInterval'

describe('usePollingInterval', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('runs immediately and continues on interval while enabled', async () => {
    const enabled = ref(true)
    const task = vi.fn().mockResolvedValue(undefined)

    const scope = effectScope()
    scope.run(() => {
      usePollingInterval({
        enabled,
        intervalMs: 5_000,
        task,
      })
    })

    await vi.runAllTicks()
    expect(task).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(5_200)
    expect(task).toHaveBeenCalledTimes(2)

    scope.stop()
  })

  it('stops polling when enabled toggles off', async () => {
    const enabled = ref(true)
    const task = vi.fn().mockResolvedValue(undefined)

    const scope = effectScope()
    scope.run(() => {
      usePollingInterval({
        enabled,
        intervalMs: 4_000,
        task,
      })
    })

    await vi.runAllTicks()
    expect(task).toHaveBeenCalledTimes(1)

    enabled.value = false
    await vi.runAllTicks()

    await vi.advanceTimersByTimeAsync(8_500)
    expect(task).toHaveBeenCalledTimes(1)

    scope.stop()
  })
})
