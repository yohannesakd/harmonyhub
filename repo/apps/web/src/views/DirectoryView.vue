<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import DirectoryResultCard from '@/components/directory/DirectoryResultCard.vue'
import DirectorySearchForm from '@/components/directory/DirectorySearchForm.vue'
import AppShell from '@/components/layout/AppShell.vue'
import DirectoryRecommendationRail from '@/components/recommendations/DirectoryRecommendationRail.vue'
import { useWorkspaceContext } from '@/composables/useWorkspaceContext'
import { cacheScopedRead, loadScopedRead } from '@/offline/readCache'
import { isRetryableQueueError } from '@/offline/writeQueue'
import {
  fetchDirectory,
  fetchDirectoryRecommendations,
  pinFeaturedTarget,
  revealDirectoryContact,
  unpinFeaturedTarget,
} from '@/services/api'
import type {
  ActiveContext,
  DirectoryEntryCard,
  DirectoryRecommendationItem,
  DirectorySearchFilters,
  DirectorySearchResponse,
} from '@/types'

const { authStore, contextStore, bootstrapWorkspace, switchWorkspaceContext } = useWorkspaceContext()

const loading = ref(false)
const errorMessage = ref<string | null>(null)
const results = ref<DirectoryEntryCard[]>([])
const total = ref(0)
const activeFilters = ref<DirectorySearchFilters>({})
const revealErrorMessage = ref<string | null>(null)
const revealingById = ref<Record<string, boolean>>({})
const recommendations = ref<DirectoryRecommendationItem[]>([])
const recommendationsLoading = ref(false)
const recommendationsError = ref<string | null>(null)
const pinningIds = ref<string[]>([])
const offlineNotice = ref<string | null>(null)
const usingCachedOfflineData = ref(false)

const hasRevealPermission = computed(() => authStore.permissions.includes('directory.contact.reveal'))
const canManageRecommendations = computed(() => authStore.permissions.includes('recommendations.manage'))
const scopeKey = computed(() => {
  if (!authStore.user || !contextStore.activeContextKey) {
    return null
  }
  return `${authStore.user.id}:${contextStore.activeContextKey}`
})

function normalizeFilters(filters: DirectorySearchFilters): DirectorySearchFilters {
  const normalized: DirectorySearchFilters = {}

  if (filters.q?.trim()) {
    normalized.q = filters.q.trim()
  }
  if (filters.actor?.trim()) {
    normalized.actor = filters.actor.trim()
  }
  if (filters.repertoire?.trim()) {
    normalized.repertoire = filters.repertoire.trim()
  }
  if (filters.region?.trim()) {
    normalized.region = filters.region.trim()
  }
  if (filters.availability_start?.trim()) {
    normalized.availability_start = filters.availability_start.trim()
  }
  if (filters.availability_end?.trim()) {
    normalized.availability_end = filters.availability_end.trim()
  }

  const tags = (filters.tags ?? []).map((tag) => tag.trim()).filter((tag) => tag.length > 0)
  if (tags.length > 0) {
    normalized.tags = tags
  }

  return normalized
}

function filtersCacheKey(filters: DirectorySearchFilters): string {
  const normalized = normalizeFilters(filters)
  return [
    `q=${normalized.q ?? ''}`,
    `actor=${normalized.actor ?? ''}`,
    `repertoire=${normalized.repertoire ?? ''}`,
    `region=${normalized.region ?? ''}`,
    `availability_start=${normalized.availability_start ?? ''}`,
    `availability_end=${normalized.availability_end ?? ''}`,
    `tags=${(normalized.tags ?? []).join('|')}`,
  ].join('&')
}

function directorySearchResource(filters: DirectorySearchFilters): string {
  return `directory_search:${filtersCacheKey(filters)}`
}

function directoryRecommendationsResource(filters: DirectorySearchFilters): string {
  return `directory_recommendations:${filtersCacheKey(filters)}`
}

async function loadRecommendations(filters: DirectorySearchFilters = activeFilters.value) {
  recommendationsLoading.value = true
  recommendationsError.value = null
  const normalized = normalizeFilters(filters)
  const recommendationFilters = {
    tags: normalized.tags,
    limit: 6,
  }
  try {
    const payload = await fetchDirectoryRecommendations(recommendationFilters)
    recommendations.value = payload.results
    if (scopeKey.value) {
      cacheScopedRead(scopeKey.value, directoryRecommendationsResource(normalized), payload.results)
    }
  } catch (error) {
    const canFallback = Boolean(scopeKey.value) && isRetryableQueueError(error)
    if (canFallback) {
      const cachedRecommendations = loadScopedRead<DirectoryRecommendationItem[]>(
        scopeKey.value!,
        directoryRecommendationsResource(normalized),
      )
      if (cachedRecommendations) {
        recommendations.value = cachedRecommendations
        recommendationsError.value = 'Offline: showing cached recommendation rail data.'
        return
      }
    }
    recommendationsError.value = error instanceof Error ? error.message : 'Unable to load recommendations'
  } finally {
    recommendationsLoading.value = false
  }
}

async function loadDirectory(filters: DirectorySearchFilters = activeFilters.value) {
  loading.value = true
  errorMessage.value = null
  revealErrorMessage.value = null
  offlineNotice.value = null
  usingCachedOfflineData.value = false
  const normalizedFilters = normalizeFilters(filters)
  try {
    const payload = await fetchDirectory(normalizedFilters)
    results.value = payload.results
    total.value = payload.total
    activeFilters.value = normalizedFilters
    if (scopeKey.value) {
      cacheScopedRead(scopeKey.value, directorySearchResource(normalizedFilters), payload)
    }
    await loadRecommendations(normalizedFilters)
  } catch (error) {
    const canFallback = Boolean(scopeKey.value) && isRetryableQueueError(error)
    if (canFallback) {
      const cached = loadScopedRead<DirectorySearchResponse>(scopeKey.value!, directorySearchResource(normalizedFilters))
      if (cached) {
        results.value = cached.results
        total.value = cached.total
        activeFilters.value = normalizedFilters
        usingCachedOfflineData.value = true
        offlineNotice.value = 'Offline: showing cached directory results for this context and filter set. Data may be stale.'
        await loadRecommendations(normalizedFilters)
        return
      }
    }
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load directory results'
  } finally {
    loading.value = false
  }
}

