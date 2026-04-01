<script setup lang="ts">
import { reactive, watch } from 'vue'

import type {
  RecommendationConfig,
  RecommendationConfigUpdate,
  RecommendationScopeType,
  RecommendationWeights,
} from '@/types'

const props = defineProps<{
  config: RecommendationConfig | null
  canManage: boolean
  loading: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  selectScope: [scope: RecommendationScopeType]
  save: [payload: RecommendationConfigUpdate]
}>()

const formState = reactive<RecommendationConfigUpdate>({
  scope: 'event_store',
  enabled_modes: {
    popularity_30d: true,
    recent_activity_72h: true,
    tag_match: true,
  },
  weights: {
    popularity_30d: 0.5,
    recent_activity_72h: 0.3,
    tag_match: 0.2,
  },
  pins_enabled: true,
  max_pins: 20,
  pin_ttl_hours: null,
  enforce_pairing_rules: true,
  allow_staff_event_store_manage: false,
})

function normalizeWeights(weights: RecommendationWeights): RecommendationWeights {
  const total = weights.popularity_30d + weights.recent_activity_72h + weights.tag_match
  if (total <= 0) {
    return {
      popularity_30d: 0.5,
      recent_activity_72h: 0.3,
      tag_match: 0.2,
    }
  }
  return {
    popularity_30d: Number((weights.popularity_30d / total).toFixed(4)),
    recent_activity_72h: Number((weights.recent_activity_72h / total).toFixed(4)),
    tag_match: Number((weights.tag_match / total).toFixed(4)),
  }
}

watch(
  () => props.config,
  (config) => {
    if (!config) {
      return
    }
    formState.scope = config.scope.scope
    formState.enabled_modes = { ...config.enabled_modes }
    formState.weights = { ...config.weights }
    formState.pins_enabled = config.pins_enabled
    formState.max_pins = config.max_pins
    formState.pin_ttl_hours = config.pin_ttl_hours
    formState.enforce_pairing_rules = config.enforce_pairing_rules
    formState.allow_staff_event_store_manage = config.allow_staff_event_store_manage
  },
  { immediate: true },
)

function handleScopeChange(scope: RecommendationScopeType) {
  formState.scope = scope
  emit('selectScope', scope)
}

function save() {
  const normalized = normalizeWeights(formState.weights)
  emit('save', {
    ...formState,
    weights: normalized,
  })
}
</script>

<template>
  <section class="config-editor">
    <header>
      <h3>Recommendation configuration</h3>
      <p>Scope inheritance: organization default → program override → event/store override.</p>
    </header>

    <div class="scope-switch">
      <button type="button" :disabled="loading" @click="handleScopeChange('organization')">Organization</button>
      <button type="button" :disabled="loading" @click="handleScopeChange('program')">Program</button>
      <button type="button" :disabled="loading" @click="handleScopeChange('event_store')">Event/Store</button>
    </div>

    <p v-if="config" class="config-editor__info">
      Editing scope: <strong>{{ config.scope.scope }}</strong>
      <span v-if="config.inherited_from_scope"> (inherited from {{ config.inherited_from_scope }} until saved)</span>
    </p>

    <div class="fields">
      <label><input v-model="formState.enabled_modes.popularity_30d" type="checkbox" />Popularity (30d)</label>
      <label><input v-model="formState.enabled_modes.recent_activity_72h" type="checkbox" />Recent activity (72h)</label>
      <label><input v-model="formState.enabled_modes.tag_match" type="checkbox" />Tag match</label>

      <label>
        Weight: Popularity
        <input v-model.number="formState.weights.popularity_30d" type="number" min="0" step="0.05" />
      </label>
      <label>
        Weight: Recent
        <input v-model.number="formState.weights.recent_activity_72h" type="number" min="0" step="0.05" />
      </label>
      <label>
        Weight: Tag match
        <input v-model.number="formState.weights.tag_match" type="number" min="0" step="0.05" />
      </label>

      <label><input v-model="formState.pins_enabled" type="checkbox" />Featured pins enabled</label>
      <label>
        Max pins
        <input v-model.number="formState.max_pins" type="number" min="1" max="100" />
      </label>
      <label>
        Pin TTL (hours, optional)
        <input v-model.number="formState.pin_ttl_hours" type="number" min="1" max="168" />
      </label>
      <label><input v-model="formState.enforce_pairing_rules" type="checkbox" />Enforce pairing rules</label>
      <label>
        <input v-model="formState.allow_staff_event_store_manage" type="checkbox" />
        Allow staff event/store management (org/program scopes)
      </label>
    </div>

    <button v-if="canManage" class="config-editor__save" :disabled="saving || loading" type="button" @click="save">
      {{ saving ? 'Saving…' : 'Save recommendation config' }}
    </button>
    <p v-else class="config-editor__readonly">Read-only: your role cannot manage recommendation settings at this scope.</p>
  </section>
</template>

<style scoped>
.config-editor {
  border: 1px solid rgba(18, 36, 58, 0.16);
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.94);
  padding: 1rem;
  display: grid;
  gap: 0.8rem;
}

h3 {
  margin: 0;
  font-family: 'Fraunces', serif;
}

header p {
  margin: 0.35rem 0 0;
  color: #2f4b67;
}

.scope-switch {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.scope-switch button {
  border: 1px solid rgba(16, 36, 59, 0.18);
  border-radius: 0.55rem;
  background: rgba(33, 68, 110, 0.08);
  padding: 0.36rem 0.62rem;
  cursor: pointer;
}

.fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.6rem;
}

label {
  display: grid;
  gap: 0.2rem;
  font-size: 0.82rem;
  color: #2b4561;
}

input[type='number'] {
  border: 1px solid rgba(30, 51, 76, 0.2);
  border-radius: 0.5rem;
  padding: 0.4rem 0.55rem;
}

.config-editor > button {
  width: fit-content;
  border: none;
  border-radius: 0.55rem;
  background: linear-gradient(120deg, #17446f, #4c2c75);
  color: white;
  padding: 0.5rem 0.78rem;
  cursor: pointer;
}

.config-editor__readonly,
.config-editor__info {
  margin: 0;
  color: #35526f;
}
</style>
