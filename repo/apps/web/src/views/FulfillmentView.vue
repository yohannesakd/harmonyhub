<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

import FulfillmentQueuePanel from '@/components/fulfillment/FulfillmentQueuePanel.vue'
import AppShell from '@/components/layout/AppShell.vue'
import { useWorkspaceContext } from '@/composables/useWorkspaceContext'
import {
  fetchDeliveryFulfillmentQueue,
  fetchPickupFulfillmentQueue,
  transitionFulfillmentOrder,
  verifyPickupCodeForHandoff,
} from '@/services/api'
import { toDisplayErrorMessage } from '@/utils/displayErrors'
import type { ActiveContext, FulfillmentQueueOrder, FulfillmentTransitionStatus } from '@/types'

const { authStore, contextStore, bootstrapWorkspace, switchWorkspaceContext } = useWorkspaceContext()

const loading = ref(false)
const saving = ref(false)
const errorMessage = ref<string | null>(null)
const pickupQueue = ref<FulfillmentQueueOrder[]>([])
const deliveryQueue = ref<FulfillmentQueueOrder[]>([])
let queueRefreshTimer: ReturnType<typeof setInterval> | null = null

const canManageFulfillment = computed(() => authStore.permissions.includes('fulfillment.manage'))

async function loadQueues() {
  const [pickup, delivery] = await Promise.all([fetchPickupFulfillmentQueue(), fetchDeliveryFulfillmentQueue()])
  pickupQueue.value = pickup
  deliveryQueue.value = delivery
}

async function loadPage() {
  loading.value = true
  errorMessage.value = null
  try {
    await bootstrapWorkspace()
    if (!canManageFulfillment.value) {
      pickupQueue.value = []
      deliveryQueue.value = []
      return
    }
    await loadQueues()
  } catch (error) {
    errorMessage.value = toDisplayErrorMessage(error, 'Unable to load fulfillment queues')
  } finally {
    loading.value = false
  }
}

async function handleSwitchContext(next: ActiveContext) {
  try {
    await switchWorkspaceContext(next)
    await loadPage()
  } catch {
    // Context-switch errors already surfaced by context store.
  }
}

async function withSaving(operation: () => Promise<void>) {
  saving.value = true
  errorMessage.value = null
  try {
    await operation()
  } catch (error) {
    errorMessage.value = toDisplayErrorMessage(error, 'Fulfillment action failed')
  } finally {
    saving.value = false
  }
}

async function handlePageVisibilityChange() {
  if (document.visibilityState !== 'visible' || !canManageFulfillment.value || loading.value || saving.value) {
    return
  }
  try {
    await loadQueues()
  } catch {
    // Keep current queue state if opportunistic refresh fails.
  }
}

async function handleTransition(orderId: string, targetStatus: FulfillmentTransitionStatus, cancelReason?: string) {
  await withSaving(async () => {
    await transitionFulfillmentOrder(orderId, {
      target_status: targetStatus,
      cancel_reason: cancelReason,
    })
    await loadQueues()
  })
}

async function handleVerifyPickup(orderId: string, code: string) {
  await withSaving(async () => {
    await verifyPickupCodeForHandoff(orderId, code)
    await loadQueues()
  })
}

onMounted(async () => {
  await loadPage()
  document.addEventListener('visibilitychange', handlePageVisibilityChange)
  queueRefreshTimer = setInterval(() => {
    if (!canManageFulfillment.value || loading.value || saving.value) {
      return
    }
    void loadQueues()
  }, 30_000)
})

onUnmounted(() => {
  document.removeEventListener('visibilitychange', handlePageVisibilityChange)
  if (queueRefreshTimer) {
    clearInterval(queueRefreshTimer)
  }
})
</script>

<template>
  <AppShell
    :contexts="contextStore.contexts"
    :active-context="contextStore.activeContext"
    :switching-context="contextStore.switching"
    @switch-context="handleSwitchContext"
  >
    <section class="fulfillment-page">
      <header class="fulfillment-page__header">
        <p class="eyebrow">Fulfillment + handoff</p>
        <h2>Run pickup and delivery queues with strict, service-aware status transitions.</h2>
        <p>
          Pickup requires a valid rotating code at handoff. Delivery runs through dispatch and completion with audited state changes.
        </p>
      </header>

      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      <p v-if="contextStore.errorMessage" class="error">{{ contextStore.errorMessage }}</p>

      <p v-if="loading">Loading fulfillment workspace…</p>

      <p v-else-if="!canManageFulfillment" class="denied">
        Your current role does not include fulfillment operations in this context.
      </p>

      <div v-else class="fulfillment-page__queues">
        <FulfillmentQueuePanel
          title="Pickup queue"
          subtitle="Confirmed pickup orders move to prep, then ready-for-pickup, then verified handoff."
          queue-type="pickup"
          :orders="pickupQueue"
          :loading="loading"
          :saving="saving"
          @transition="handleTransition"
          @verify-pickup-code="handleVerifyPickup"
        />

        <FulfillmentQueuePanel
          title="Delivery queue"
          subtitle="Confirmed delivery orders move through prep, dispatch readiness, route handoff, and delivery completion."
          queue-type="delivery"
          :orders="deliveryQueue"
          :loading="loading"
          :saving="saving"
          @transition="handleTransition"
          @verify-pickup-code="handleVerifyPickup"
        />
      </div>
    </section>
  </AppShell>
</template>

<style scoped>
.fulfillment-page {
  display: grid;
  gap: 1rem;
}

.fulfillment-page__header {
  border: 1px solid rgba(21, 39, 61, 0.15);
  border-radius: 1rem;
  padding: 1rem;
  background:
    radial-gradient(circle at 12% 22%, rgba(108, 214, 255, 0.2), transparent 34%),
    radial-gradient(circle at 86% 76%, rgba(122, 246, 188, 0.2), transparent 36%),
    rgba(248, 252, 255, 0.94);
}

.eyebrow {
  margin: 0;
  font-size: 0.73rem;
  letter-spacing: 0.19em;
  text-transform: uppercase;
  color: #2a4f75;
}

h2 {
  margin: 0.3rem 0 0;
  font-family: 'Fraunces', serif;
}

.fulfillment-page__header p {
  margin: 0.2rem 0 0;
  color: #2f4e6f;
}

.fulfillment-page__queues {
  display: grid;
  gap: 0.9rem;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
}

.error {
  margin: 0;
  color: #8a1e35;
}

.denied {
  margin: 0;
  color: #34506e;
}
</style>
