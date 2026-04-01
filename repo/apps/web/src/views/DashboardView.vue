<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import EventContextCard from '@/components/dashboard/EventContextCard.vue'
import AppShell from '@/components/layout/AppShell.vue'
import { cacheScopedRead, loadScopedRead } from '@/offline/readCache'
import { isRetryableQueueError } from '@/offline/writeQueue'
import { fetchDashboard } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { useContextStore } from '@/stores/context'
import { useSyncStore } from '@/stores/sync'
import type { ActiveContext, DashboardResponse } from '@/types'

const authStore = useAuthStore()
const contextStore = useContextStore()
const syncStore = useSyncStore()

const loading = ref(false)
const dashboard = ref<DashboardResponse | null>(null)
const error = ref<string | null>(null)
const offlineNotice = ref<string | null>(null)

const maskedContactPreview = computed(() => 'a***@domain.com · ***-***-1234')

async function loadPage() {
  loading.value = true
  error.value = null
  offlineNotice.value = null
  try {
    await authStore.bootstrap()
    contextStore.syncFromAuthStore()
    await contextStore.loadContexts()
    const cacheScope = authStore.user
      ? `${authStore.user.id}:${contextStore.activeContextKey || 'no-context'}`
      : null

    try {
      dashboard.value = await fetchDashboard()
      if (cacheScope && dashboard.value) {
        cacheScopedRead(cacheScope, 'dashboard', dashboard.value)
      }
    } catch (fetchError) {
      if (!cacheScope || !isRetryableQueueError(fetchError)) {
        throw fetchError
      }
      const cached = loadScopedRead<DashboardResponse>(cacheScope, 'dashboard')
      if (!cached) {
        throw fetchError
      }
      dashboard.value = cached
      offlineNotice.value = 'Offline: using recently cached dashboard data.'
    }

    syncStore.setQueueItems(syncStore.queueItems)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load dashboard'
  } finally {
    loading.value = false
  }
}

async function handleSwitchContext(next: ActiveContext) {
  try {
    await contextStore.switchContext(next)
    await loadPage()
  } catch {
    // Context error is surfaced by store state.
  }
}

onMounted(loadPage)
</script>

<template>
  <AppShell
    :contexts="contextStore.contexts"
    :active-context="contextStore.activeContext"
    :switching-context="contextStore.switching"
    @switch-context="handleSwitchContext"
  >
    <section class="dashboard">
      <header class="dashboard__header">
        <h2>Event operations dashboard</h2>
        <p>Role-aware operations overview with policy masking and sync status indicators.</p>
      </header>

      <p v-if="loading">Loading dashboard…</p>
      <p v-else-if="error" class="error">{{ error }}</p>
      <p v-else-if="offlineNotice" class="notice">{{ offlineNotice }}</p>

      <template v-if="!loading && !error && dashboard">
        <div class="dashboard__grid">
          <EventContextCard title="Organization" :value="dashboard.organization_name" />
          <EventContextCard title="Event" :value="dashboard.event_name" />
          <EventContextCard title="Kitchen" :value="dashboard.store_name" />
          <EventContextCard title="Role" :value="dashboard.user_role" />
        </div>

        <section class="dashboard__section">
          <h3>Authorization baseline</h3>
          <p><strong>ABAC status:</strong> {{ dashboard.abac_enforced ? 'Enforced' : 'Not enforced for this surface' }}</p>
          <p><strong>Permissions:</strong> {{ dashboard.permissions.join(', ') }}</p>
        </section>

        <section class="dashboard__section">
          <h3>Policy masking status</h3>
          <p>Directory contact fields remain masked by default unless policy permits access:</p>
          <code>{{ maskedContactPreview }}</code>
        </section>

        <section class="dashboard__section">
          <h3>Operations notes</h3>
          <ul>
            <li v-for="note in dashboard.notes" :key="note">{{ note }}</li>
          </ul>
        </section>
      </template>
    </section>
  </AppShell>
</template>

<style scoped>
.dashboard {
  display: grid;
  gap: 1rem;
}

.dashboard__header {
  border: 1px solid rgba(20, 36, 57, 0.14);
  border-radius: 1rem;
  padding: 1rem;
  background: rgba(250, 248, 242, 0.95);
}

.dashboard__header h2 {
  margin: 0;
  font-family: 'Fraunces', serif;
}

.dashboard__header p {
  margin: 0.45rem 0 0;
  color: #2f476a;
}

.dashboard__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 0.8rem;
}

.dashboard__section {
  border: 1px solid rgba(21, 36, 58, 0.16);
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.85);
  padding: 1rem;
}

h3 {
  margin: 0;
}

code {
  display: inline-block;
  margin-top: 0.5rem;
  background: rgba(17, 37, 67, 0.1);
  padding: 0.35rem 0.5rem;
  border-radius: 0.45rem;
}

.error {
  color: #8a1e35;
}

.notice {
  color: #34506e;
}
</style>
