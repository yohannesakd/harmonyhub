<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

import type {
  AuditEvent,
  BackupRun,
  ExportRun,
  OperationsStatus,
  RecoveryDrillCreateInput,
  RecoveryDrillRun,
  RecoveryDrillStatus,
} from '@/types'

const props = defineProps<{
  loading: boolean
  acting: boolean
  status: OperationsStatus | null
  auditEvents: AuditEvent[]
  exportRuns: ExportRun[]
  backupRuns: BackupRun[]
  recoveryDrills: RecoveryDrillRun[]
  canViewAudit: boolean
  canManageExports: boolean
  canManageBackups: boolean
  canManageRecoveryDrills: boolean
}>()

const emit = defineEmits<{
  refresh: []
  requestAudit: [filters: { action_prefix?: string; target_type?: string; limit?: number }]
  runExport: [includeSensitive: boolean]
  runBackup: [copyToOfflineMedium: boolean]
  recordDrill: [payload: RecoveryDrillCreateInput]
}>()

const includeSensitiveExport = ref(false)
const copyToOfflineMedium = ref(true)

const drill = reactive<{
  backup_run_id: string
  scenario: string
  status: RecoveryDrillStatus
  notes: string
}>({
  backup_run_id: '',
  scenario: '',
  status: 'passed',
  notes: '',
})

const auditFilters = reactive<{ action_prefix: string; target_type: string; limit: number }>({
  action_prefix: '',
  target_type: '',
  limit: 100,
})

const statusItems = computed(() => {
  if (!props.status) {
    return []
  }
  return [
    { label: 'Pending import batches', value: props.status.pending_import_batches },
    { label: 'Open import duplicates', value: props.status.open_import_duplicates },
    { label: 'Pickup queue count', value: props.status.pickup_queue_count },
    { label: 'Delivery queue count', value: props.status.delivery_queue_count },
    { label: 'Order conflicts', value: props.status.order_conflict_count },
    {
      label: 'Recovery drill compliance',
      value:
        props.status.recovery_drill_compliance.status === 'current'
          ? `current · due in ${props.status.recovery_drill_compliance.days_until_due ?? 0}d`
          : `overdue · ${props.status.recovery_drill_compliance.days_overdue}d late`,
    },
    {
      label: 'Audit retention drift',
      value: `${props.status.audit_retention.events_older_than_retention} events past ${props.status.audit_retention.retention_days}d`,
    },
  ]
})

