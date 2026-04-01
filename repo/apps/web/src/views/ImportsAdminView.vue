<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AccountControlPanel from '@/components/imports/AccountControlPanel.vue'
import DuplicateReviewPanel from '@/components/imports/DuplicateReviewPanel.vue'
import ImportBatchManager from '@/components/imports/ImportBatchManager.vue'
import AppShell from '@/components/layout/AppShell.vue'
import { useWorkspaceContext } from '@/composables/useWorkspaceContext'
import {
  applyImportBatch,
  freezeAccount,
  getImportBatchDetail,
  ignoreImportDuplicate,
  listAccounts,
  listImportBatches,
  listImportDuplicates,
  mergeImportDuplicate,
  normalizeImportBatch,
  undoImportMerge,
  unfreezeAccount,
  uploadImportBatch,
} from '@/services/api'
import type { AccountStatus, ActiveContext, ImportBatch, ImportBatchDetail, ImportDuplicateCandidate, ImportKind } from '@/types'

const { authStore, contextStore, bootstrapWorkspace, switchWorkspaceContext } = useWorkspaceContext()

const loading = ref(false)
const acting = ref(false)
const errorMessage = ref<string | null>(null)
const batches = ref<ImportBatch[]>([])
const selectedBatch = ref<ImportBatchDetail | null>(null)
const duplicates = ref<ImportDuplicateCandidate[]>([])
const users = ref<AccountStatus[]>([])

const canManageImports = computed(() => authStore.permissions.includes('imports.manage'))
const canManageAccounts = computed(() => authStore.permissions.includes('account_control.manage'))

async function loadBatches() {
  if (!canManageImports.value) {
    batches.value = []
    selectedBatch.value = null
    duplicates.value = []
    return
  }
  batches.value = await listImportBatches()
  duplicates.value = await listImportDuplicates(['open', 'undo_applied', 'merged'])
}

async function loadUsers() {
  if (!canManageAccounts.value) {
    users.value = []
    return
  }
  users.value = await listAccounts()
}

async function loadPage() {
  loading.value = true
  errorMessage.value = null
  try {
    await bootstrapWorkspace()
    await Promise.all([loadBatches(), loadUsers()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load import/account controls'
  } finally {
    loading.value = false
  }
}

async function handleSwitchContext(next: ActiveContext) {
  try {
    await switchWorkspaceContext(next)
    await loadPage()
  } catch {
    // Context-switch error already surfaced in context store.
  }
}

async function runAction(action: () => Promise<void>, fallbackError: string) {
  acting.value = true
  errorMessage.value = null
  try {
    await action()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : fallbackError
  } finally {
    acting.value = false
  }
}

async function handleUploadBatch(payload: { kind: ImportKind; file: File }) {
  await runAction(async () => {
    await uploadImportBatch(payload.kind, payload.file)
    await loadBatches()
  }, 'Upload failed')
}

async function handleSelectBatch(batchId: string) {
  await runAction(async () => {
    selectedBatch.value = await getImportBatchDetail(batchId)
  }, 'Unable to load batch detail')
}

async function handleNormalizeBatch(batchId: string) {
  await runAction(async () => {
    const updated = await normalizeImportBatch(batchId)
    await loadBatches()
    selectedBatch.value = await getImportBatchDetail(updated.id)
  }, 'Normalize failed')
}

async function handleApplyBatch(batchId: string) {
  await runAction(async () => {
    const updated = await applyImportBatch(batchId)
    await loadBatches()
    selectedBatch.value = await getImportBatchDetail(updated.id)
  }, 'Apply failed')
}

async function handleMergeDuplicate(payload: { duplicateId: string; note?: string }) {
  await runAction(async () => {
    await mergeImportDuplicate(payload.duplicateId, payload.note)
    await loadBatches()
  }, 'Merge failed')
}

async function handleIgnoreDuplicate(duplicateId: string) {
  await runAction(async () => {
    await ignoreImportDuplicate(duplicateId)
    await loadBatches()
  }, 'Ignore duplicate failed')
}

async function handleUndoMerge(payload: { mergeActionId: string; reason?: string }) {
  await runAction(async () => {
    await undoImportMerge(payload.mergeActionId, payload.reason)
    await loadBatches()
  }, 'Undo merge failed')
}

async function handleFreeze(payload: { userId: string; reason: string }) {
  await runAction(async () => {
    await freezeAccount(payload.userId, payload.reason)
    await loadUsers()
  }, 'Freeze action failed')
}

async function handleUnfreeze(payload: { userId: string; reason?: string }) {
  await runAction(async () => {
    await unfreezeAccount(payload.userId, payload.reason)
    await loadUsers()
  }, 'Unfreeze action failed')
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
    <section class="imports-admin-page">
      <header class="imports-admin-page__header">
        <p class="eyebrow">Imports + account controls</p>
        <h2>Run controlled CSV imports and enforce account freeze/unfreeze operations.</h2>
        <p>All actions are permission-gated and audited in the active context.</p>
      </header>

      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      <p v-if="contextStore.errorMessage" class="error">{{ contextStore.errorMessage }}</p>
      <p v-if="loading">Loading controls…</p>

      <p v-else-if="!canManageImports && !canManageAccounts" class="denied">
        Your current role does not include imports or account-control permissions in this context.
      </p>

      <template v-else>
        <ImportBatchManager
          v-if="canManageImports"
          :batches="batches"
          :selected-batch="selectedBatch"
          :loading="loading"
          :acting="acting"
          :can-manage="canManageImports"
          @upload-batch="handleUploadBatch"
          @select-batch="handleSelectBatch"
          @normalize-batch="handleNormalizeBatch"
          @apply-batch="handleApplyBatch"
        />

        <DuplicateReviewPanel
          v-if="canManageImports"
          :duplicates="duplicates"
          :acting="acting"
          :can-manage="canManageImports"
          @merge-duplicate="handleMergeDuplicate"
          @ignore-duplicate="handleIgnoreDuplicate"
          @undo-merge="handleUndoMerge"
        />

        <AccountControlPanel
          v-if="canManageAccounts"
          :users="users"
          :acting="acting"
          :can-manage="canManageAccounts"
          @freeze="handleFreeze"
          @unfreeze="handleUnfreeze"
        />
      </template>
    </section>
  </AppShell>
</template>

<style scoped>
.imports-admin-page {
  display: grid;
  gap: 1rem;
}

.imports-admin-page__header {
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

.imports-admin-page__header p {
  margin: 0.2rem 0 0;
  color: #314c6a;
}

.error {
  margin: 0;
  color: #8a1e35;
}

.denied {
  margin: 0;
  color: #34506e;
}
</style>
