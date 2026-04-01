<script setup lang="ts">
import type { RepertoireRecommendationItem } from '@/types'

defineProps<{
  items: RepertoireRecommendationItem[]
  loading: boolean
  errorMessage: string | null
}>()
</script>

<template>
  <section class="recommendation-rail">
    <header>
      <h3>Recommended repertoire</h3>
      <p>Recommendations respect pairing restrictions and featured pin ordering.</p>
    </header>

    <p v-if="loading">Loading recommendations…</p>
    <p v-else-if="errorMessage" class="error">{{ errorMessage }}</p>
    <p v-else-if="items.length === 0" class="empty">No repertoire recommendations available.</p>

    <ul v-else>
      <li v-for="item in items" :key="item.repertoire_item_id">
        <div>
          <strong>{{ item.title }}</strong>
          <small>Score: {{ item.score.total.toFixed(2) }}</small>
          <small>Performers: {{ item.performers.join(', ') || '—' }}</small>
        </div>
        <span v-if="item.pinned" class="badge">Featured</span>
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

.badge {
  border: 1px solid rgba(36, 69, 102, 0.24);
  border-radius: 0.45rem;
  padding: 0.22rem 0.42rem;
  font-size: 0.74rem;
  color: #24466c;
}

.error {
  color: #8a1e35;
}

.empty {
  color: #36516f;
}
</style>
