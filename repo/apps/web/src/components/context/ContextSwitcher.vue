<script setup lang="ts">
import { computed } from 'vue'

import type { ActiveContext, ContextChoice } from '@/types'

const props = defineProps<{
  contexts: ContextChoice[]
  activeContext: ActiveContext | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  switch: [context: ActiveContext]
}>()

const activeKey = computed(() => {
  if (!props.activeContext) {
    return ''
  }
  return `${props.activeContext.organization_id}:${props.activeContext.program_id}:${props.activeContext.event_id}:${props.activeContext.store_id}:${props.activeContext.role}`
})

function onChange(event: Event) {
  const target = event.target as HTMLSelectElement
  const [organization_id, program_id, event_id, store_id, role] = target.value.split(':')
  if (!organization_id || !program_id || !event_id || !store_id || !role) {
    return
  }
  emit('switch', { organization_id, program_id, event_id, store_id, role: role as ActiveContext['role'] })
}
</script>

<template>
  <label class="context-switcher">
    <span>Active context</span>
    <select :value="activeKey" :disabled="disabled" @change="onChange">
      <option v-for="context in contexts" :key="`${context.organization_id}:${context.program_id}:${context.event_id}:${context.store_id}:${context.role}`" :value="`${context.organization_id}:${context.program_id}:${context.event_id}:${context.store_id}:${context.role}`">
        {{ context.organization_name }} · {{ context.program_name }} · {{ context.event_name }} · {{ context.store_name }} ({{ context.role }})
      </option>
    </select>
  </label>
</template>

<style scoped>
.context-switcher {
  display: grid;
  gap: 0.35rem;
  font-size: 0.8rem;
  color: #d6e4ff;
}

select {
  min-width: min(520px, 100%);
  padding: 0.5rem 0.7rem;
  border-radius: 0.55rem;
  border: 1px solid rgba(255, 255, 255, 0.35);
  background: rgba(6, 12, 27, 0.34);
  color: #f3f4f6;
}
</style>