async function initializePage() {
  loading.value = true
  errorMessage.value = null
  try {
    await bootstrapWorkspace()
    await loadDirectory(activeFilters.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to initialize directory'
    loading.value = false
  }
}

async function onSearch(filters: DirectorySearchFilters) {
  await loadDirectory(filters)
}

async function onSwitchContext(next: ActiveContext) {
  try {
    await switchWorkspaceContext(next)
    await loadDirectory(activeFilters.value)
  } catch {
    // Context switch errors are surfaced by store state.
  }
}

async function onRevealContact(entryId: string) {
  revealErrorMessage.value = null
  revealingById.value[entryId] = true
  try {
    const payload = await revealDirectoryContact(entryId)
    results.value = results.value.map((entry) =>
      entry.id === payload.entry_id
        ? {
            ...entry,
            contact: payload.contact,
          }
        : entry,
    )
  } catch (error) {
    revealErrorMessage.value = error instanceof Error ? error.message : 'Unable to reveal contact details'
  } finally {
    revealingById.value[entryId] = false
  }
}

async function pinEntry(entryId: string) {
  pinningIds.value = [...pinningIds.value, entryId]
  try {
    await pinFeaturedTarget(entryId, { surface: 'directory' })
    await loadRecommendations()
  } catch (error) {
    revealErrorMessage.value = error instanceof Error ? error.message : 'Unable to pin entry'
  } finally {
    pinningIds.value = pinningIds.value.filter((id) => id !== entryId)
  }
}

async function unpinEntry(entryId: string) {
  pinningIds.value = [...pinningIds.value, entryId]
  try {
    await unpinFeaturedTarget(entryId, 'directory')
    await loadRecommendations()
  } catch (error) {
    revealErrorMessage.value = error instanceof Error ? error.message : 'Unable to unpin entry'
  } finally {
    pinningIds.value = pinningIds.value.filter((id) => id !== entryId)
  }
}

onMounted(initializePage)
</script>

<template>
  <AppShell
    :contexts="contextStore.contexts"
    :active-context="contextStore.activeContext"
    :switching-context="contextStore.switching"
    @switch-context="onSwitchContext"
  >
    <section class="directory-page">
      <header class="directory-page__header">
        <p class="eyebrow">Directory search</p>
        <h2>Find performers by repertoire, region, tags, and availability windows.</h2>
        <p>
          Active scope is enforced from your current tenant context. Contact fields remain masked by default.
          <span v-if="hasRevealPermission">Your role can request explicit reveal.</span>
        </p>
      </header>

      <section class="directory-page__filters">
        <DirectorySearchForm @search="onSearch" />
      </section>

      <p v-if="contextStore.errorMessage" class="error">{{ contextStore.errorMessage }}</p>
      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      <p v-if="revealErrorMessage" class="error">{{ revealErrorMessage }}</p>
      <p v-if="offlineNotice" class="notice" role="status" aria-live="polite" aria-atomic="true">{{ offlineNotice }}</p>
      <p v-if="loading">Loading directory results…</p>

      <template v-else>
        <p class="directory-page__data-source" :class="usingCachedOfflineData ? 'is-cached' : 'is-live'">
          {{ usingCachedOfflineData ? 'Data source: cached offline snapshot' : 'Data source: live context data' }}
        </p>
        <p class="directory-page__summary">{{ total }} result<span v-if="total !== 1">s</span> in active context.</p>

        <p v-if="total === 0" class="directory-page__empty">
          No directory entries matched your filters. Try broadening tags, region, or availability bounds.
        </p>

        <div v-else class="directory-page__grid">
          <DirectoryResultCard
            v-for="entry in results"
            :key="entry.id"
            :entry="entry"
            :revealing="Boolean(revealingById[entry.id])"
            @reveal="onRevealContact"
          />
        </div>

        <DirectoryRecommendationRail
          :items="recommendations"
          :loading="recommendationsLoading"
          :error-message="recommendationsError"
          :can-manage="canManageRecommendations"
          :pinning-ids="pinningIds"
          @pin="pinEntry"
          @unpin="unpinEntry"
        />
      </template>
    </section>
  </AppShell>
</template>

<style scoped>
.directory-page {
  display: grid;
  gap: 1rem;
}

.directory-page__header,
.directory-page__filters {
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
  font-family: 'Fraunces', serif;
}

.directory-page__header p {
  margin: 0.2rem 0 0;
  color: #314c6a;
}

.directory-page__summary {
  margin: 0;
  color: #294562;
}

.directory-page__data-source {
  margin: 0;
  font-size: 0.8rem;
}

.directory-page__data-source.is-live {
  color: #0b5e47;
}

.directory-page__data-source.is-cached {
  color: #734d00;
}

.directory-page__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0.8rem;
}

.directory-page__empty {
  margin: 0;
  border: 1px dashed rgba(39, 63, 92, 0.3);
  border-radius: 0.8rem;
  padding: 0.9rem;
  background: rgba(253, 252, 250, 0.85);
  color: #34506d;
}

.error {
  margin: 0;
  color: #8a1e35;
}

.notice {
  margin: 0;
  color: #34506e;
}
</style>
