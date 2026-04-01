<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AppShell from '@/components/layout/AppShell.vue'
import RepertoireRecommendationRail from '@/components/recommendations/RepertoireRecommendationRail.vue'
import RepertoireResultCard from '@/components/repertoire/RepertoireResultCard.vue'
import RepertoireSearchForm from '@/components/repertoire/RepertoireSearchForm.vue'
import { useWorkspaceContext } from '@/composables/useWorkspaceContext'
import { cacheScopedRead, loadScopedRead } from '@/offline/readCache'
import { isRetryableQueueError } from '@/offline/writeQueue'
import { fetchRepertoire, fetchRepertoireRecommendations } from '@/services/api'
import type {
  ActiveContext,
  RepertoireItemCard,
  RepertoireRecommendationItem,
  RepertoireSearchResponse,
  RepertoireSearchFilters,
} from '@/types'

const { authStore, contextStore, bootstrapWorkspace, switchWorkspaceContext } = useWorkspaceContext()

const loading = ref(false)
const errorMessage = ref<string | null>(null)
const activeFilters = ref<RepertoireSearchFilters>({})
const results = ref<RepertoireItemCard[]>([])
const total = ref(0)
const recommendations = ref<RepertoireRecommendationItem[]>([])
const recommendationsLoading = ref(false)
const recommendationsError = ref<string | null>(null)
const offlineNotice = ref<string | null>(null)
const usingCachedOfflineData = ref(false)

const scopeKey = computed(() => {
  if (!authStore.user || !contextStore.activeContextKey) {
    return null
  }
  return `${authStore.user.id}:${contextStore.activeContextKey}`
})

function normalizeFilters(filters: RepertoireSearchFilters): RepertoireSearchFilters {
  const normalized: RepertoireSearchFilters = {}

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

function filtersCacheKey(filters: RepertoireSearchFilters): string {
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

function repertoireSearchResource(filters: RepertoireSearchFilters): string {
  return `repertoire_search:${filtersCacheKey(filters)}`
}

function repertoireRecommendationsResource(filters: RepertoireSearchFilters): string {
  return `repertoire_recommendations:${filtersCacheKey(filters)}`
}

async function loadRecommendations(filters: RepertoireSearchFilters = activeFilters.value) {
  recommendationsLoading.value = true
  recommendationsError.value = null
  const normalized = normalizeFilters(filters)
  const recommendationFilters = {
    tags: normalized.tags,
    limit: 6,
  }
  try {
    const payload = await fetchRepertoireRecommendations(recommendationFilters)
    recommendations.value = payload.results
    if (scopeKey.value) {
      cacheScopedRead(scopeKey.value, repertoireRecommendationsResource(normalized), payload.results)
    }
  } catch (error) {
    const canFallback = Boolean(scopeKey.value) && isRetryableQueueError(error)
    if (canFallback) {
      const cachedRecommendations = loadScopedRead<RepertoireRecommendationItem[]>(
        scopeKey.value!,
        repertoireRecommendationsResource(normalized),
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

async function loadRepertoire(filters: RepertoireSearchFilters = activeFilters.value) {
  loading.value = true
  errorMessage.value = null
  offlineNotice.value = null
  usingCachedOfflineData.value = false
  const normalizedFilters = normalizeFilters(filters)
  try {
    const payload = await fetchRepertoire(normalizedFilters)
    results.value = payload.results
    total.value = payload.total
    activeFilters.value = normalizedFilters
    if (scopeKey.value) {
      cacheScopedRead(scopeKey.value, repertoireSearchResource(normalizedFilters), payload)
    }
    await loadRecommendations(normalizedFilters)
  } catch (error) {
    const canFallback = Boolean(scopeKey.value) && isRetryableQueueError(error)
    if (canFallback) {
      const cached = loadScopedRead<RepertoireSearchResponse>(scopeKey.value!, repertoireSearchResource(normalizedFilters))
      if (cached) {
        results.value = cached.results
        total.value = cached.total
        activeFilters.value = normalizedFilters
        usingCachedOfflineData.value = true
        offlineNotice.value = 'Offline: showing cached repertoire results for this context and filter set. Data may be stale.'
        await loadRecommendations(normalizedFilters)
        return
      }
    }
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load repertoire results'
  } finally {
    loading.value = false
  }
}

async function initializePage() {
  loading.value = true
  errorMessage.value = null
  try {
    await bootstrapWorkspace()
    await loadRepertoire(activeFilters.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to initialize repertoire view'
    loading.value = false
  }
}

async function onSearch(filters: RepertoireSearchFilters) {
  await loadRepertoire(filters)
}

async function onSwitchContext(next: ActiveContext) {
  try {
    await switchWorkspaceContext(next)
    await loadRepertoire(activeFilters.value)
  } catch {
    // Context switch errors are surfaced by store state.
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
    <section class="repertoire-page">
      <header class="repertoire-page__header">
        <p class="eyebrow">Repertoire browsing</p>
        <h2>Search repertoire by title, performer linkage, tags, region, and availability overlap.</h2>
        <p>Results are constrained to your current active tenant context.</p>
      </header>

      <section class="repertoire-page__filters">
        <RepertoireSearchForm @search="onSearch" />
      </section>

      <p v-if="contextStore.errorMessage" class="error">{{ contextStore.errorMessage }}</p>
      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      <p v-if="offlineNotice" class="notice" role="status" aria-live="polite" aria-atomic="true">{{ offlineNotice }}</p>
      <p v-if="loading">Loading repertoire…</p>

      <template v-else>
        <p class="repertoire-page__data-source" :class="usingCachedOfflineData ? 'is-cached' : 'is-live'">
          {{ usingCachedOfflineData ? 'Data source: cached offline snapshot' : 'Data source: live context data' }}
        </p>
        <p class="repertoire-page__summary">{{ total }} repertoire item<span v-if="total !== 1">s</span> found.</p>

        <p v-if="total === 0" class="repertoire-page__empty">
          No repertoire items match these filters in the active context.
        </p>

        <div v-else class="repertoire-page__grid">
          <RepertoireResultCard v-for="item in results" :key="item.id" :item="item" />
        </div>

        <RepertoireRecommendationRail
          :items="recommendations"
          :loading="recommendationsLoading"
          :error-message="recommendationsError"
        />
      </template>
    </section>
  </AppShell>
</template>

<style scoped>
.repertoire-page {
  display: grid;
  gap: 1rem;
}

.repertoire-page__header,
.repertoire-page__filters {
  border: 1px solid rgba(21, 39, 61, 0.14);
  border-radius: 1rem;
  padding: 1rem;
  background: rgba(252, 250, 245, 0.92);
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

.repertoire-page__header p {
  margin: 0.2rem 0 0;
  color: #314c6a;
}

.repertoire-page__summary {
  margin: 0;
  color: #294562;
}

.repertoire-page__data-source {
  margin: 0;
  font-size: 0.8rem;
}

.repertoire-page__data-source.is-live {
  color: #0b5e47;
}

.repertoire-page__data-source.is-cached {
  color: #734d00;
}

.repertoire-page__empty {
  margin: 0;
  border: 1px dashed rgba(39, 63, 92, 0.3);
  border-radius: 0.8rem;
  padding: 0.9rem;
  background: rgba(253, 252, 250, 0.85);
  color: #34506d;
}

.repertoire-page__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0.8rem;
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