function formatDate(value: string | null): string {
  if (!value) {
    return '—'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString()
}

function requestAuditRows() {
  emit('requestAudit', {
    action_prefix: auditFilters.action_prefix || undefined,
    target_type: auditFilters.target_type || undefined,
    limit: auditFilters.limit,
  })
}

function runExportAction() {
  emit('runExport', includeSensitiveExport.value)
}

function runBackupAction() {
  emit('runBackup', copyToOfflineMedium.value)
}

function submitDrill() {
  if (drill.scenario.trim().length < 3) {
    return
  }
  emit('recordDrill', {
    backup_run_id: drill.backup_run_id || undefined,
    scenario: drill.scenario.trim(),
    status: drill.status,
    notes: drill.notes.trim() || undefined,
  })
  drill.scenario = ''
  drill.notes = ''
}
</script>

<template>
  <section class="operations-panel">
    <header class="operations-panel__header">
      <div>
        <p class="eyebrow">Operations oversight</p>
        <h3>Audit, exports, backups, and recovery drills</h3>
      </div>
      <button type="button" :disabled="loading || acting" @click="emit('refresh')">Refresh</button>
    </header>

    <p v-if="loading" class="muted">Loading operations data…</p>

    <section class="status-grid" aria-label="Operations status summary">
      <article v-for="item in statusItems" :key="item.label" class="status-card">
        <p>{{ item.label }}</p>
        <strong>{{ item.value }}</strong>
      </article>
    </section>

    <section class="status-grid">
      <article class="status-card status-card--wide">
        <p>Latest backup</p>
        <strong>{{ props.status?.latest_backup ? formatDate(props.status.latest_backup.completed_at) : 'No runs yet' }}</strong>
      </article>
      <article class="status-card status-card--wide">
        <p>Latest recovery drill</p>
        <strong>
          {{
            props.status?.latest_recovery_drill
              ? `${props.status.latest_recovery_drill.status} · ${formatDate(props.status.latest_recovery_drill.performed_at)}`
              : 'No drills yet'
          }}
        </strong>
        <p>
          Policy: every {{ props.status?.recovery_drill_compliance.interval_days ?? '—' }} days · next due
          {{ formatDate(props.status?.recovery_drill_compliance.due_at ?? null) }}
        </p>
      </article>
      <article class="status-card status-card--wide">
        <p>Audit retention policy</p>
        <strong>
          {{
            props.status
              ? `${props.status.audit_retention.retention_days} days · cutoff ${formatDate(props.status.audit_retention.cutoff_at)}`
              : '—'
          }}
        </strong>
        <p>
          Older-than-policy events in scope:
          <strong>{{ props.status?.audit_retention.events_older_than_retention ?? '—' }}</strong>
        </p>
      </article>
    </section>

    <section v-if="canManageExports" class="panel-section">
      <header>
        <h4>Directory exports</h4>
      </header>
      <label class="checkbox-row">
        <input v-model="includeSensitiveExport" :disabled="acting" type="checkbox" />
        Include sensitive contact data
      </label>
      <button type="button" :disabled="acting" @click="runExportAction">Generate directory CSV</button>
      <ul class="run-list">
        <li v-for="run in exportRuns" :key="run.id">
          <div>
            <strong>{{ run.export_type }}</strong>
            <p>{{ formatDate(run.created_at) }} · {{ run.row_count }} rows · sha {{ run.sha256.slice(0, 10) }}</p>
          </div>
          <a :href="`/api/v1/operations/exports/runs/${run.id}/download`">Download</a>
        </li>
      </ul>
    </section>

    <section v-if="canManageBackups" class="panel-section">
      <header>
        <h4>Backups</h4>
      </header>
      <label class="checkbox-row">
        <input v-model="copyToOfflineMedium" :disabled="acting" type="checkbox" />
        Copy backup to offline medium
      </label>
      <button type="button" :disabled="acting" @click="runBackupAction">Run backup now</button>
      <ul class="run-list">
        <li v-for="run in backupRuns" :key="run.id">
          <div>
            <strong>{{ run.trigger_type }}</strong>
            <p>
              {{ formatDate(run.completed_at) }} · verified {{ run.offline_copy_verified ? 'yes' : 'no' }} · sha
              {{ run.sha256.slice(0, 10) }}
            </p>
          </div>
        </li>
      </ul>
    </section>

    <section v-if="canManageRecoveryDrills" class="panel-section">
      <header>
        <h4>Recovery drills</h4>
      </header>
      <div class="drill-form">
        <label>
          Backup run (optional)
          <select v-model="drill.backup_run_id" :disabled="acting">
            <option value="">None</option>
            <option v-for="run in backupRuns" :key="run.id" :value="run.id">{{ run.id.slice(0, 8) }}</option>
          </select>
        </label>
        <label>
          Scenario
          <input v-model="drill.scenario" :disabled="acting" placeholder="e.g. restore latest and verify records" />
        </label>
        <label>
          Status
          <select v-model="drill.status" :disabled="acting">
            <option value="passed">passed</option>
            <option value="failed">failed</option>
            <option value="inconclusive">inconclusive</option>
          </select>
        </label>
        <label>
          Notes
          <textarea v-model="drill.notes" :disabled="acting" rows="2" />
        </label>
      </div>
      <button type="button" :disabled="acting" @click="submitDrill">Record drill</button>
      <ul class="run-list">
        <li v-for="drillRun in recoveryDrills" :key="drillRun.id">
          <div>
            <strong>{{ drillRun.status }}</strong>
            <p>{{ drillRun.scenario }} · {{ formatDate(drillRun.performed_at) }}</p>
          </div>
        </li>
      </ul>
    </section>

    <section v-if="canViewAudit" class="panel-section">
      <header>
        <h4>Audit events</h4>
      </header>
      <div class="audit-filters">
        <label>
          Action prefix
          <input v-model="auditFilters.action_prefix" :disabled="acting" placeholder="e.g. exports." />
        </label>
        <label>
          Target type
          <input v-model="auditFilters.target_type" :disabled="acting" placeholder="e.g. backup_run" />
        </label>
        <label>
          Limit
          <input v-model.number="auditFilters.limit" :disabled="acting" type="number" min="1" max="500" />
        </label>
        <button type="button" :disabled="acting" @click="requestAuditRows">Apply filters</button>
      </div>
      <ul class="run-list">
        <li v-for="event in auditEvents" :key="event.id">
          <div>
            <strong>{{ event.action }}</strong>
            <p>
              {{ event.target_type ?? 'n/a' }} · {{ event.target_id ?? 'n/a' }} · {{ formatDate(event.created_at) }}
            </p>
          </div>
        </li>
      </ul>
    </section>
  </section>
</template>

<style scoped>
.operations-panel {
  display: grid;
  gap: 1rem;
}

.operations-panel__header {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 1rem;
}

.eyebrow {
  margin: 0;
  font-size: 0.73rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #2a4f75;
}

h3,
h4 {
  margin: 0.3rem 0 0;
  font-family: 'Fraunces', serif;
}

.muted {
  margin: 0;
  color: #375675;
}

button,
a {
  border: 1px solid rgba(20, 47, 76, 0.25);
  border-radius: 0.55rem;
  background: rgba(255, 255, 255, 0.92);
  color: #12385e;
  padding: 0.45rem 0.7rem;
  text-decoration: none;
  cursor: pointer;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.7rem;
}

.status-card {
  border: 1px solid rgba(20, 47, 76, 0.14);
  border-radius: 0.85rem;
  padding: 0.7rem;
  background: rgba(251, 250, 246, 0.92);
}

.status-card p {
  margin: 0;
  font-size: 0.8rem;
  color: #3a5877;
}

.status-card strong {
  display: block;
  margin-top: 0.35rem;
}

.status-card--wide {
  min-height: 5rem;
}

.panel-section {
  border: 1px solid rgba(21, 39, 61, 0.14);
  border-radius: 1rem;
  padding: 0.85rem;
  background: rgba(251, 250, 246, 0.92);
  display: grid;
  gap: 0.6rem;
}

.checkbox-row {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.run-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.45rem;
}

.run-list li {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  align-items: center;
  border: 1px solid rgba(20, 47, 76, 0.12);
  border-radius: 0.7rem;
  background: rgba(255, 255, 255, 0.92);
  padding: 0.55rem;
}

.run-list p {
  margin: 0.2rem 0 0;
  color: #355371;
  font-size: 0.8rem;
}

.drill-form,
.audit-filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.5rem;
}

label {
  display: grid;
  gap: 0.2rem;
  color: #355370;
  font-size: 0.79rem;
}

input,
select,
textarea {
  border: 1px solid rgba(21, 47, 76, 0.2);
  border-radius: 0.5rem;
  padding: 0.42rem 0.5rem;
  font-size: 0.85rem;
}
</style>
