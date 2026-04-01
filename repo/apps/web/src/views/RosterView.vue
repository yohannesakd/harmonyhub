<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AppShell from '@/components/layout/AppShell.vue'
import { useWorkspaceContext } from '@/composables/useWorkspaceContext'
import { fetchDirectory } from '@/services/api'
import type { ActiveContext, DirectoryEntryCard } from '@/types'

const { authStore, contextStore, bootstrapWorkspace, switchWorkspaceContext } = useWorkspaceContext()

const loading = ref(false)
const errorMessage = ref<string | null>(null)
const searchTerm = ref('')
const rosterEntries = ref<DirectoryEntryCard[]>([])
const total = ref(0)

const isRefereeRole = computed(() => authStore.activeContext?.role === 'referee')

async function loadRoster() {
  loading.value = true
  errorMessage.value = null
  try {
    const payload = await fetchDirectory({ q: searchTerm.value.trim() || undefined })
    rosterEntries.value = payload.results
    total.value = payload.total
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load roster'
  } finally {
    loading.value = false
  }
}

async function initializePage() {
  loading.value = true
  errorMessage.value = null
  try {
    await bootstrapWorkspace()
    await loadRoster()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to initialize roster visibility'
    loading.value = false
  }
}

async function handleSwitchContext(next: ActiveContext) {
  try {
    await switchWorkspaceContext(next)
    await loadRoster()
  } catch {
    // Context errors surfaced by store.
  }
}

async function handleSearch() {
  await loadRoster()
}

onMounted(initializePage)
</script>

<template>
  <AppShell
    :contexts="contextStore.contexts"
    :active-context="contextStore.activeContext"
    :switching-context="contextStore.switching"
    @switch-context="handleSwitchContext"
  >
    <section class="roster-page">
      <header class="roster-page__header">
        <p class="eyebrow">Roster visibility</p>
        <h2>View the active event roster within your current role boundary.</h2>
        <p v-if="isRefereeRole">
          Referee access is intentionally limited to roster identity, region, tags, and repertoire context.
        </p>
        <p v-else>Use this roster surface for quick event visibility without exposing full profile/contact details.</p>
      </header>

      <form class="roster-page__search" @submit.prevent="handleSearch">
        <label>
          Search roster
          <input v-model="searchTerm" :disabled="loading" placeholder="Name, stage alias, repertoire" />
        </label>
        <button type="submit" :disabled="loading">Search</button>
      </form>

      <p v-if="contextStore.errorMessage" class="error">{{ contextStore.errorMessage }}</p>
      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      <p v-if="loading">Loading roster…</p>

      <template v-else>
        <p class="roster-page__summary">{{ total }} roster entr{{ total === 1 ? 'y' : 'ies' }} in active context.</p>

        <ul v-if="rosterEntries.length > 0" class="roster-page__list">
          <li v-for="entry in rosterEntries" :key="entry.id" class="roster-page__item">
            <div>
              <h3>{{ entry.display_name }}</h3>
              <p v-if="entry.stage_name">Stage name: {{ entry.stage_name }}</p>
              <p>Region: {{ entry.region }}</p>
            </div>
            <div>
              <p><strong>Repertoire:</strong> {{ entry.repertoire.join(', ') || '—' }}</p>
              <p><strong>Tags:</strong> {{ entry.tags.join(', ') || '—' }}</p>
            </div>
          </li>
        </ul>
        <p v-else class="roster-page__empty">No roster entries matched your current filters.</p>
      </template>
    </section>
  </AppShell>
</template>

<style scoped>
.roster-page {
  display: grid;
  gap: 1rem;
}

.roster-page__header,
.roster-page__search,
.roster-page__summary,
.roster-page__empty {
  border: 1px solid rgba(21, 39, 61, 0.14);
  border-radius: 1rem;
  padding: 1rem;
  background: rgba(251, 250, 246, 0.92);
}

.eyebrow {
  margin: 0;
  font-size: 0.73rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #2a4f75;
}

h2 {
  margin: 0.35rem 0;
}

.roster-page__header p {
  margin: 0.2rem 0 0;
  color: #314c6a;
}

.roster-page__search {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  align-items: end;
}

.roster-page__search label {
  display: grid;
  gap: 0.3rem;
  min-width: min(420px, 100%);
}

.roster-page__search input {
  border: 1px solid rgba(30, 51, 76, 0.18);
  border-radius: 0.55rem;
  padding: 0.52rem 0.6rem;
  background: rgba(255, 255, 255, 0.95);
}

.roster-page__search button {
  border: none;
  border-radius: 0.55rem;
  padding: 0.52rem 0.76rem;
  background: #1e4c7d;
  color: #fff;
  cursor: pointer;
}

.roster-page__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.75rem;
}

.roster-page__item {
  border: 1px solid rgba(16, 36, 61, 0.16);
  border-radius: 0.9rem;
  background: rgba(255, 255, 255, 0.92);
  padding: 0.9rem;
  display: grid;
  gap: 0.6rem;
}

.roster-page__item h3 {
  margin: 0;
}

.roster-page__item p,
.roster-page__summary,
.roster-page__empty {
  margin: 0;
  color: #2e4762;
}

.error {
  margin: 0;
  color: #8a1e35;
}
</style>
