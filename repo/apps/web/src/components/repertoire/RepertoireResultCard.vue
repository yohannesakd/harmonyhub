<script setup lang="ts">
import type { RepertoireItemCard } from '@/types'

defineProps<{
  item: RepertoireItemCard
}>()
</script>

<template>
  <article class="repertoire-card">
    <header>
      <h3>{{ item.title }}</h3>
      <p class="composer">{{ item.composer ?? 'Composer unavailable' }}</p>
    </header>

    <p><strong>Tags:</strong> {{ item.tags.join(', ') || '—' }}</p>
    <p><strong>Performers:</strong> {{ item.performer_names.join(', ') || '—' }}</p>
    <p><strong>Regions:</strong> {{ item.regions.join(', ') || '—' }}</p>
  </article>
</template>

<style scoped>
.repertoire-card {
  border: 1px solid rgba(20, 38, 61, 0.16);
  border-radius: 0.9rem;
  background: rgba(255, 255, 255, 0.92);
  padding: 0.9rem;
  display: grid;
  gap: 0.45rem;
}

header {
  display: grid;
  gap: 0.25rem;
}

h3 {
  margin: 0;
  font-family: 'Fraunces', serif;
}

.composer,
p {
  margin: 0;
  color: #2f4766;
}
</style>
