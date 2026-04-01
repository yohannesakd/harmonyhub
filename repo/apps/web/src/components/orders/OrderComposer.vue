<script setup lang="ts">
import { computed, reactive, watch } from 'vue'

import type { AddressBookEntry, MenuItem, Order, OrderLineInput, OrderType, SyncStatus } from '@/types'

const props = defineProps<{
  menuItems: MenuItem[]
  addresses: AddressBookEntry[]
  currentOrder: Order | null
  loading: boolean
  saving: boolean
  networkOnline: boolean
  quoteConflictSlots: string[]
  currentOrderSyncState?: SyncStatus | null
  currentOrderSyncError?: string | null
  queuedConfirmConflict?: { message: string; nextSlots: string[] } | null
}>()

const emit = defineEmits<{
  saveDraft: [payload: { order_type: OrderType; slot_start: string; address_book_entry_id?: string; lines: OrderLineInput[] }]
  quote: []
  confirm: []
  cancel: []
  chooseSuggestedSlot: [slotStart: string]
}>()

const form = reactive<{
  orderType: OrderType
  slotStart: string
  addressId: string
  quantities: Record<string, number>
}>({
  orderType: 'pickup',
  slotStart: '',
  addressId: '',
  quantities: {},
})

const hasExistingOrder = computed(() => Boolean(props.currentOrder?.id))
const hasQuotedOrder = computed(() => props.currentOrder?.status === 'quoted')

