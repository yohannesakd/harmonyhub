<script setup lang="ts">
import { computed, reactive } from 'vue'

import type { FulfillmentQueueOrder, FulfillmentTransitionStatus } from '@/types'

const props = defineProps<{
  title: string
  subtitle: string
  queueType: 'pickup' | 'delivery'
  orders: FulfillmentQueueOrder[]
  loading: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  transition: [orderId: string, targetStatus: FulfillmentTransitionStatus, cancelReason?: string]
  verifyPickupCode: [orderId: string, code: string]
}>()

const pickupCodes = reactive<Record<string, string>>({})

const sortedOrders = computed(() => {
  return [...props.orders].sort((a, b) => a.slot_start.localeCompare(b.slot_start))
})

function transitionOptions(order: FulfillmentQueueOrder): Array<{ label: string; status: FulfillmentTransitionStatus }> {
  if (props.queueType === 'pickup') {
    if (order.status === 'confirmed') return [{ label: 'Start preparing', status: 'preparing' }]
    if (order.status === 'preparing') return [{ label: 'Mark ready for pickup', status: 'ready_for_pickup' }]
    if (order.status === 'ready_for_pickup') return [{ label: 'Cancel order', status: 'cancelled' }]
    return []
  }

  if (order.status === 'confirmed') return [{ label: 'Start preparing', status: 'preparing' }]
  if (order.status === 'preparing') return [{ label: 'Ready for dispatch', status: 'ready_for_dispatch' }]
  if (order.status === 'ready_for_dispatch') {
    return [
      { label: 'Out for delivery', status: 'out_for_delivery' },
      { label: 'Cancel order', status: 'cancelled' },
    ]
  }
  if (order.status === 'out_for_delivery') return [{ label: 'Mark delivered', status: 'delivered' }]
  return []
}

function onTransition(order: FulfillmentQueueOrder, targetStatus: FulfillmentTransitionStatus) {
  const cancelReason = targetStatus === 'cancelled' ? 'Cancelled by fulfillment operator' : undefined
  emit('transition', order.id, targetStatus, cancelReason)
}

function onVerifyPickup(order: FulfillmentQueueOrder) {
  const code = (pickupCodes[order.id] ?? '').trim()
  if (!/^\d{6}$/.test(code)) {
    return
  }
  emit('verifyPickupCode', order.id, code)
  pickupCodes[order.id] = ''
}
</script>

<template>
  <section class="queue-panel">
    <header class="queue-panel__header">
      <div>
        <h3>{{ title }}</h3>
        <p>{{ subtitle }}</p>
      </div>
      <span class="queue-panel__count">{{ orders.length }} active</span>
    </header>

    <ul class="queue-panel__list">
      <li v-for="order in sortedOrders" :key="order.id" class="queue-card">
        <div class="queue-card__meta">
          <p class="queue-card__heading">
            <strong>#{{ order.id.slice(0, 8) }}</strong>
            <span>{{ order.username }}</span>
          </p>
          <p>
            Status <strong>{{ order.status }}</strong> · Slot <strong>{{ order.slot_start }}</strong> · ETA
            <strong>{{ order.eta_minutes ?? '—' }} min</strong>
          </p>
          <p>
            Total <strong>${{ (order.total_cents / 100).toFixed(2) }}</strong>
            <span v-if="order.address"> · {{ order.address.city }}, {{ order.address.state }} {{ order.address.postal_code }}</span>
          </p>
          <ul>
            <li v-for="line in order.lines" :key="line.id">{{ line.item_name }} × {{ line.quantity }}</li>
          </ul>
        </div>

        <div class="queue-card__actions">
          <button
            v-for="action in transitionOptions(order)"
            :key="`${order.id}-${action.status}`"
            type="button"
            :disabled="loading || saving"
            :class="{ warn: action.status === 'cancelled' }"
            @click="onTransition(order, action.status)"
          >
            {{ action.label }}
          </button>

          <div v-if="queueType === 'pickup' && order.status === 'ready_for_pickup'" class="queue-card__verify">
            <label>
              Pickup code
              <input
                v-model="pickupCodes[order.id]"
                :disabled="loading || saving"
                inputmode="numeric"
                maxlength="6"
                placeholder="6-digit code"
              />
            </label>
            <button type="button" class="accent" :disabled="loading || saving" @click="onVerifyPickup(order)">
              Verify + hand off
            </button>
          </div>
        </div>
      </li>
      <li v-if="orders.length === 0" class="queue-panel__empty">No active orders in this queue.</li>
    </ul>
  </section>
</template>

<style scoped>
.queue-panel {
  border: 1px solid rgba(16, 37, 56, 0.15);
  border-radius: 1.1rem;
  background:
    radial-gradient(circle at 12% 18%, rgba(130, 193, 255, 0.18), transparent 36%),
    radial-gradient(circle at 88% 80%, rgba(172, 255, 218, 0.22), transparent 32%),
    rgba(250, 252, 255, 0.92);
  box-shadow: 0 18px 28px rgba(18, 32, 48, 0.08);
  padding: 1rem;
  display: grid;
  gap: 0.8rem;
}

.queue-panel__header {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  align-items: baseline;
}

h3 {
  margin: 0;
  font-family: 'Fraunces', serif;
  font-size: 1.15rem;
}

.queue-panel__header p {
  margin: 0.25rem 0 0;
  color: #34506e;
  font-size: 0.83rem;
}

.queue-panel__count {
  font-size: 0.8rem;
  color: #295274;
  background: rgba(29, 70, 115, 0.08);
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
}

.queue-panel__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.65rem;
}

.queue-card {
  border: 1px solid rgba(20, 46, 74, 0.15);
  border-radius: 0.85rem;
  background: rgba(255, 255, 255, 0.85);
  padding: 0.75rem;
  display: grid;
  gap: 0.7rem;
}

.queue-card__heading {
  margin: 0;
  display: flex;
  gap: 0.55rem;
  align-items: center;
}

.queue-card__meta p {
  margin: 0.2rem 0 0;
  color: #2e4b68;
  font-size: 0.84rem;
}

.queue-card__meta ul {
  margin: 0.35rem 0 0;
  padding-left: 1rem;
  color: #34506d;
  font-size: 0.82rem;
}

.queue-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

button {
  border: none;
  border-radius: 0.5rem;
  background: #1d4673;
  color: #fff;
  padding: 0.42rem 0.62rem;
  cursor: pointer;
}

.accent {
  background: #2a6c4e;
}

.warn {
  background: #7f2444;
}

.queue-card__verify {
  display: flex;
  gap: 0.45rem;
  align-items: end;
}

label {
  display: grid;
  gap: 0.2rem;
  font-size: 0.78rem;
  color: #2f4d6c;
}

input {
  border: 1px solid rgba(30, 51, 76, 0.2);
  border-radius: 0.5rem;
  padding: 0.4rem 0.5rem;
  width: 8.4rem;
}

.queue-panel__empty {
  color: #405e7d;
  font-size: 0.88rem;
}
</style>
