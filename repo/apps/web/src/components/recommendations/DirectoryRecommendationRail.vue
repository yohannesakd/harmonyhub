<script setup lang="ts">
import type { DirectoryRecommendationItem } from '@/types'

const props = defineProps<{
  items: DirectoryRecommendationItem[]
  loading: boolean
  errorMessage: string | null
  canManage: boolean
  pinningIds: string[]
}>()

const emit = defineEmits<{
  pin: [entryId: string]
  unpin: [entryId: string]
}>()

function togglePin(item: DirectoryRecommendationItem) {
  if (item.pinned) {
    emit('unpin', item.entry_id)
    return
  }
  emit('pin', item.entry_id)
}
</script>

<template>
  <section class="recommendation-rail">
    <header>
      <h3>Recommended performers</h3>
      <p>Scored using popularity (30d), recent activity (72h), and tag matching.</p>
    </header>

    <p v-if="loading">Loading recommendations…</p>
    <p v-else-if="errorMessage" class="error">{{ errorMessage }}</p>
    <p v-else-if="items.length === 0" class="empty">No recommendations match the current constraints.</p>

    <ul v-else>
      <li v-for="item in items" :key="item.entry_id">
        <div>
          <strong>{{ item.display_name }}</strong>
          <small>Score: {{ item.score.total.toFixed(2) }}</small>
          <small>Tag match: {{ item.score.tag_match.toFixed(2) }}</small>
        </div>
        <button
          v-if="canManage"
          type="button"
          :disabled="pinningIds.includes(item.entry_id)"
          @click="togglePin(item)"
        >
          {{ item.pinned ? 'Unpin' : 'Pin featured' }}
        </button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.recommendation-rail {
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

small {
  display: block;
  color: #3e5a77;
}

button {
  border: none;
  border-radius: 0.45rem;
  background: #1d4673;
  color: #fff;
  padding: 0.35rem 0.55rem;
  cursor: pointer;
}

.error {
  color: #8a1e35;
}

.empty {
  color: #36516f;
}
</style>
