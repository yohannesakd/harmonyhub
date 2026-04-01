import { defineStore } from 'pinia'
import type { QueuedMutation, SyncStatus } from '@/types'

type SyncState = {
  networkOnline: boolean
  queueStatus: SyncStatus
  pendingCount: number
  lastConflict: string | null
  queueItems: QueuedMutation[]
  listenerInitialized: boolean
}

export const useSyncStore = defineStore('sync', {
  state: (): SyncState => ({
    networkOnline: typeof navigator !== 'undefined' ? navigator.onLine : true,
    queueStatus: 'server_committed',
    pendingCount: 0,
    lastConflict: null,
    queueItems: [],
    listenerInitialized: false,
  }),
  actions: {
    initializeNetworkListener() {
      if (typeof window === 'undefined') {
        return
      }
      if (this.listenerInitialized) {
        return
      }
      this.listenerInitialized = true

      window.addEventListener('online', () => {
        this.networkOnline = true
        if (this.pendingCount > 0) {
          this.queueStatus = 'syncing'
        }
      })
      window.addEventListener('offline', () => {
        this.networkOnline = false
      })
    },
    setQueueSnapshot(status: SyncStatus, pendingCount: number, conflict: string | null = null) {
      this.queueStatus = status
      this.pendingCount = pendingCount
      this.lastConflict = conflict
    },

    setQueueItems(items: QueuedMutation[]) {
      this.queueItems = items
      const conflict = items.find((item) => item.status === 'conflict')
      const pending = items.filter((item) => ['local_queued', 'failed_retrying', 'syncing', 'conflict'].includes(item.status))

      this.pendingCount = pending.length
      this.lastConflict = conflict?.last_error ?? conflict?.conflict?.message ?? null

      if (conflict) {
        this.queueStatus = 'conflict'
        return
      }
      if (pending.some((item) => item.status === 'syncing')) {
        this.queueStatus = 'syncing'
        return
      }
      if (pending.some((item) => item.status === 'failed_retrying')) {
        this.queueStatus = 'failed_retrying'
        return
      }
      if (pending.some((item) => item.status === 'local_queued')) {
        this.queueStatus = 'local_queued'
        return
      }
      this.queueStatus = 'server_committed'
    },
  },
})
