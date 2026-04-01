import { onScopeDispose, toValue, watchEffect, type MaybeRefOrGetter } from 'vue'

type UsePollingIntervalOptions = {
  enabled: MaybeRefOrGetter<boolean>
  intervalMs: number
  task: () => Promise<void> | void
}

export function usePollingInterval(options: UsePollingIntervalOptions) {
  let timer: ReturnType<typeof setInterval> | null = null
  let inFlight = false

  const runTask = async () => {
    if (inFlight) {
      return
    }
    inFlight = true
    try {
      await options.task()
    } finally {
      inFlight = false
    }
  }

  const stop = () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  const start = () => {
    if (timer) {
      return
    }
    void runTask()
    timer = setInterval(() => {
      void runTask()
    }, options.intervalMs)
  }

  watchEffect(() => {
    if (toValue(options.enabled)) {
      start()
    } else {
      stop()
    }
  })

  onScopeDispose(stop)

  return {
    stop,
  }
}
