<script setup lang="ts">
import { computed } from 'vue'
import { useSyncStore } from '@/stores/sync'

const syncStore = useSyncStore()

const label = computed(() => {
  if (!syncStore.networkOnline) {
    return 'Offline mode'
  }

  switch (syncStore.queueStatus) {
    case 'syncing':
      return `Syncing ${syncStore.pendingCount} actions`
    case 'local_queued':
      return `${syncStore.pendingCount} queued`
    case 'conflict':
      return 'Sync conflict needs review'
    case 'failed_retrying':
      return 'Retrying failed sync'
    default:
      return 'In sync'
  }
})

const tone = computed(() => {
  if (!syncStore.networkOnline) return 'is-offline'
  if (syncStore.queueStatus === 'conflict') return 'is-conflict'
  if (syncStore.queueStatus === 'syncing' || syncStore.queueStatus === 'local_queued') return 'is-pending'
  return 'is-ok'
})
</script>

<template>
  <span
    class="sync-badge"
    :class="tone"
    :title="syncStore.lastConflict ?? undefined"
    role="status"
    aria-live="polite"
    aria-atomic="true"
  >
    {{ label }}
  </span>
</template>

<style scoped>
.sync-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-size: 0.75rem;
  letter-spacing: 0.03em;
  border: 1px solid transparent;
}

.is-ok {
  color: #0b5e47;
  background: rgba(34, 197, 94, 0.15);
  border-color: rgba(34, 197, 94, 0.4);
}

.is-pending {
  color: #734d00;
  background: rgba(250, 204, 21, 0.2);
  border-color: rgba(250, 204, 21, 0.4);
}

.is-conflict {
  color: #6a0f1b;
  background: rgba(244, 63, 94, 0.2);
  border-color: rgba(244, 63, 94, 0.4);
}

.is-offline {
  color: #203a64;
  background: rgba(56, 189, 248, 0.2);
  border-color: rgba(56, 189, 248, 0.4);
}
</style>
