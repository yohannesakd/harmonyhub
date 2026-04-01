<script setup lang="ts">
import { computed } from 'vue'

import type { DirectoryEntryCard } from '@/types'

const props = defineProps<{
  entry: DirectoryEntryCard
  revealing?: boolean
}>()

const emit = defineEmits<{
  reveal: [entryId: string]
}>()

const canRequestReveal = computed(() => props.entry.contact.masked && props.entry.can_reveal_contact)

function formatDate(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed)
}

function requestReveal() {
  emit('reveal', props.entry.id)
}
</script>

<template>
  <article class="directory-card">
    <header class="directory-card__header">
      <div>
        <h3>{{ entry.display_name }}</h3>
        <p v-if="entry.stage_name" class="directory-card__stage">Stage: {{ entry.stage_name }}</p>
      </div>
      <p class="directory-card__region">{{ entry.region }}</p>
    </header>

    <p class="directory-card__meta"><strong>Repertoire:</strong> {{ entry.repertoire.join(', ') || '—' }}</p>
    <p class="directory-card__meta"><strong>Tags:</strong> {{ entry.tags.join(', ') || '—' }}</p>

    <section class="directory-card__availability">
      <strong>Availability windows</strong>
      <ul>
        <li v-for="window in entry.availability_windows" :key="`${window.starts_at}-${window.ends_at}`">
          {{ formatDate(window.starts_at) }} → {{ formatDate(window.ends_at) }}
        </li>
      </ul>
    </section>

    <section class="directory-card__contact">
      <strong>Contact</strong>
      <p>{{ entry.contact.email ?? '—' }}</p>
      <p>{{ entry.contact.phone ?? '—' }}</p>
      <p>{{ entry.contact.address_line1 ?? '—' }}</p>

      <button v-if="canRequestReveal" :disabled="revealing" type="button" @click="requestReveal">
        {{ revealing ? 'Revealing…' : 'Reveal contact details' }}
      </button>
    </section>
  </article>
</template>

<style scoped>
.directory-card {
  border: 1px solid rgba(16, 36, 61, 0.16);
  border-radius: 0.9rem;
  background: rgba(255, 255, 255, 0.92);
  padding: 0.9rem;
  display: grid;
  gap: 0.65rem;
}

.directory-card__header {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
}

h3 {
  margin: 0;
  font-family: 'Fraunces', serif;
}

.directory-card__stage,
.directory-card__meta,
.directory-card__region {
  margin: 0;
  color: #2e4762;
}

.directory-card__availability ul {
  margin: 0.35rem 0 0;
  padding-left: 1rem;
}

.directory-card__contact p {
  margin: 0.18rem 0;
}

button {
  margin-top: 0.55rem;
  border: none;
  border-radius: 0.5rem;
  padding: 0.46rem 0.68rem;
  background: #4c2c75;
  color: #fff;
  cursor: pointer;
}

button:disabled {
  opacity: 0.65;
  cursor: progress;
}
</style>
