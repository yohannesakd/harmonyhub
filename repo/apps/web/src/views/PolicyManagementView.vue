<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import AppShell from '@/components/layout/AppShell.vue'
import { useWorkspaceContext } from '@/composables/useWorkspaceContext'
import {
  createAbacRule,
  deleteAbacRule,
  listAbacRules,
  listAbacSurfaces,
  simulateAbac,
  upsertAbacSurface,
} from '@/services/api'
import { toDisplayErrorMessage } from '@/utils/displayErrors'
import type {
  AbacRule,
  AbacRuleCreateInput,
  AbacSimulationResponse,
  AbacSurfaceSetting,
  ActiveContext,
} from '@/types'

const { authStore, contextStore, bootstrapWorkspace, switchWorkspaceContext } = useWorkspaceContext()

const loading = ref(false)
const acting = ref(false)
const errorMessage = ref<string | null>(null)

const surfaces = ref<AbacSurfaceSetting[]>([])
const selectedSurface = ref('')
const selectedAction = ref('view')
const rules = ref<AbacRule[]>([])
const simulationResult = ref<AbacSimulationResponse | null>(null)

const surfaceForm = reactive({
  surface: '',
  enabled: true,
})

const ruleForm = reactive({
  surface: '',
  action: 'view',
  effect: 'deny' as 'allow' | 'deny',
  priority: 100,
  role: '',
  subject_department: '',
  subject_grade: '',
  subject_class: '',
  program_id: '',
  event_id: '',
  store_id: '',
  resource_department: '',
  resource_grade: '',
  resource_class: '',
  resource_field: '',
})

const simulationForm = reactive({
  surface: '',
  action: 'view',
  role: 'student',
  program_id: '',
  event_id: '',
  store_id: '',
  subject_department: '',
  subject_grade: '',
  subject_class: '',
  resource_department: '',
  resource_grade: '',
  resource_class: '',
  resource_field: '',
})

const canManagePolicies = computed(() => authStore.permissions.includes('abac.policy.manage'))

function normalizeInput(value: string): string {
  return value.trim()
}

function applySurfaceSelectionDefaults() {
  if (selectedSurface.value && surfaces.value.some((surface) => surface.surface === selectedSurface.value)) {
    return
  }
  selectedSurface.value = surfaces.value[0]?.surface ?? ''
}

function syncFormDefaults() {
  const fallbackSurface = selectedSurface.value || surfaces.value[0]?.surface || ''
  if (fallbackSurface.length > 0) {
    if (!ruleForm.surface) {
      ruleForm.surface = fallbackSurface
    }
    if (!simulationForm.surface) {
      simulationForm.surface = fallbackSurface
    }
  }
}

