<script setup lang="ts">
defineProps<{
  title: string
  value: string
}>()
</script>

<template>
  <article class="context-card">
    <p class="context-card__title">{{ title }}</p>
    <p class="context-card__value">{{ value }}</p>
  </article>
</template>

<style scoped>
.context-card {
  border-radius: 0.9rem;
  border: 1px solid rgba(27, 46, 81, 0.18);
  background: rgba(255, 255, 255, 0.8);
  padding: 0.95rem;
  box-shadow: 0 10px 18px rgba(18, 32, 56, 0.08);
}

.context-card__title {
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.72rem;
  color: #395277;
}

.context-card__value {
  margin: 0.35rem 0 0;
  font-weight: 600;
  color: #1b2940;
}
</style>
