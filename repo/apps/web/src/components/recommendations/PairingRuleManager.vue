<script setup lang="ts">
import { computed, ref } from 'vue'

import type { DirectoryEntryCard, PairingRule, RepertoireItemCard } from '@/types'

const props = defineProps<{
  canManage: boolean
  rules: PairingRule[]
  directoryEntries: DirectoryEntryCard[]
  repertoireItems: RepertoireItemCard[]
  loading: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  createAllow: [payload: { directory_entry_id: string; repertoire_item_id: string; note?: string }]
  createBlock: [payload: { directory_entry_id: string; repertoire_item_id: string; note?: string }]
  deleteRule: [ruleId: string]
}>()

const selectedEntryId = ref('')
const selectedItemId = ref('')
const note = ref('')

const canSubmit = computed(() => selectedEntryId.value.length > 0 && selectedItemId.value.length > 0)

function createAllow() {
  if (!canSubmit.value) return
  emit('createAllow', {
    directory_entry_id: selectedEntryId.value,
    repertoire_item_id: selectedItemId.value,
    note: note.value || undefined,
  })
}

function createBlock() {
  if (!canSubmit.value) return
  emit('createBlock', {
    directory_entry_id: selectedEntryId.value,
    repertoire_item_id: selectedItemId.value,
    note: note.value || undefined,
  })
}

function deleteRule(ruleId: string) {
  emit('deleteRule', ruleId)
}
</script>

<template>
  <section class="pairing-manager">
    <header>
      <h3>Pairing governance</h3>
      <p>Manage performer ↔ repertoire allowlist/blocklist rules. Blocklist always overrides allowlist.</p>
    </header>

    <div class="pairing-manager__form">
      <label>
        Directory entry
        <select v-model="selectedEntryId" :disabled="loading || saving">
          <option value="">Select performer…</option>
          <option v-for="entry in directoryEntries" :key="entry.id" :value="entry.id">{{ entry.display_name }}</option>
        </select>
      </label>

      <label>
        Repertoire item
        <select v-model="selectedItemId" :disabled="loading || saving">
          <option value="">Select repertoire…</option>
          <option v-for="item in repertoireItems" :key="item.id" :value="item.id">{{ item.title }}</option>
        </select>
      </label>

      <label>
        Note
        <input v-model="note" :disabled="loading || saving" placeholder="optional" />
      </label>
    </div>

    <div class="pairing-manager__actions" v-if="canManage">
      <button type="button" :disabled="!canSubmit || saving" @click="createAllow">Add allowlist rule</button>
      <button type="button" class="danger" :disabled="!canSubmit || saving" @click="createBlock">Add blocklist rule</button>
    </div>
    <p v-else class="pairing-manager__readonly">Read-only: your role cannot manage pairing rules.</p>

    <ul class="pairing-manager__rules">
      <li v-for="rule in rules" :key="rule.id">
        <span>
          <strong>{{ rule.effect.toUpperCase() }}</strong> · {{ rule.directory_entry_id }} → {{ rule.repertoire_item_id }}
          <em v-if="rule.note"> ({{ rule.note }})</em>
        </span>
        <button v-if="canManage" type="button" class="ghost" @click="deleteRule(rule.id)">Delete</button>
      </li>
      <li v-if="rules.length === 0">No pairing rules in this context.</li>
    </ul>
  </section>
</template>

<style scoped>
.pairing-manager {
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

.pairing-manager__form {
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

select,
input {
  border: 1px solid rgba(30, 51, 76, 0.2);
  border-radius: 0.5rem;
  padding: 0.4rem 0.55rem;
}

.pairing-manager__actions {
  display: flex;
  gap: 0.5rem;
}

button {
  border: none;
  border-radius: 0.5rem;
  background: #1d4673;
  color: #fff;
  padding: 0.45rem 0.7rem;
  cursor: pointer;
}

.danger {
  background: #7c2342;
}

.ghost {
  background: rgba(22, 34, 55, 0.1);
  color: #1f3450;
}

.pairing-manager__rules {
  margin: 0;
  padding-left: 1rem;
  display: grid;
  gap: 0.4rem;
}

.pairing-manager__rules li {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  align-items: center;
}

.pairing-manager__readonly {
  margin: 0;
  color: #35526f;
}
</style>
