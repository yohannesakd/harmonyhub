<script setup lang="ts">
import { ref } from 'vue'

import type { RepertoireSearchFilters } from '@/types'

const emit = defineEmits<{
  search: [filters: RepertoireSearchFilters]
}>()

const keyword = ref('')
const actor = ref('')
const tagsCsv = ref('')
const region = ref('')
const availabilityStart = ref('')
const availabilityEnd = ref('')

function parseTags(value: string): string[] {
  return value
    .split(',')
    .map((tag) => tag.trim())
    .filter((tag) => tag.length > 0)
}

function toIso(value: string): string | undefined {
  if (!value) {
    return undefined
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return undefined
  }
  return parsed.toISOString()
}

function onSubmit() {
  emit('search', {
    q: keyword.value || undefined,
    repertoire: keyword.value || undefined,
    actor: actor.value || undefined,
    tags: parseTags(tagsCsv.value),
    region: region.value || undefined,
    availability_start: toIso(availabilityStart.value),
    availability_end: toIso(availabilityEnd.value),
  })
}

function resetForm() {
  keyword.value = ''
  actor.value = ''
  tagsCsv.value = ''
  region.value = ''
  availabilityStart.value = ''
  availabilityEnd.value = ''
  onSubmit()
}
</script>

<template>
  <form class="repertoire-search" @submit.prevent="onSubmit">
    <div class="repertoire-search__grid">
      <label>
        <span>Title / Composer</span>
        <input v-model="keyword" placeholder="Moonlight, Beethoven…" />
      </label>

      <label>
        <span>Actor / Person</span>
        <input v-model="actor" placeholder="Ava, Diego…" />
      </label>

      <label>
        <span>Tags (comma-separated)</span>
        <input v-model="tagsCsv" placeholder="classical, ensemble" />
      </label>

      <label>
        <span>Region</span>
        <input v-model="region" placeholder="North Region" />
      </label>

      <label>
        <span>Available from</span>
        <input v-model="availabilityStart" type="datetime-local" />
      </label>

      <label>
        <span>Available to</span>
        <input v-model="availabilityEnd" type="datetime-local" />
      </label>
    </div>

    <div class="repertoire-search__actions">
      <button type="submit">Search repertoire</button>
      <button type="button" class="secondary" @click="resetForm">Reset</button>
    </div>
  </form>
</template>

<style scoped>
.repertoire-search {
  display: grid;
  gap: 1rem;
}

.repertoire-search__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.8rem;
}

label {
  display: grid;
  gap: 0.3rem;
  font-size: 0.82rem;
  color: #253b57;
}

input {
  border: 1px solid rgba(30, 51, 76, 0.18);
  border-radius: 0.55rem;
  padding: 0.52rem 0.6rem;
  background: rgba(255, 255, 255, 0.95);
}

.repertoire-search__actions {
  display: flex;
  gap: 0.6rem;
}

button {
  border: none;
  border-radius: 0.55rem;
  padding: 0.52rem 0.76rem;
  background: #23496f;
  color: #fff;
  cursor: pointer;
}

.secondary {
  background: rgba(24, 36, 58, 0.12);
  color: #1e324c;
}
</style>
