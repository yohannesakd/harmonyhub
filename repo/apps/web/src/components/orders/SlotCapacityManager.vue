<script setup lang="ts">
import { reactive } from 'vue'

import type { SlotCapacity, SlotCapacityInput } from '@/types'

const props = defineProps<{
  capacities: SlotCapacity[]
  loading: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  loadForDate: [date: string]
  upsert: [payload: SlotCapacityInput]
  remove: [slotStart: string]
}>()

const form = reactive<SlotCapacityInput>({
  slot_start: '',
  capacity: 0,
})

function toIso(value: string): string | null {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed.toISOString()
}

function upsert() {
  const slot = toIso(form.slot_start)
  if (!slot) return
  emit('upsert', {
    slot_start: slot,
    capacity: form.capacity,
  })
}

function edit(row: SlotCapacity) {
  const parsed = new Date(row.slot_start)
  if (Number.isNaN(parsed.getTime())) return
  const pad = (n: number) => String(n).padStart(2, '0')
  form.slot_start = `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`
  form.capacity = row.capacity
}

function loadDate(event: Event) {
  const target = event.target as HTMLInputElement
  emit('loadForDate', target.value)
}
</script>

<template>
  <section class="slot-manager">
    <header>
      <h3>15-minute slot capacities</h3>
      <p>Server-authoritative capacity constraints used during quote/finalize.</p>
    </header>

    <div class="slot-manager__controls">
      <label>
        Filter date
        <input :disabled="loading || saving" type="date" @change="loadDate" />
      </label>
      <label>
        Slot start
        <input v-model="form.slot_start" :disabled="loading || saving" type="datetime-local" step="900" />
      </label>
      <label>
        Capacity
        <input v-model.number="form.capacity" :disabled="loading || saving" type="number" min="0" max="200" />
      </label>
      <button type="button" :disabled="loading || saving" @click="upsert">Upsert slot capacity</button>
    </div>

    <ul>
      <li v-for="row in capacities" :key="row.id">
        <span>{{ row.slot_start }} · cap {{ row.capacity }}</span>
        <div>
          <button type="button" class="secondary" :disabled="loading || saving" @click="edit(row)">Edit</button>
          <button type="button" class="danger" :disabled="loading || saving" @click="emit('remove', row.slot_start)">Delete</button>
        </div>
      </li>
      <li v-if="capacities.length === 0">No slot capacities configured.</li>
    </ul>
  </section>
</template>

<style scoped>
.slot-manager {
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

.slot-manager__controls {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 0.55rem;
  align-items: end;
}

label {
  display: grid;
  gap: 0.2rem;
  font-size: 0.82rem;
  color: #2b4561;
}

input {
  border: 1px solid rgba(30, 51, 76, 0.2);
  border-radius: 0.5rem;
  padding: 0.4rem 0.5rem;
}

button {
  border: none;
  border-radius: 0.5rem;
  background: #1d4673;
  color: #fff;
  padding: 0.42rem 0.66rem;
  cursor: pointer;
}

.secondary {
  background: rgba(22, 34, 55, 0.1);
  color: #1f3450;
}

.danger {
  background: #7c2342;
}

ul {
  margin: 0;
  padding-left: 0;
  list-style: none;
  display: grid;
  gap: 0.45rem;
}

li {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  align-items: center;
}

li > div {
  display: flex;
  gap: 0.35rem;
}
</style>