async function withAction(action: () => Promise<void>, fallbackMessage: string) {
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

async function loadSurfaces() {
  const rows = await listAbacSurfaces()
  surfaces.value = [...rows].sort((a, b) => a.surface.localeCompare(b.surface))
  applySurfaceSelectionDefaults()
  syncFormDefaults()
}

async function loadRules() {
  const surface = normalizeInput(selectedSurface.value)
  const action = normalizeInput(selectedAction.value)
  if (!surface || !action) {
    rules.value = []
    return
  }
  rules.value = await listAbacRules(surface, action)
}

async function loadAll() {
  loading.value = true
  errorMessage.value = null
  simulationResult.value = null
  rules.value = []
  surfaces.value = []
  try {
    await bootstrapWorkspace()
    if (!canManagePolicies.value) {
      return
    }
    await loadSurfaces()
    await loadRules()
  } catch (error) {
    errorMessage.value = toDisplayErrorMessage(error, 'Unable to load policy management workspace')
  } finally {
    loading.value = false
  }
}

async function handleSwitchContext(next: ActiveContext) {
  try {
    await switchWorkspaceContext(next)
    await loadAll()
  } catch {
    // Context-switch errors are already surfaced by context store.
  }
}

async function handleUpsertSurface() {
  const surface = normalizeInput(surfaceForm.surface)
  if (!surface) {
    errorMessage.value = 'Surface key is required.'
    return
  }
  await withAction(async () => {
    await upsertAbacSurface(surface, { enabled: surfaceForm.enabled })
    selectedSurface.value = surface
    ruleForm.surface = surface
    simulationForm.surface = surface
    await loadSurfaces()
    await loadRules()
  }, 'Failed to upsert ABAC surface')
}

async function handleToggleSurface(surface: string, enabled: boolean) {
  await withAction(async () => {
    await upsertAbacSurface(surface, { enabled })
    await loadSurfaces()
  }, 'Failed to update ABAC surface')
}

async function handleLoadRules() {
  selectedSurface.value = normalizeInput(selectedSurface.value)
  selectedAction.value = normalizeInput(selectedAction.value)
  await withAction(loadRules, 'Failed to load ABAC rules')
}

async function handleCreateRule() {
  const payload: AbacRuleCreateInput = {
    surface: normalizeInput(ruleForm.surface),
    action: normalizeInput(ruleForm.action),
    effect: ruleForm.effect,
    priority: ruleForm.priority,
  }
  if (!payload.surface || !payload.action) {
    errorMessage.value = 'Create rule requires both surface and action.'
    return
  }
  const role = normalizeInput(ruleForm.role)
  const subjectDepartment = normalizeInput(ruleForm.subject_department)
  const subjectGrade = normalizeInput(ruleForm.subject_grade)
  const subjectClass = normalizeInput(ruleForm.subject_class)
  const programId = normalizeInput(ruleForm.program_id)
  const eventId = normalizeInput(ruleForm.event_id)
  const storeId = normalizeInput(ruleForm.store_id)
  const resourceDepartment = normalizeInput(ruleForm.resource_department)
  const resourceGrade = normalizeInput(ruleForm.resource_grade)
  const resourceClass = normalizeInput(ruleForm.resource_class)
  const resourceField = normalizeInput(ruleForm.resource_field)
  if (role) payload.role = role
  if (subjectDepartment) payload.subject_department = subjectDepartment
  if (subjectGrade) payload.subject_grade = subjectGrade
  if (subjectClass) payload.subject_class = subjectClass
  if (programId) payload.program_id = programId
  if (eventId) payload.event_id = eventId
  if (storeId) payload.store_id = storeId
  if (resourceDepartment) payload.resource_department = resourceDepartment
  if (resourceGrade) payload.resource_grade = resourceGrade
  if (resourceClass) payload.resource_class = resourceClass
  if (resourceField) payload.resource_field = resourceField

  await withAction(async () => {
    await createAbacRule(payload)
    selectedSurface.value = payload.surface
    selectedAction.value = payload.action
    await loadRules()
  }, 'Failed to create ABAC rule')
}

async function handleDeleteRule(ruleId: string) {
  await withAction(async () => {
    await deleteAbacRule(ruleId)
    await loadRules()
  }, 'Failed to delete ABAC rule')
}

async function handleSimulate() {
  const surface = normalizeInput(simulationForm.surface)
  const action = normalizeInput(simulationForm.action)
  const role = normalizeInput(simulationForm.role)
  if (!surface || !action || !role) {
    errorMessage.value = 'Simulation requires surface, action, and role.'
    return
  }
  const programId = normalizeInput(simulationForm.program_id)
  const eventId = normalizeInput(simulationForm.event_id)
  const storeId = normalizeInput(simulationForm.store_id)
  const subjectDepartment = normalizeInput(simulationForm.subject_department)
  const subjectGrade = normalizeInput(simulationForm.subject_grade)
  const subjectClass = normalizeInput(simulationForm.subject_class)
  const resourceDepartment = normalizeInput(simulationForm.resource_department)
  const resourceGrade = normalizeInput(simulationForm.resource_grade)
  const resourceClass = normalizeInput(simulationForm.resource_class)
  const resourceField = normalizeInput(simulationForm.resource_field)

  await withAction(async () => {
    simulationResult.value = await simulateAbac({
      surface,
      action,
      role,
      context: {
        ...(programId ? { program_id: programId } : {}),
        ...(eventId ? { event_id: eventId } : {}),
        ...(storeId ? { store_id: storeId } : {}),
      },
      subject: {
        ...(subjectDepartment ? { department: subjectDepartment } : {}),
        ...(subjectGrade ? { grade: subjectGrade } : {}),
        ...(subjectClass ? { class_code: subjectClass } : {}),
      },
      resource: {
        ...(resourceDepartment ? { department: resourceDepartment } : {}),
        ...(resourceGrade ? { grade: resourceGrade } : {}),
        ...(resourceClass ? { class_code: resourceClass } : {}),
        ...(resourceField ? { field: resourceField } : {}),
      },
    })
  }, 'Failed to run ABAC simulation')
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
    <section class="policy-page">
      <header class="policy-page__header">
        <p class="eyebrow">Admin policy management</p>
        <h2>Manage scoped ABAC policy surfaces and rules.</h2>
        <p>Use this admin-only panel to control ABAC surface enforcement, maintain rule sets, and run policy simulation.</p>
      </header>

      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      <p v-if="contextStore.errorMessage" class="error">{{ contextStore.errorMessage }}</p>

      <p v-if="loading">Loading policy management workspace…</p>
      <p v-else-if="!canManagePolicies" class="denied">Your current role does not include ABAC policy management permissions.</p>

      <template v-else>
        <section class="panel-section">
          <header>
            <h3>Surface enable/disable</h3>
            <button type="button" :disabled="loading || acting" @click="loadSurfaces">Refresh surfaces</button>
          </header>

          <div class="form-grid">
            <label>
              Surface key
              <input v-model="surfaceForm.surface" :disabled="acting" placeholder="e.g. directory" />
            </label>
            <label class="checkbox-row">
              <input v-model="surfaceForm.enabled" :disabled="acting" type="checkbox" />
              Enabled
            </label>
          </div>

          <button type="button" :disabled="acting" @click="handleUpsertSurface">Upsert surface</button>

          <ul class="row-list">
            <li v-for="surface in surfaces" :key="surface.id">
              <div>
                <strong>{{ surface.surface }}</strong>
                <p>Status: {{ surface.enabled ? 'enabled' : 'disabled' }}</p>
              </div>
              <button
                type="button"
                class="secondary"
                :disabled="acting"
                @click="handleToggleSurface(surface.surface, !surface.enabled)"
              >
                {{ surface.enabled ? 'Disable surface' : 'Enable surface' }}
              </button>
            </li>
            <li v-if="surfaces.length === 0">No surfaces configured for this organization yet.</li>
          </ul>
        </section>

        <section class="panel-section">
          <header>
            <h3>Rule list</h3>
          </header>

          <div class="form-grid">
            <label>
              Rule surface
              <select v-model="selectedSurface" :disabled="acting">
                <option value="">Select surface…</option>
                <option v-for="surface in surfaces" :key="surface.id" :value="surface.surface">{{ surface.surface }}</option>
              </select>
            </label>
            <label>
              Rule action
              <input v-model="selectedAction" :disabled="acting" placeholder="e.g. view" />
            </label>
          </div>

          <button type="button" :disabled="acting" @click="handleLoadRules">Load rules</button>

          <ul class="row-list">
            <li v-for="rule in rules" :key="rule.id">
              <div>
                <strong>{{ rule.effect.toUpperCase() }}</strong>
                <p>{{ rule.surface }} · {{ rule.action }} · priority {{ rule.priority }}</p>
                <p>Role: {{ rule.role ?? 'any' }} · Program: {{ rule.program_id ?? 'any' }} · Event: {{ rule.event_id ?? 'any' }}</p>
                <p>
                  Subject → department: {{ rule.subject_department ?? 'any' }} · grade: {{ rule.subject_grade ?? 'any' }} · class:
                  {{ rule.subject_class ?? 'any' }}
                </p>
                <p>
                  Resource → department: {{ rule.resource_department ?? 'any' }} · grade: {{ rule.resource_grade ?? 'any' }} · class:
                  {{ rule.resource_class ?? 'any' }} · field: {{ rule.resource_field ?? 'any' }}
                </p>
              </div>
              <button type="button" class="danger" :disabled="acting" @click="handleDeleteRule(rule.id)">Delete rule</button>
            </li>
            <li v-if="rules.length === 0">No rules for selected surface/action.</li>
          </ul>
        </section>

        <section class="panel-section">
          <header>
            <h3>Create rule</h3>
          </header>

          <div class="form-grid">
            <label>
              Create surface
              <input v-model="ruleForm.surface" :disabled="acting" placeholder="e.g. directory" />
            </label>
            <label>
              Create action
              <input v-model="ruleForm.action" :disabled="acting" placeholder="e.g. view" />
            </label>
            <label>
              Effect
              <select v-model="ruleForm.effect" :disabled="acting">
                <option value="allow">allow</option>
                <option value="deny">deny</option>
              </select>
            </label>
            <label>
              Priority
              <input v-model.number="ruleForm.priority" :disabled="acting" type="number" min="1" max="1000" />
            </label>
            <label>
              Role (optional)
              <input v-model="ruleForm.role" :disabled="acting" placeholder="student / staff / administrator" />
            </label>
            <label>
              Subject department (optional)
              <input
                v-model="ruleForm.subject_department"
                data-testid="rule-subject-department"
                :disabled="acting"
                placeholder="e.g. music"
              />
            </label>
            <label>
              Subject grade (optional)
              <input
                v-model="ruleForm.subject_grade"
                data-testid="rule-subject-grade"
                :disabled="acting"
                placeholder="e.g. grade_10"
              />
            </label>
            <label>
              Subject class (optional)
              <input
                v-model="ruleForm.subject_class"
                data-testid="rule-subject-class"
                :disabled="acting"
                placeholder="e.g. 10A"
              />
            </label>
            <label>
              Program ID (optional)
              <input v-model="ruleForm.program_id" :disabled="acting" />
            </label>
            <label>
              Event ID (optional)
              <input v-model="ruleForm.event_id" :disabled="acting" />
            </label>
            <label>
              Store ID (optional)
              <input v-model="ruleForm.store_id" :disabled="acting" />
            </label>
            <label>
              Resource department (optional)
              <input
                v-model="ruleForm.resource_department"
                data-testid="rule-resource-department"
                :disabled="acting"
                placeholder="e.g. music"
              />
            </label>
            <label>
              Resource grade (optional)
              <input
                v-model="ruleForm.resource_grade"
                data-testid="rule-resource-grade"
                :disabled="acting"
                placeholder="e.g. grade_10"
              />
            </label>
            <label>
              Resource class (optional)
              <input
                v-model="ruleForm.resource_class"
                data-testid="rule-resource-class"
                :disabled="acting"
                placeholder="e.g. 10A"
              />
            </label>
            <label>
              Resource field (optional)
              <input
                v-model="ruleForm.resource_field"
                data-testid="rule-resource-field"
                :disabled="acting"
                placeholder="e.g. email / phone / address_line1"
              />
            </label>
          </div>

          <button type="button" :disabled="acting" @click="handleCreateRule">Create rule</button>
        </section>

        <section class="panel-section">
          <header>
            <h3>Simulation</h3>
          </header>

          <div class="form-grid">
            <label>
              Sim surface
              <input v-model="simulationForm.surface" :disabled="acting" placeholder="e.g. directory" />
            </label>
            <label>
              Sim action
              <input v-model="simulationForm.action" :disabled="acting" placeholder="e.g. view" />
            </label>
            <label>
              Sim role
              <input v-model="simulationForm.role" :disabled="acting" placeholder="student" />
            </label>
            <label>
              Sim program ID
              <input v-model="simulationForm.program_id" :disabled="acting" />
            </label>
            <label>
              Sim event ID
              <input v-model="simulationForm.event_id" :disabled="acting" />
            </label>
            <label>
              Sim store ID
              <input v-model="simulationForm.store_id" :disabled="acting" />
            </label>
            <label>
              Sim subject department
              <input
                v-model="simulationForm.subject_department"
                data-testid="sim-subject-department"
                :disabled="acting"
                placeholder="e.g. music"
              />
            </label>
            <label>
              Sim subject grade
              <input
                v-model="simulationForm.subject_grade"
                data-testid="sim-subject-grade"
                :disabled="acting"
                placeholder="e.g. grade_10"
              />
            </label>
            <label>
              Sim subject class
              <input
                v-model="simulationForm.subject_class"
                data-testid="sim-subject-class"
                :disabled="acting"
                placeholder="e.g. 10A"
              />
            </label>
            <label>
              Sim resource department
              <input
                v-model="simulationForm.resource_department"
                data-testid="sim-resource-department"
                :disabled="acting"
                placeholder="e.g. music"
              />
            </label>
            <label>
              Sim resource grade
              <input
                v-model="simulationForm.resource_grade"
                data-testid="sim-resource-grade"
                :disabled="acting"
                placeholder="e.g. grade_10"
              />
            </label>
            <label>
              Sim resource class
              <input
                v-model="simulationForm.resource_class"
                data-testid="sim-resource-class"
                :disabled="acting"
                placeholder="e.g. 10A"
              />
            </label>
            <label>
              Sim resource field
              <input
                v-model="simulationForm.resource_field"
                data-testid="sim-resource-field"
                :disabled="acting"
                placeholder="e.g. email"
              />
            </label>
          </div>

          <button type="button" :disabled="acting" @click="handleSimulate">Run simulation</button>

          <article v-if="simulationResult" class="simulation-result" aria-label="Simulation result">
            <h4>Simulation result</h4>
            <p>Allowed: <strong>{{ simulationResult.allowed ? 'yes' : 'no' }}</strong></p>
            <p>Enforced: <strong>{{ simulationResult.enforced ? 'yes' : 'no' }}</strong></p>
            <p>Reason: <strong>{{ simulationResult.reason }}</strong></p>
            <p>Matched rule: <strong>{{ simulationResult.matched_rule_id ?? 'none' }}</strong></p>
          </article>
        </section>
      </template>
    </section>
  </AppShell>
</template>

<style scoped>
.policy-page {
  display: grid;
  gap: 1rem;
}

.policy-page__header,
.panel-section {
  border: 1px solid rgba(21, 39, 61, 0.14);
  border-radius: 1rem;
  padding: 1rem;
  background: rgba(251, 250, 246, 0.92);
}

.policy-page__header p {
  margin: 0.2rem 0 0;
  color: #314c6a;
}

.eyebrow {
  margin: 0;
  font-size: 0.73rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #2a4f75;
}

h2,
h3,
h4 {
  margin: 0.35rem 0;
  font-family: 'Fraunces', serif;
}

.panel-section {
  display: grid;
  gap: 0.7rem;
}

.panel-section > header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
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
textarea,
button {
  border: 1px solid rgba(21, 47, 76, 0.2);
  border-radius: 0.5rem;
  padding: 0.42rem 0.5rem;
  font-size: 0.85rem;
}

button {
  width: fit-content;
  cursor: pointer;
  color: #12385e;
  background: rgba(255, 255, 255, 0.92);
}

.secondary {
  background: rgba(22, 34, 55, 0.08);
}

.danger {
  background: rgba(124, 35, 66, 0.12);
  color: #5e1230;
}

.checkbox-row {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}

.row-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.45rem;
}

.row-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.9rem;
  border: 1px solid rgba(20, 47, 76, 0.12);
  border-radius: 0.7rem;
  background: rgba(255, 255, 255, 0.92);
  padding: 0.6rem;
}

.row-list p {
  margin: 0.2rem 0 0;
  color: #355371;
  font-size: 0.8rem;
}

.simulation-result {
  border: 1px dashed rgba(42, 79, 117, 0.35);
  border-radius: 0.7rem;
  padding: 0.7rem;
  background: rgba(255, 255, 255, 0.95);
}

.simulation-result p {
  margin: 0.2rem 0;
  color: #2f4e6f;
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
