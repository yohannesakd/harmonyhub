<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import SyncStatusBadge from '@/components/common/SyncStatusBadge.vue'
import ContextSwitcher from '@/components/context/ContextSwitcher.vue'
import { writeQueueSingleton } from '@/offline/writeQueue'
import { useAuthStore } from '@/stores/auth'
import { useSyncStore } from '@/stores/sync'
import type { ActiveContext, ContextChoice } from '@/types'

const props = defineProps<{
  contexts: ContextChoice[]
  activeContext: ActiveContext | null
  switchingContext?: boolean
}>()

const emit = defineEmits<{
  switchContext: [context: ActiveContext]
}>()

const authStore = useAuthStore()
const syncStore = useSyncStore()
const router = useRouter()
const route = useRoute()

syncStore.initializeNetworkListener()

const queueScopeKey = computed(() => {
  if (!authStore.user || !authStore.activeContext) {
    return null
  }
  const ctx = authStore.activeContext
  return `${authStore.user.id}:${ctx.organization_id}:${ctx.program_id}:${ctx.event_id}:${ctx.store_id}`
})

const canManageRecommendations = computed(() => authStore.permissions.includes('recommendations.manage'))

const canViewRoster = computed(() => {
  const role = authStore.activeContext?.role
  if (!role) {
    return false
  }
  return authStore.permissions.includes('directory.view') && ['referee', 'staff', 'administrator'].includes(role)
})

function syncQueueBadgeState() {
  if (!queueScopeKey.value || !authStore.user) {
    syncStore.setQueueItems([])
    return
  }
  syncStore.setQueueItems(writeQueueSingleton.listForScope(queueScopeKey.value, authStore.user.id))
}

watch(queueScopeKey, syncQueueBadgeState, { immediate: true })

async function signOut() {
  await authStore.signOut()
  await router.replace('/login')
}

function onSwitchContext(context: ActiveContext) {
  emit('switchContext', context)
}
</script>

<template>
  <div class="shell">
    <a class="shell__skip-link" href="#main-content">Skip to main content</a>

    <header class="shell__header">
      <div>
        <p class="shell__eyebrow">HarmonyHub</p>
        <h1 class="shell__title">Performing Arts + Concessions Portal</h1>
        <p v-if="authStore.activeContext" class="shell__subtext">
          Signed in as <strong>{{ authStore.user?.username }}</strong> · role <strong>{{ authStore.activeContext.role }}</strong>
        </p>
      </div>

      <div class="shell__meta">
        <nav class="shell__nav" aria-label="Main">
          <RouterLink to="/dashboard" :class="{ 'shell__nav-link--active': route.path.startsWith('/dashboard') }"
            >Dashboard</RouterLink
          >
          <RouterLink to="/directory" :class="{ 'shell__nav-link--active': route.path.startsWith('/directory') }"
            >Directory</RouterLink
          >
          <RouterLink to="/repertoire" :class="{ 'shell__nav-link--active': route.path.startsWith('/repertoire') }"
            >Repertoire</RouterLink
          >
          <RouterLink
            to="/recommendations"
            v-if="canManageRecommendations"
            :class="{ 'shell__nav-link--active': route.path.startsWith('/recommendations') }"
            >Recommendations</RouterLink
          >
          <RouterLink to="/roster" v-if="canViewRoster" :class="{ 'shell__nav-link--active': route.path.startsWith('/roster') }"
            >Roster</RouterLink
          >
          <RouterLink to="/ordering" :class="{ 'shell__nav-link--active': route.path.startsWith('/ordering') }"
            >Ordering</RouterLink
          >
          <RouterLink
            v-if="authStore.permissions.includes('fulfillment.manage')"
            to="/fulfillment"
            :class="{ 'shell__nav-link--active': route.path.startsWith('/fulfillment') }"
            >Fulfillment</RouterLink
          >
          <RouterLink
            v-if="
              authStore.permissions.includes('imports.manage') || authStore.permissions.includes('account_control.manage')
            "
            to="/imports-admin"
            :class="{ 'shell__nav-link--active': route.path.startsWith('/imports-admin') }"
            >Imports & Accounts</RouterLink
          >
          <RouterLink
            v-if="
              authStore.permissions.includes('operations.view') ||
              authStore.permissions.includes('audit.view') ||
              authStore.permissions.includes('export.manage') ||
              authStore.permissions.includes('backup.manage') ||
              authStore.permissions.includes('recovery_drill.manage')
            "
            to="/operations"
            :class="{ 'shell__nav-link--active': route.path.startsWith('/operations') }"
            >Operations</RouterLink
          >
          <RouterLink
            v-if="authStore.permissions.includes('abac.policy.manage')"
            to="/policy-management"
            :class="{ 'shell__nav-link--active': route.path.startsWith('/policy-management') }"
            >Policy Management</RouterLink
          >
        </nav>
        <ContextSwitcher
          :contexts="props.contexts"
          :active-context="props.activeContext"
          :disabled="props.switchingContext"
          @switch="onSwitchContext"
        />
        <SyncStatusBadge />
        <button class="shell__logout" type="button" @click="signOut">Sign out</button>
      </div>
    </header>

    <main id="main-content" class="shell__content" tabindex="-1">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.shell {
  position: relative;
  min-height: 100vh;
  padding: clamp(1rem, 2.2vw, 2rem);
}

.shell__skip-link {
  position: absolute;
  left: 1rem;
  top: 0;
  transform: translateY(-140%);
  background: #fff;
  color: #102640;
  border: 1px solid rgba(16, 38, 64, 0.35);
  border-radius: 0.5rem;
  padding: 0.45rem 0.7rem;
  font-size: 0.82rem;
  text-decoration: none;
  z-index: 40;
}

.shell__skip-link:focus-visible {
  transform: translateY(0.2rem);
}

.shell__header {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
  padding: 1.25rem;
  border-radius: 1rem;
  background: linear-gradient(128deg, rgba(17, 37, 67, 0.92), rgba(34, 10, 46, 0.92));
  color: #f4f0e5;
  border: 1px solid rgba(255, 255, 255, 0.14);
  box-shadow: 0 18px 28px rgba(15, 15, 35, 0.3);
}

.shell__eyebrow {
  margin: 0;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  opacity: 0.8;
}

.shell__title {
  margin: 0.35rem 0 0;
  font-family: 'Fraunces', serif;
  font-size: clamp(1.2rem, 2.2vw, 1.65rem);
  font-weight: 600;
}

.shell__subtext {
  margin: 0.55rem 0 0;
  font-size: 0.82rem;
  opacity: 0.92;
}

.shell__meta {
  display: grid;
  justify-items: start;
  gap: 0.7rem;
}

.shell__nav {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.shell__nav a {
  text-decoration: none;
  color: #f7f2e8;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 0.5rem;
  padding: 0.26rem 0.56rem;
  font-size: 0.8rem;
}

.shell__nav-link--active {
  background: rgba(255, 255, 255, 0.18);
}

.shell__logout {
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 0.6rem;
  background: transparent;
  color: #f7f2e8;
  padding: 0.45rem 0.8rem;
  cursor: pointer;
}

.shell__content {
  margin-top: 1rem;
}
</style>