function toDateTimeLocal(iso: string): string {
  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`
}

function toIso(value: string): string | null {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return null
  }
  return parsed.toISOString()
}

watch(
  () => props.currentOrder,
  (order) => {
    if (!order) {
      return
    }
    form.orderType = order.order_type
    form.slotStart = toDateTimeLocal(order.slot_start)
    form.addressId = order.address_book_entry_id ?? ''
    form.quantities = {}
    for (const line of order.lines) {
      form.quantities[line.menu_item_id] = line.quantity
    }
  },
  { immediate: true },
)

const lineSubtotal = computed(() => {
  return props.menuItems.reduce((acc, item) => acc + item.price_cents * (form.quantities[item.id] ?? 0), 0)
})

const selectedLineItems = computed<OrderLineInput[]>(() => {
  return Object.entries(form.quantities)
    .filter(([, quantity]) => quantity > 0)
    .map(([menuItemId, quantity]) => ({ menu_item_id: menuItemId, quantity }))
})

const canSaveDraft = computed(() => {
  const hasSlot = toIso(form.slotStart) !== null
  const hasLines = selectedLineItems.value.length > 0
  const addressValid = form.orderType === 'pickup' || form.addressId.length > 0
  return hasSlot && hasLines && addressValid
})

const canQuote = computed(() => hasExistingOrder.value && props.networkOnline)

const confirmLabel = computed(() => (props.networkOnline ? 'Finalize checkout' : 'Queue finalize (offline)'))

function saveDraft() {
  const slotIso = toIso(form.slotStart)
  if (!slotIso) {
    return
  }
  emit('saveDraft', {
    order_type: form.orderType,
    slot_start: slotIso,
    address_book_entry_id: form.orderType === 'delivery' ? form.addressId : undefined,
    lines: selectedLineItems.value,
  })
}

function chooseSlot(slotStartIso: string) {
  form.slotStart = toDateTimeLocal(slotStartIso)
  emit('chooseSuggestedSlot', slotStartIso)
}
</script>

<template>
  <section class="order-composer">
    <header>
      <h3>Order flow</h3>
      <p>Create/update draft, quote with capacity checks, then confirm checkout.</p>
    </header>

    <div class="order-composer__controls">
      <label>
        Fulfillment type
        <select v-model="form.orderType" name="order_type" autocomplete="off" :disabled="saving || loading">
          <option value="pickup">Pickup</option>
          <option value="delivery">Delivery</option>
        </select>
      </label>

      <label>
        15-minute slot
        <input
          v-model="form.slotStart"
          name="slot_start"
          autocomplete="off"
          :disabled="saving || loading"
          type="datetime-local"
          step="900"
        />
      </label>

      <label v-if="form.orderType === 'delivery'">
        Delivery address
        <select v-model="form.addressId" name="address_book_entry_id" autocomplete="off" :disabled="saving || loading">
          <option value="">Select address…</option>
          <option v-for="address in addresses" :key="address.id" :value="address.id">
            {{ address.label }} · {{ address.postal_code }}
          </option>
        </select>
      </label>
    </div>

    <div class="order-composer__menu">
      <article v-for="item in menuItems" :key="item.id">
        <p>
          <strong>{{ item.name }}</strong>
          <span>{{ (item.price_cents / 100).toFixed(2) }}</span>
        </p>
        <p v-if="item.description" class="order-composer__description">{{ item.description }}</p>
        <label>
          Qty
          <input
            v-model.number="form.quantities[item.id]"
            :name="`quantity_${item.id}`"
            autocomplete="off"
            inputmode="numeric"
            :disabled="saving || loading"
            type="number"
            min="0"
            max="50"
          />
        </label>
      </article>
    </div>

    <p class="order-composer__subtotal">Draft subtotal: ${{ (lineSubtotal / 100).toFixed(2) }}</p>

    <div class="order-composer__actions">
      <button type="button" :disabled="!canSaveDraft || saving || loading" @click="saveDraft">
        {{ hasExistingOrder ? 'Update draft' : 'Create draft' }}
      </button>
      <button type="button" class="secondary" :disabled="!canQuote || saving || loading" @click="emit('quote')">
        Quote
      </button>
      <button type="button" class="confirm" :disabled="!hasQuotedOrder || saving || loading" @click="emit('confirm')">
        {{ confirmLabel }}
      </button>
      <button type="button" class="danger" :disabled="!hasExistingOrder || saving || loading" @click="emit('cancel')">
        Cancel order
      </button>
    </div>

    <p v-if="!networkOnline" class="order-composer__offline-note" role="status" aria-live="polite" aria-atomic="true">
      Offline: draft and address writes are queued with protected local payload storage. Quote remains online-only. Finalize will be
      queued and server-validated on reconnect.
    </p>

    <p
      v-if="currentOrderSyncState"
      class="order-composer__sync-state"
      :class="`order-composer__sync-state--${currentOrderSyncState}`"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      Current order sync: {{ currentOrderSyncState }}
    </p>
    <p v-if="currentOrderSyncError" class="order-composer__sync-error" role="alert" aria-live="assertive" aria-atomic="true">
      {{ currentOrderSyncError }}
    </p>

    <section v-if="quoteConflictSlots.length > 0" class="order-composer__conflict" role="alert" aria-live="assertive" aria-atomic="true">
      <p>Requested slot is at capacity. Suggested next slots:</p>
      <div>
        <button
          v-for="slot in quoteConflictSlots"
          :key="slot"
          type="button"
          class="secondary"
          :disabled="saving || loading"
          @click="chooseSlot(slot)"
        >
          {{ slot }}
        </button>
      </div>
    </section>

    <section v-if="queuedConfirmConflict" class="order-composer__conflict" role="alert" aria-live="assertive" aria-atomic="true">
      <p>
        Queued finalize was rejected by server: <strong>{{ queuedConfirmConflict.message }}</strong>
      </p>
      <div v-if="queuedConfirmConflict.nextSlots.length > 0">
        <button
          v-for="slot in queuedConfirmConflict.nextSlots"
          :key="slot"
          type="button"
          class="secondary"
          :disabled="saving || loading"
          @click="chooseSlot(slot)"
        >
          {{ slot }}
        </button>
      </div>
    </section>
  </section>
</template>

<style scoped>
.order-composer {
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

.order-composer__controls {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 0.55rem;
}

label {
  display: grid;
  gap: 0.2rem;
  font-size: 0.82rem;
  color: #2b4561;
}

select,
input {
  border: 1px solid rgba(30, 51, 76, 0.2);
  border-radius: 0.5rem;
  padding: 0.4rem 0.5rem;
}

.order-composer__menu {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.5rem;
}

.order-composer__menu article {
  border: 1px solid rgba(27, 50, 76, 0.14);
  border-radius: 0.7rem;
  padding: 0.6rem;
}

.order-composer__menu p {
  margin: 0;
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
}

.order-composer__description {
  margin-top: 0.35rem !important;
  color: #3f5c79;
  font-size: 0.8rem;
}

.order-composer__subtotal {
  margin: 0;
  color: #274462;
}

.order-composer__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

button {
  border: none;
  border-radius: 0.5rem;
  background: #1d4673;
  color: #fff;
  padding: 0.42rem 0.66rem;
  cursor: pointer;
}

.secondary {
  background: rgba(22, 34, 55, 0.1);
  color: #1f3450;
}

.confirm {
  background: #2b6d45;
}

.danger {
  background: #7c2342;
}

.order-composer__conflict {
  border: 1px dashed rgba(142, 30, 53, 0.35);
  border-radius: 0.65rem;
  padding: 0.65rem;
  color: #7e1b36;
}

.order-composer__offline-note {
  margin: 0;
  color: #34506e;
  font-size: 0.82rem;
}

.order-composer__sync-state,
.order-composer__sync-error {
  margin: 0;
  font-size: 0.8rem;
}

.order-composer__sync-state--local_queued,
.order-composer__sync-state--syncing {
  color: #734d00;
}

.order-composer__sync-state--server_committed {
  color: #0b5e47;
}

.order-composer__sync-state--failed_retrying,
.order-composer__sync-state--conflict,
.order-composer__sync-error {
  color: #8a1e35;
}

.order-composer__conflict p {
  margin: 0 0 0.45rem;
}

.order-composer__conflict div {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}
</style>
