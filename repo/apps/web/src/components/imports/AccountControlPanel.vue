<script setup lang="ts">
import { reactive } from 'vue'

import type { AccountStatus } from '@/types'

const props = defineProps<{
  users: AccountStatus[]
  canManage: boolean
  acting: boolean
}>()

const emit = defineEmits<{
  freeze: [payload: { userId: string; reason: string }]
  unfreeze: [payload: { userId: string; reason?: string }]
}>()

const freezeReasons = reactive<Record<string, string>>({})
const unfreezeReasons = reactive<Record<string, string>>({})

function freeze(user: AccountStatus) {
  const reason = (freezeReasons[user.id] || '').trim()
  if (reason.length < 3) {
    return
  }
  emit('freeze', { userId: user.id, reason })
}

function unfreeze(user: AccountStatus) {
  emit('unfreeze', { userId: user.id, reason: unfreezeReasons[user.id] || undefined })
}
</script>

<template>
  <section class="account-panel">
    <header>
      <h3>Account freeze controls</h3>
      <p>Freeze and unfreeze user access with reason tracking and audit logging.</p>
    </header>

    <ul class="account-panel__list">
      <li v-for="user in users" :key="user.id">
        <div class="account-panel__summary">
          <strong>{{ user.username }}</strong>
          <span>{{ user.is_frozen ? 'Frozen' : 'Active' }}</span>
        </div>

        <p v-if="user.is_frozen && user.freeze_reason" class="account-panel__meta">Reason: {{ user.freeze_reason }}</p>

        <div v-if="!user.is_frozen" class="account-panel__actions">
          <input
            v-model="freezeReasons[user.id]"
            type="text"
            placeholder="Freeze reason (required)"
            :disabled="!canManage || acting"
          />
          <button type="button" :disabled="!canManage || acting" @click="freeze(user)">Freeze</button>
        </div>

        <div v-else class="account-panel__actions">
          <input
            v-model="unfreezeReasons[user.id]"
            type="text"
            placeholder="Unfreeze note (optional)"
            :disabled="!canManage || acting"
          />
          <button type="button" :disabled="!canManage || acting" @click="unfreeze(user)">Unfreeze</button>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.account-panel {
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
.account-panel__meta {
  margin: 0.25rem 0 0;
  color: #2f4b67;
}

.account-panel__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.55rem;
}

.account-panel__list li {
  border: 1px solid rgba(16, 36, 59, 0.16);
  border-radius: 0.75rem;
  padding: 0.65rem;
  display: grid;
  gap: 0.35rem;
}

.account-panel__summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.account-panel__actions {
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
