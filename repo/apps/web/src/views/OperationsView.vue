<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AppShell from '@/components/layout/AppShell.vue'
import OperationsControlPanel from '@/components/operations/OperationsControlPanel.vue'
import { useWorkspaceContext } from '@/composables/useWorkspaceContext'
import {
  createDirectoryExport,
  createRecoveryDrill,
  fetchOperationsStatus,
  listAuditEvents,
  listBackupRuns,
  listExportRuns,
  listRecoveryDrills,
  triggerBackupRun,
} from '@/services/api'
import { toDisplayErrorMessage } from '@/utils/displayErrors'
import type {
  ActiveContext,
  AuditEvent,
  BackupRun,
  ExportRun,
  OperationsStatus,
  RecoveryDrillCreateInput,
  RecoveryDrillRun,
} from '@/types'

const { authStore, contextStore, bootstrapWorkspace, switchWorkspaceContext } = useWorkspaceContext()

const loading = ref(false)
const acting = ref(false)
const errorMessage = ref<string | null>(null)

const status = ref<OperationsStatus | null>(null)
const auditEvents = ref<AuditEvent[]>([])
const exportRuns = ref<ExportRun[]>([])
const backupRuns = ref<BackupRun[]>([])
const recoveryDrills = ref<RecoveryDrillRun[]>([])

const canViewAudit = computed(() => authStore.permissions.includes('audit.view'))
const canManageExports = computed(() => authStore.permissions.includes('export.manage'))
const canManageBackups = computed(() => authStore.permissions.includes('backup.manage'))
const canManageRecoveryDrills = computed(() => authStore.permissions.includes('recovery_drill.manage'))
const canViewOperations = computed(() => authStore.permissions.includes('operations.view'))
const hasOperationsAccess = computed(
  () =>
    canViewOperations.value ||
    canViewAudit.value ||
    canManageExports.value ||
    canManageBackups.value ||
    canManageRecoveryDrills.value,
)

function resetOperationsState() {
  status.value = null
  auditEvents.value = []
  exportRuns.value = []
  backupRuns.value = []
  recoveryDrills.value = []
}

async function loadAll() {
  loading.value = true
  errorMessage.value = null
  resetOperationsState()
  try {
    await bootstrapWorkspace()

    if (!hasOperationsAccess.value) {
      return
    }

    const requests: Promise<unknown>[] = []
    if (canViewOperations.value) {
      requests.push(
        fetchOperationsStatus().then((payload) => {
          status.value = payload
        }),
      )
      requests.push(
        listBackupRuns().then((rows) => {
          backupRuns.value = rows
        }),
      )
      requests.push(
        listRecoveryDrills().then((rows) => {
          recoveryDrills.value = rows
        }),
      )
    }
    if (canManageExports.value) {
      requests.push(
        listExportRuns().then((rows) => {
          exportRuns.value = rows
        }),
      )
    }
    if (canViewAudit.value) {
      requests.push(
        listAuditEvents({ limit: 100 }).then((rows) => {
          auditEvents.value = rows
        }),
      )
    }

    await Promise.all(requests)
  } catch (error) {
    errorMessage.value = toDisplayErrorMessage(error, 'Unable to load operations controls')
  } finally {
    loading.value = false
  }
}

async function handleSwitchContext(next: ActiveContext) {
  try {
    await switchWorkspaceContext(next)
    await loadAll()
  } catch {
    // Context-switch error already surfaced by context store.
  }
}

async function runAction(action: () => Promise<void>, fallbackMessage: string) {
  acting.value = true
  errorMessage.value = null
  try {
    await action()
  } catch (error) {
    errorMessage.value = toDisplayErrorMessage(error, fallbackMessage)
  } finally {
    acting.value = false
  }
}

async function handleExport(includeSensitive: boolean) {
  await runAction(async () => {
    await createDirectoryExport(includeSensitive)
    exportRuns.value = await listExportRuns()
    if (canViewAudit.value) {
      auditEvents.value = await listAuditEvents({ limit: 100 })
    }
  }, 'Failed to run directory export')
}

async function handleBackup(copyToOfflineMedium: boolean) {
  await runAction(async () => {
    await triggerBackupRun(copyToOfflineMedium)
    backupRuns.value = await listBackupRuns()
    if (canViewOperations.value) {
      status.value = await fetchOperationsStatus()
    }
    if (canViewAudit.value) {
      auditEvents.value = await listAuditEvents({ limit: 100 })
    }
  }, 'Failed to run backup')
}

async function handleRecordDrill(payload: RecoveryDrillCreateInput) {
  await runAction(async () => {
    await createRecoveryDrill(payload)
    recoveryDrills.value = await listRecoveryDrills()
    if (canViewOperations.value) {
      status.value = await fetchOperationsStatus()
    }
    if (canViewAudit.value) {
      auditEvents.value = await listAuditEvents({ limit: 100 })
    }
  }, 'Failed to record recovery drill')
}

async function handleAuditQuery(filters: { action_prefix?: string; target_type?: string; limit?: number }) {
  await runAction(async () => {
    auditEvents.value = await listAuditEvents(filters)
  }, 'Failed to query audit events')
}

onMounted(loadAll)
</script>

<template>
  <AppShell
    :contexts="contextStore.contexts"
    :active-context="contextStore.activeContext"
    :switching-context="contextStore.switching"
    @switch-context="handleSwitchContext"
  >
    <section class="operations-page">
      <header class="operations-page__header">
        <p class="eyebrow">Operations center</p>
        <h2>Audit trails, exports, backups, and recovery drills</h2>
        <p>Use these controls to verify operational health and compliance for the active tenant scope.</p>
      </header>

      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      <p v-if="contextStore.errorMessage" class="error">{{ contextStore.errorMessage }}</p>

      <p v-if="!canViewOperations && !canManageExports && !canManageBackups && !canManageRecoveryDrills && !canViewAudit" class="denied">
        Your current role does not include operations permissions in this context.
      </p>

      <OperationsControlPanel
        v-else
        :loading="loading"
        :acting="acting"
        :status="status"
        :audit-events="auditEvents"
        :export-runs="exportRuns"
        :backup-runs="backupRuns"
        :recovery-drills="recoveryDrills"
        :can-view-audit="canViewAudit"
        :can-manage-exports="canManageExports"
        :can-manage-backups="canManageBackups"
        :can-manage-recovery-drills="canManageRecoveryDrills"
        @refresh="loadAll"
        @run-export="handleExport"
        @run-backup="handleBackup"
        @record-drill="handleRecordDrill"
        @request-audit="handleAuditQuery"
      />
    </section>
  </AppShell>
</template>

<style scoped>
.operations-page {
  display: grid;
  gap: 1rem;
}

.operations-page__header {
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

.operations-page__header p {
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
