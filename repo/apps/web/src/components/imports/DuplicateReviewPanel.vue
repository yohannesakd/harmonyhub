<script setup lang="ts">
import { reactive } from 'vue'

import type { ImportDuplicateCandidate } from '@/types'

const props = defineProps<{
  duplicates: ImportDuplicateCandidate[]
  canManage: boolean
  acting: boolean
}>()

const emit = defineEmits<{
  mergeDuplicate: [payload: { duplicateId: string; note?: string }]
  ignoreDuplicate: [duplicateId: string]
  undoMerge: [payload: { mergeActionId: string; reason?: string }]
}>()

const notes = reactive<Record<string, string>>({})
const undoReasons = reactive<Record<string, string>>({})

function merge(candidate: ImportDuplicateCandidate) {
  emit('mergeDuplicate', { duplicateId: candidate.id, note: notes[candidate.id] || undefined })
}

function undo(candidate: ImportDuplicateCandidate) {
  if (!candidate.merge_action_id) {
    return
  }
  emit('undoMerge', {
    mergeActionId: candidate.merge_action_id,
    reason: undoReasons[candidate.id] || undefined,
  })
}
</script>

<template>
  <section class="duplicate-panel">
    <header>
      <h3>Duplicate review queue</h3>
      <p>Review potential duplicate member rows before final apply.</p>
    </header>

    <ul v-if="duplicates.length" class="duplicate-panel__list">
      <li v-for="candidate in duplicates" :key="candidate.id">
        <p>
          <strong>{{ candidate.target_display_name }}</strong> · reason {{ candidate.reason }} · status
          {{ candidate.status }}
        </p>
        <p v-if="candidate.normalized_json">Incoming {{ candidate.normalized_json }}</p>
        <div v-if="candidate.status === 'open' || candidate.status === 'undo_applied'" class="duplicate-panel__actions">
          <input v-model="notes[candidate.id]" type="text" placeholder="Merge note (optional)" :disabled="acting || !canManage" />
          <button type="button" :disabled="acting || !canManage" @click="merge(candidate)">Merge</button>
          <button type="button" :disabled="acting || !canManage" @click="emit('ignoreDuplicate', candidate.id)">Ignore</button>
        </div>
        <div v-else-if="candidate.status === 'merged' && candidate.merge_action_id" class="duplicate-panel__actions">
          <input
            v-model="undoReasons[candidate.id]"
            type="text"
            placeholder="Undo reason (optional)"
            :disabled="acting || !canManage"
          />
          <button type="button" :disabled="acting || !canManage" @click="undo(candidate)">Undo merge</button>
        </div>
      </li>
    </ul>

    <p v-else class="duplicate-panel__empty">No duplicate candidates in scope.</p>
  </section>
</template>

<style scoped>
.duplicate-panel {
  border: 1px solid rgba(18, 36, 58, 0.16);
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.94);
  padding: 1rem;
  display: grid;
  gap: 0.75rem;
}

h3 {
  margin: 0;
  font-family: 'Fraunces', serif;
}

header p,
.duplicate-panel__empty {
  margin: 0.25rem 0 0;
  color: #2f4b67;
}

.duplicate-panel__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.55rem;
}

.duplicate-panel__list li {
  border: 1px solid rgba(16, 36, 59, 0.16);
  border-radius: 0.75rem;
  padding: 0.65rem;
  display: grid;
  gap: 0.35rem;
}

.duplicate-panel__list p {
  margin: 0;
}

.duplicate-panel__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

button,
input {
  border-radius: 0.5rem;
  border: 1px solid rgba(16, 36, 59, 0.22);
  padding: 0.35rem 0.5rem;
}
</style>
