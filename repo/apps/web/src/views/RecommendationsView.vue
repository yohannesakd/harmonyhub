<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AppShell from '@/components/layout/AppShell.vue'
import PairingRuleManager from '@/components/recommendations/PairingRuleManager.vue'
import RecommendationConfigEditor from '@/components/recommendations/RecommendationConfigEditor.vue'
import { useWorkspaceContext } from '@/composables/useWorkspaceContext'
import {
  createAllowlistRule,
  createBlocklistRule,
  deletePairingRule,
  fetchDirectory,
  fetchRecommendationConfig,
  fetchRepertoire,
  listPairingRules,
  updateRecommendationConfig,
} from '@/services/api'
import type {
  ActiveContext,
  DirectoryEntryCard,
  PairingRule,
  RecommendationConfig,
  RecommendationConfigUpdate,
  RecommendationScopeType,
  RepertoireItemCard,
} from '@/types'

const { authStore, contextStore, bootstrapWorkspace, switchWorkspaceContext } = useWorkspaceContext()

const loading = ref(false)
const savingConfig = ref(false)
const savingRules = ref(false)
const errorMessage = ref<string | null>(null)
const selectedScope = ref<RecommendationScopeType>('event_store')
const config = ref<RecommendationConfig | null>(null)
const rules = ref<PairingRule[]>([])
const directoryEntries = ref<DirectoryEntryCard[]>([])
const repertoireItems = ref<RepertoireItemCard[]>([])

const canManage = computed(() => authStore.permissions.includes('recommendations.manage'))

async function loadPageData() {
  loading.value = true
  errorMessage.value = null
  try {
    await bootstrapWorkspace()
    const [configPayload, rulesPayload, directoryPayload, repertoirePayload] = await Promise.all([
      fetchRecommendationConfig(selectedScope.value),
      listPairingRules(),
      fetchDirectory({}),
      fetchRepertoire({}),
    ])
    config.value = configPayload
    rules.value = rulesPayload
    directoryEntries.value = directoryPayload.results
    repertoireItems.value = repertoirePayload.results
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load recommendations management data'
  } finally {
    loading.value = false
  }
}

async function handleSwitchContext(next: ActiveContext) {
  try {
    await switchWorkspaceContext(next)
    await loadPageData()
  } catch {
    // Context errors surfaced from store.
  }
}

async function handleScopeSelection(scope: RecommendationScopeType) {
  selectedScope.value = scope
  try {
    config.value = await fetchRecommendationConfig(scope)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load selected scope config'
  }
}

async function handleSaveConfig(payload: RecommendationConfigUpdate) {
  savingConfig.value = true
  errorMessage.value = null
  try {
    config.value = await updateRecommendationConfig(payload)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to save recommendation config'
  } finally {
    savingConfig.value = false
  }
}

async function handleCreateAllow(payload: { directory_entry_id: string; repertoire_item_id: string; note?: string }) {
  savingRules.value = true
  errorMessage.value = null
  try {
    await createAllowlistRule(payload)
    rules.value = await listPairingRules()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to create allowlist rule'
  } finally {
    savingRules.value = false
  }
}

async function handleCreateBlock(payload: { directory_entry_id: string; repertoire_item_id: string; note?: string }) {
  savingRules.value = true
  errorMessage.value = null
  try {
    await createBlocklistRule(payload)
    rules.value = await listPairingRules()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to create blocklist rule'
  } finally {
    savingRules.value = false
  }
}

async function handleDeleteRule(ruleId: string) {
  savingRules.value = true
  errorMessage.value = null
  try {
    await deletePairingRule(ruleId)
    rules.value = await listPairingRules()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to delete pairing rule'
  } finally {
    savingRules.value = false
  }
}

onMounted(loadPageData)
</script>

<template>
  <AppShell
    :contexts="contextStore.contexts"
    :active-context="contextStore.activeContext"
    :switching-context="contextStore.switching"
    @switch-context="handleSwitchContext"
  >
    <section class="recommendations-page">
      <header class="recommendations-page__header">
        <p class="eyebrow">Recommendations controls</p>
        <h2>Recommendation management for delegated scoring, featured pins, and pairing rules.</h2>
        <p>This management surface requires recommendation-manage permissions in the active context.</p>
      </header>

      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      <p v-if="contextStore.errorMessage" class="error">{{ contextStore.errorMessage }}</p>
      <p v-if="loading">Loading recommendation controls…</p>

      <template v-else>
        <RecommendationConfigEditor
          :config="config"
          :can-manage="canManage"
          :loading="loading"
          :saving="savingConfig"
          @select-scope="handleScopeSelection"
          @save="handleSaveConfig"
        />

        <PairingRuleManager
          :can-manage="canManage"
          :rules="rules"
          :directory-entries="directoryEntries"
          :repertoire-items="repertoireItems"
          :loading="loading"
          :saving="savingRules"
          @create-allow="handleCreateAllow"
          @create-block="handleCreateBlock"
          @delete-rule="handleDeleteRule"
        />
      </template>
    </section>
  </AppShell>
</template>

<style scoped>
.recommendations-page {
  display: grid;
  gap: 1rem;
}

.recommendations-page__header {
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

.recommendations-page__header p {
  margin: 0.2rem 0 0;
  color: #314c6a;
}

.error {
  margin: 0;
  color: #8a1e35;
}
</style>
