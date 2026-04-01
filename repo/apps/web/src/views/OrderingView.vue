<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import AppShell from '@/components/layout/AppShell.vue'
import AddressBookManager from '@/components/orders/AddressBookManager.vue'
import DeliveryZoneManager from '@/components/orders/DeliveryZoneManager.vue'
import OrderComposer from '@/components/orders/OrderComposer.vue'
import SlotCapacityManager from '@/components/orders/SlotCapacityManager.vue'
import { usePollingInterval } from '@/composables/usePollingInterval'
import { useWorkspaceContext } from '@/composables/useWorkspaceContext'
import {
  cacheOrderingSnapshot,
  loadOrderingIdMap,
  loadOrderingSnapshot,
  saveOrderingIdMap,
  type OrderingIdMap,
} from '@/offline/readCache'
import { protectQueuedPayload, unprotectQueuedPayload } from '@/offline/secureQueuePayload'
import { isRetryableQueueError, toQueueConflict, writeQueueSingleton } from '@/offline/writeQueue'
import {
  ApiError,
  cancelOrder,
  confirmOrder,
  createAddress,
  createDeliveryZone,
  createOrderDraft,
  deleteDeliveryZone,
  deleteSlotCapacity,
  deleteAddress,
  fetchMenuItems,
  listDeliveryZones,
  listAddresses,
  listMyOrders,
  listSlotCapacities,
  issuePickupCode,
  quoteOrder,
  updateDeliveryZone,
  updateAddress,
  updateOrderDraft,
  upsertSlotCapacity,
} from '@/services/api'
import { useSyncStore } from '@/stores/sync'
import { toDisplayErrorMessage } from '@/utils/displayErrors'
import type {
  ActiveContext,
  AddressBookEntry,
  AddressBookEntryInput,
  DeliveryZone,
  DeliveryZoneInput,
  MenuItem,
  Order,
  OrderLineInput,
  OrderType,
  QueuedMutation,
  SyncStatus,
  SlotCapacity,
  SlotCapacityInput,
} from '@/types'

const { authStore, contextStore, bootstrapWorkspace, switchWorkspaceContext } = useWorkspaceContext()
const syncStore = useSyncStore()

const loading = ref(false)
const saving = ref(false)
const errorMessage = ref<string | null>(null)
const offlineNotice = ref<string | null>(null)
const quoteConflictSlots = ref<string[]>([])
const menuItems = ref<MenuItem[]>([])
const addresses = ref<AddressBookEntry[]>([])
const deliveryZones = ref<DeliveryZone[]>([])
const slotCapacities = ref<SlotCapacity[]>([])
const orders = ref<Order[]>([])
const currentOrderId = ref<string | null>(null)
const selectedCapacityDate = ref<string>('')
const pickupCode = ref<string | null>(null)
const pickupCodeExpiresAt = ref<string | null>(null)
const queueItems = ref<QueuedMutation[]>([])
const idMap = ref<OrderingIdMap>({ address_ids: {}, order_ids: {} })
const ETA_REFRESH_INTERVAL_MS = 30_000
const etaTrackedStatuses = new Set([
  'quoted',
  'confirmed',
  'preparing',
  'ready_for_pickup',
  'ready_for_dispatch',
  'out_for_delivery',
  'dispatched',
  'handed_off',
])

const canManageScheduling = computed(() => authStore.permissions.includes('scheduling.manage'))
const scopeKey = computed(() => {
  if (!authStore.user || !contextStore.activeContextKey) {
    return null
  }
  return `${authStore.user.id}:${contextStore.activeContextKey}`
})

const addressSyncStates = computed<Record<string, SyncStatus>>(() => {
  const states: Record<string, SyncStatus> = {}
  for (const item of queueItems.value) {
    if (item.entity_type === 'address') {
      states[item.entity_id] = item.status
    }
  }
  return states
})

const addressSyncErrors = computed<Record<string, string | null>>(() => {
  const errors: Record<string, string | null> = {}
  for (const item of queueItems.value) {
    if (item.entity_type === 'address') {
      errors[item.entity_id] = item.last_error
    }
  }
  return errors
})

const currentOrderQueuedConfirmConflict = computed(() => {
  if (!currentOrder.value) {
    return null
  }
  const conflict = queueItems.value.find((item) => {
    if (item.action !== 'order.confirm' || item.status !== 'conflict') {
      return false
    }
    const payload = item.payload as { order_id: string }
    return resolveOrderId(payload.order_id) === currentOrder.value?.id
  })
  if (!conflict?.conflict) {
    return null
  }
  const slots = conflict.conflict.details.next_slots
  return {
    message: conflict.conflict.message,
    nextSlots: Array.isArray(slots) ? (slots as string[]) : [],
  }
})

const canRequestPickupCode = computed(() => {
  if (!currentOrder.value) return false
  if (currentOrder.value.order_type !== 'pickup') return false
  return ['confirmed', 'preparing', 'ready_for_pickup'].includes(currentOrder.value.status)
})

watch(
  () => currentOrder.value?.id,
  () => {
    pickupCode.value = null
    pickupCodeExpiresAt.value = null
  },
)

const currentOrder = computed(() => orders.value.find((row) => row.id === currentOrderId.value) ?? null)

const shouldPollEta = computed(() => {
  if (!currentOrder.value) {
    return false
  }
  return etaTrackedStatuses.has(currentOrder.value.status)
})

function resolveAddressId(addressId: string): string {
  return idMap.value.address_ids[addressId] ?? addressId
}

function resolveOrderId(orderId: string): string {
  return idMap.value.order_ids[orderId] ?? orderId
}

function loadScopeArtifacts() {
  if (!scopeKey.value) {
    idMap.value = { address_ids: {}, order_ids: {} }
    queueItems.value = []
    syncStore.setQueueItems([])
    return
  }

  idMap.value = loadOrderingIdMap(scopeKey.value)
  queueItems.value = writeQueueSingleton.listForScope(scopeKey.value, authStore.user!.id)
  syncStore.setQueueItems(queueItems.value)
}

function persistIdMap() {
  if (!scopeKey.value) {
    return
  }
  saveOrderingIdMap(scopeKey.value, idMap.value)
}

function refreshQueueState() {
  if (!scopeKey.value || !authStore.user) {
    queueItems.value = []
    syncStore.setQueueItems([])
    return
  }

  queueItems.value = writeQueueSingleton.listForScope(scopeKey.value, authStore.user.id)
  syncStore.setQueueItems(queueItems.value)
}

function buildLocalOrderFromDraft(orderId: string, payload: {
  order_type: OrderType
  slot_start: string
  address_book_entry_id?: string
  lines: OrderLineInput[]
}): Order {
  const lines = payload.lines.map((line) => {
    const menu = menuItems.value.find((item) => item.id === line.menu_item_id)
    const unitPrice = menu?.price_cents ?? 0
    return {
      id: `local-line-${line.menu_item_id}`,
      menu_item_id: line.menu_item_id,
      item_name: menu?.name ?? 'Menu item',
      quantity: line.quantity,
      unit_price_cents: unitPrice,
      line_total_cents: unitPrice * line.quantity,
    }
  })
  const subtotal = lines.reduce((acc, line) => acc + line.line_total_cents, 0)
  const now = new Date().toISOString()

  return {
    id: orderId,
    status: 'draft',
    order_type: payload.order_type,
    slot_start: payload.slot_start,
    subtotal_cents: subtotal,
    delivery_fee_cents: payload.order_type === 'pickup' ? 0 : 0,
    total_cents: subtotal,
    eta_minutes: null,
    address_book_entry_id: payload.address_book_entry_id ?? null,
    delivery_zone_id: null,
    conflict_reason: null,
    cancel_reason: null,
    quote_expires_at: null,
    confirmed_at: null,
    preparing_at: null,
    ready_at: null,
    dispatched_at: null,
    handed_off_at: null,
    delivered_at: null,
    pickup_code_expires_at: null,
    pickup_code_rotated_at: null,
    created_at: now,
    updated_at: now,
    lines,
    local_only: true,
    sync_state: 'local_queued',
    sync_error: null,
  }
}

function applyQueueOverlays() {
  const addressMap = new Map(addresses.value.map((entry) => [entry.id, { ...entry, sync_state: undefined, sync_error: null }]))
  const orderMap = new Map(orders.value.map((order) => [order.id, { ...order, sync_state: undefined, sync_error: null }]))

  for (const item of queueItems.value) {
    if (item.entity_type === 'address') {
      if (item.action === 'address.delete' && item.status !== 'conflict') {
        const resolvedAddressId = resolveAddressId(item.entity_id)
        addressMap.delete(item.entity_id)
        addressMap.delete(resolvedAddressId)
        continue
      }

      const target = addressMap.get(item.entity_id) ?? addressMap.get(resolveAddressId(item.entity_id))
      if (target) {
        target.sync_state = item.status
        target.sync_error = item.last_error
      }
      continue
    }

    if (item.entity_type === 'order') {
      const resolvedOrderId = resolveOrderId(item.entity_id)
      const target = orderMap.get(resolvedOrderId) ?? orderMap.get(item.entity_id)
      if (target) {
        target.sync_state = item.status
        target.sync_error = item.last_error
      }
    }
  }

  addresses.value = [...addressMap.values()]
  orders.value = [...orderMap.values()].sort((a, b) => b.updated_at.localeCompare(a.updated_at))
}

function purgeUnsupportedOfflineQueueActions() {
  if (!scopeKey.value || !authStore.user) {
    return
  }

  const supported = new Set(['address.create', 'address.update', 'address.delete', 'order.draft.save', 'order.confirm'])

  writeQueueSingleton.removeWhere((item) => {
    if (item.context_key !== scopeKey.value || item.user_id !== authStore.user!.id) {
      return false
    }
    return !supported.has(item.action)
  })
}

function mapDraftInputForServer(payload: {
  order_type: OrderType
  slot_start: string
  address_book_entry_id?: string
  lines: OrderLineInput[]
}) {
  return {
    ...payload,
    address_book_entry_id: payload.address_book_entry_id ? resolveAddressId(payload.address_book_entry_id) : undefined,
  }
}

async function drainQueuedWrites() {
  if (!scopeKey.value || !authStore.user || !syncStore.networkOnline) {
    return
  }

  await writeQueueSingleton.processScope(scopeKey.value, authStore.user.id, async (item) => {
    if (item.action === 'address.create') {
      const payload = await unprotectQueuedPayload<{ local_address_id: string; input: AddressBookEntryInput }>(
        item.action,
        authStore.user!.id,
        item.payload,
      )
      const created = await createAddress(payload.input)
      idMap.value.address_ids[payload.local_address_id] = created.id
      persistIdMap()
      return { outcome: 'committed' } as const
    }

    if (item.action === 'address.update') {
      const payload = await unprotectQueuedPayload<{ address_id: string; input: AddressBookEntryInput }>(
        item.action,
        authStore.user!.id,
        item.payload,
      )
      const resolvedId = resolveAddressId(payload.address_id)
      if (resolvedId.startsWith('local-address-')) {
        return {
          outcome: 'retry',
          message: 'Waiting for queued address create to commit before update.',
        } as const
      }
      await updateAddress(resolvedId, payload.input)
      return { outcome: 'committed' } as const
    }

    if (item.action === 'address.delete') {
      const payload = item.payload as { address_id: string }
      const resolvedId = resolveAddressId(payload.address_id)
      if (resolvedId.startsWith('local-address-')) {
        return { outcome: 'committed' } as const
      }
      await deleteAddress(resolvedId)
      return { outcome: 'committed' } as const
    }

    if (item.action === 'order.draft.save') {
      const payload = await unprotectQueuedPayload<{
        order_id: string
        input: { order_type: OrderType; slot_start: string; address_book_entry_id?: string; lines: OrderLineInput[] }
      }>(item.action, authStore.user!.id, item.payload)
      const resolvedId = resolveOrderId(payload.order_id)
      const draftInput = mapDraftInputForServer(payload.input)
      const committedOrder = resolvedId.startsWith('local-order-')
        ? await createOrderDraft(draftInput)
        : await updateOrderDraft(resolvedId, draftInput)

      if (resolvedId.startsWith('local-order-')) {
        idMap.value.order_ids[payload.order_id] = committedOrder.id
        persistIdMap()
        if (currentOrderId.value === payload.order_id) {
          currentOrderId.value = committedOrder.id
        }
      }

      return { outcome: 'committed' } as const
    }

    if (item.action === 'order.confirm') {
      const payload = item.payload as { order_id: string }
      const resolvedId = resolveOrderId(payload.order_id)
      if (resolvedId.startsWith('local-order-')) {
        return {
          outcome: 'retry',
          message: 'Waiting for queued draft to sync before finalize.',
        } as const
      }
      try {
        await confirmOrder(resolvedId)
        return { outcome: 'committed' } as const
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          return {
            outcome: 'conflict',
            conflict: toQueueConflict(error),
          } as const
        }
        throw error
      }
    }

    return { outcome: 'committed' } as const
  })

  refreshQueueState()
}

async function refreshData() {
  offlineNotice.value = null
  const hasScope = Boolean(scopeKey.value)

  try {
    const [menu, addressList, myOrders] = await Promise.all([fetchMenuItems(), listAddresses(), listMyOrders()])
    menuItems.value = menu
    addresses.value = addressList
    orders.value = myOrders

    if (canManageScheduling.value) {
      const [zones, capacities] = await Promise.all([
        listDeliveryZones(),
        listSlotCapacities(selectedCapacityDate.value || undefined),
      ])
      deliveryZones.value = zones
      slotCapacities.value = capacities
    } else {
      deliveryZones.value = []
      slotCapacities.value = []
    }

    if (hasScope) {
      cacheOrderingSnapshot(scopeKey.value!, {
        menu_items: menuItems.value,
        delivery_zones: deliveryZones.value,
        slot_capacities: slotCapacities.value,
      })
    }
  } catch (error) {
    const canFallback = hasScope && isRetryableQueueError(error)
    if (!canFallback) {
      throw error
    }

    const cached = loadOrderingSnapshot(scopeKey.value!)
    if (!cached) {
      throw error
    }

    menuItems.value = cached.menu_items
    addresses.value = []
    orders.value = []
    deliveryZones.value = canManageScheduling.value ? cached.delivery_zones : []
    slotCapacities.value = canManageScheduling.value ? cached.slot_capacities : []
    offlineNotice.value =
      'Offline: showing cached menu/scheduling data only. Address and order data require an online connection.'
  }

  refreshQueueState()
  applyQueueOverlays()

  if (!currentOrderId.value && orders.value.length > 0) {
    currentOrderId.value = orders.value[0].id
  }
  if (currentOrderId.value && !orders.value.find((row) => row.id === currentOrderId.value)) {
    currentOrderId.value = orders.value[0]?.id ?? null
  }
}

async function refreshOrderEtaTelemetry() {
  if (
    !syncStore.networkOnline
    || !scopeKey.value
    || !authStore.user
    || loading.value
    || saving.value
    || !shouldPollEta.value
  ) {
    return
  }

  try {
    orders.value = await listMyOrders()
    refreshQueueState()
    applyQueueOverlays()

    if (currentOrderId.value && !orders.value.find((row) => row.id === currentOrderId.value)) {
      currentOrderId.value = orders.value[0]?.id ?? null
    }
  } catch {
    // Keep passive refresh silent; explicit user actions still surface errors.
  }
}

usePollingInterval({
  enabled: computed(() => shouldPollEta.value && syncStore.networkOnline),
  intervalMs: ETA_REFRESH_INTERVAL_MS,
  task: refreshOrderEtaTelemetry,
})

async function loadPage() {
  loading.value = true
  errorMessage.value = null
  try {
    await bootstrapWorkspace()
    loadScopeArtifacts()
    purgeUnsupportedOfflineQueueActions()
    refreshQueueState()
    await drainQueuedWrites()
    await refreshData()
  } catch (error) {
    errorMessage.value = toDisplayErrorMessage(error, 'Unable to load ordering workspace')
  } finally {
    loading.value = false
  }
}

async function handleSwitchContext(next: ActiveContext) {
  try {
    await switchWorkspaceContext(next)
    currentOrderId.value = null
    quoteConflictSlots.value = []
    await loadPage()
  } catch {
    // Context errors surfaced by store.
  }
}

async function handleIssuePickupCode() {
  if (!currentOrder.value || !canRequestPickupCode.value) return
  await withSaving(async () => {
    const issued = await issuePickupCode(currentOrder.value!.id)
    pickupCode.value = issued.code
    pickupCodeExpiresAt.value = issued.expires_at
    await refreshData()
  })
}

async function withSaving(operation: () => Promise<void>) {
  saving.value = true
  errorMessage.value = null
  try {
    await operation()
  } catch (error) {
    errorMessage.value = toDisplayErrorMessage(error, 'Operation failed')
  } finally {
    saving.value = false
  }
}

async function enqueueAddressCreate(payload: AddressBookEntryInput) {
  if (!scopeKey.value || !authStore.user) {
    throw new Error('No active scope for queued address write')
  }

  const localId = `local-address-${crypto.randomUUID()}`
  const protectedPayload = await protectQueuedPayload('address.create', authStore.user.id, {
    local_address_id: localId,
    input: payload,
  })

  writeQueueSingleton.enqueue({
    action: 'address.create',
    entity_type: 'address',
    entity_id: localId,
    context_key: scopeKey.value,
    user_id: authStore.user.id,
    payload: protectedPayload,
  })

  addresses.value = [
    {
      id: localId,
      ...payload,
      line2: payload.line2 ?? null,
      phone: payload.phone ?? null,
      local_only: true,
      sync_state: 'local_queued',
      sync_error: null,
    },
    ...addresses.value,
  ]

  refreshQueueState()
  applyQueueOverlays()
}

async function enqueueAddressUpdate(addressId: string, payload: AddressBookEntryInput) {
  if (!scopeKey.value || !authStore.user) {
    throw new Error('No active scope for queued address write')
  }

  writeQueueSingleton.removeWhere(
    (item) => item.action === 'address.update' && item.entity_id === addressId && item.context_key === scopeKey.value,
  )

  const protectedPayload = await protectQueuedPayload('address.update', authStore.user.id, {
    address_id: addressId,
    input: payload,
  })

  writeQueueSingleton.enqueue({
    action: 'address.update',
    entity_type: 'address',
    entity_id: addressId,
    context_key: scopeKey.value,
    user_id: authStore.user.id,
    payload: protectedPayload,
  })

  addresses.value = addresses.value.map((entry) => {
    if (entry.id !== addressId) {
      return entry
    }
    return {
      ...entry,
      ...payload,
      line2: payload.line2 ?? null,
      phone: payload.phone ?? null,
      sync_state: 'local_queued',
      sync_error: null,
    }
  })

  refreshQueueState()
  applyQueueOverlays()
}

async function enqueueAddressDelete(addressId: string) {
  if (!scopeKey.value || !authStore.user) {
    throw new Error('No active scope for queued address write')
  }

  writeQueueSingleton.enqueue({
    action: 'address.delete',
    entity_type: 'address',
    entity_id: addressId,
    context_key: scopeKey.value,
    user_id: authStore.user.id,
    payload: {
      address_id: addressId,
    },
  })

  addresses.value = addresses.value.filter((entry) => entry.id !== addressId)

  refreshQueueState()
  applyQueueOverlays()
}

async function enqueueDraftSave(
  orderId: string,
  payload: { order_type: OrderType; slot_start: string; address_book_entry_id?: string; lines: OrderLineInput[] },
) {
  if (!scopeKey.value || !authStore.user) {
    throw new Error('No active scope for queued order write')
  }

  writeQueueSingleton.removeWhere(
    (item) => item.action === 'order.draft.save' && item.entity_id === orderId && item.context_key === scopeKey.value,
  )

  const protectedPayload = await protectQueuedPayload('order.draft.save', authStore.user.id, {
    order_id: orderId,
    input: payload,
  })

  writeQueueSingleton.enqueue({
    action: 'order.draft.save',
    entity_type: 'order',
    entity_id: orderId,
    context_key: scopeKey.value,
    user_id: authStore.user.id,
    payload: protectedPayload,
  })

  const existing = orders.value.find((order) => order.id === orderId)
  if (existing) {
    existing.order_type = payload.order_type
    existing.slot_start = payload.slot_start
    existing.address_book_entry_id = payload.address_book_entry_id ?? null
    existing.sync_state = 'local_queued'
    existing.sync_error = null
  } else {
    const localOrder = buildLocalOrderFromDraft(orderId, payload)
    orders.value = [localOrder, ...orders.value]
    currentOrderId.value = localOrder.id
  }

  refreshQueueState()
  applyQueueOverlays()
}

function enqueueOrderConfirm(orderId: string) {
  if (!scopeKey.value || !authStore.user) {
    throw new Error('No active scope for queued order write')
  }
  writeQueueSingleton.removeWhere(
    (item) => item.action === 'order.confirm' && item.entity_id === orderId && item.context_key === scopeKey.value,
  )
  writeQueueSingleton.enqueue({
    action: 'order.confirm',
    entity_type: 'order',
    entity_id: orderId,
    context_key: scopeKey.value,
    user_id: authStore.user.id,
    payload: {
      order_id: orderId,
    },
  })
  refreshQueueState()
  applyQueueOverlays()
}

async function handleCreateAddress(payload: AddressBookEntryInput) {
  await withSaving(async () => {
    if (!syncStore.networkOnline) {
      await enqueueAddressCreate(payload)
      offlineNotice.value = 'Address change queued for sync.'
      return
    }
    try {
      await createAddress(payload)
      await refreshData()
    } catch (error) {
      if (!isRetryableQueueError(error)) {
        throw error
      }
      await enqueueAddressCreate(payload)
      offlineNotice.value = 'Address change queued for sync after network interruption.'
    }
  })
}

async function handleSaveDeliveryZone(payload: DeliveryZoneInput, zoneId?: string) {
  await withSaving(async () => {
    if (zoneId) {
      await updateDeliveryZone(zoneId, payload)
    } else {
      await createDeliveryZone(payload)
    }
    await refreshData()
  })
}

async function handleDeleteDeliveryZone(zoneId: string) {
  await withSaving(async () => {
    await deleteDeliveryZone(zoneId)
    await refreshData()
  })
}

async function handleLoadSlotCapacitiesForDate(date: string) {
  selectedCapacityDate.value = date
  await withSaving(async () => {
    slotCapacities.value = await listSlotCapacities(date || undefined)
  })
}

async function handleUpsertSlotCapacity(payload: SlotCapacityInput) {
  await withSaving(async () => {
    await upsertSlotCapacity(payload)
    slotCapacities.value = await listSlotCapacities(selectedCapacityDate.value || undefined)
  })
}

async function handleDeleteSlotCapacity(slotStart: string) {
  await withSaving(async () => {
    await deleteSlotCapacity(slotStart)
    slotCapacities.value = await listSlotCapacities(selectedCapacityDate.value || undefined)
  })
}

async function handleUpdateAddress(addressId: string, payload: AddressBookEntryInput) {
  await withSaving(async () => {
    if (!syncStore.networkOnline) {
      await enqueueAddressUpdate(addressId, payload)
      offlineNotice.value = 'Address update queued for sync.'
      return
    }
    try {
      await updateAddress(resolveAddressId(addressId), payload)
      await refreshData()
    } catch (error) {
      if (!isRetryableQueueError(error)) {
        throw error
      }
      await enqueueAddressUpdate(addressId, payload)
      offlineNotice.value = 'Address update queued after temporary network failure.'
    }
  })
}

async function handleDeleteAddress(addressId: string) {
  await withSaving(async () => {
    if (!syncStore.networkOnline) {
      await enqueueAddressDelete(addressId)
      offlineNotice.value = 'Address deletion queued for sync.'
      return
    }
    try {
      await deleteAddress(resolveAddressId(addressId))
      await refreshData()
    } catch (error) {
      if (!isRetryableQueueError(error)) {
        throw error
      }
      await enqueueAddressDelete(addressId)
      offlineNotice.value = 'Address deletion queued after temporary network failure.'
    }
  })
}

async function handleSaveDraft(payload: {
  order_type: OrderType
  slot_start: string
  address_book_entry_id?: string
  lines: OrderLineInput[]
}) {
  await withSaving(async () => {
    pickupCode.value = null
    pickupCodeExpiresAt.value = null
    quoteConflictSlots.value = []
    const activeOrderId = currentOrder.value?.id ?? `local-order-${crypto.randomUUID()}`

    if (!syncStore.networkOnline) {
      await enqueueDraftSave(activeOrderId, payload)
      offlineNotice.value = 'Draft write queued for sync.'
      return
    }

    try {
      const order = currentOrder.value
        ? await updateOrderDraft(resolveOrderId(currentOrder.value.id), mapDraftInputForServer(payload))
        : await createOrderDraft(mapDraftInputForServer(payload))
      currentOrderId.value = order.id
      await refreshData()
    } catch (error) {
      if (!isRetryableQueueError(error)) {
        throw error
      }
      await enqueueDraftSave(activeOrderId, payload)
      offlineNotice.value = 'Draft write queued after temporary network failure.'
    }
  })
}

async function handleQuote() {
  if (!currentOrder.value) return
  if (!syncStore.networkOnline) {
    errorMessage.value = 'Quote requires an online connection for server-authoritative capacity checks.'
    return
  }
  await withSaving(async () => {
    quoteConflictSlots.value = []
    try {
      const quoted = await quoteOrder(resolveOrderId(currentOrder.value!.id))
      currentOrderId.value = quoted.order_id
      await refreshData()
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        const slots = error.details.next_slots
        quoteConflictSlots.value = Array.isArray(slots) ? (slots as string[]) : []
      }
      throw error
    }
  })
}

async function handleConfirm() {
  if (!currentOrder.value) return
  await withSaving(async () => {
    quoteConflictSlots.value = []
    if (!syncStore.networkOnline) {
      enqueueOrderConfirm(currentOrder.value!.id)
      offlineNotice.value = 'Finalize action queued. Server will confirm or reject when reconnected.'
      return
    }

    try {
      await confirmOrder(resolveOrderId(currentOrder.value!.id))
      await refreshData()
    } catch (error) {
      if (isRetryableQueueError(error)) {
        enqueueOrderConfirm(currentOrder.value!.id)
        offlineNotice.value = 'Finalize action queued after temporary network failure.'
        return
      }
      if (error instanceof ApiError && error.status === 409) {
        const slots = error.details.next_slots
        quoteConflictSlots.value = Array.isArray(slots) ? (slots as string[]) : []
      }
      throw error
    }
  })
}

async function handleCancel() {
  if (!currentOrder.value) return
  await withSaving(async () => {
    if (!syncStore.networkOnline) {
      throw new Error('Cancel requires online connection; this action is security-sensitive and online-only.')
    }
    await cancelOrder(resolveOrderId(currentOrder.value!.id), 'User cancelled before fulfillment')
    pickupCode.value = null
    pickupCodeExpiresAt.value = null
    quoteConflictSlots.value = []
    await refreshData()
  })
}

async function handleRetryQueuedMutation(queueItemId: string) {
  writeQueueSingleton.markLocalQueued(queueItemId)
  refreshQueueState()
  if (syncStore.networkOnline) {
    await withSaving(async () => {
      await drainQueuedWrites()
      await refreshData()
    })
  }
}

function handleDiscardQueuedMutation(queueItemId: string) {
  writeQueueSingleton.removeById(queueItemId)
  refreshQueueState()
  applyQueueOverlays()
}

function handleFocusConflict(item: QueuedMutation) {
  if (item.entity_type === 'order') {
    currentOrderId.value = resolveOrderId(item.entity_id)
    const slots = item.conflict?.details.next_slots
    quoteConflictSlots.value = Array.isArray(slots) ? (slots as string[]) : []
  }
}

async function handleReconnect() {
  if (!scopeKey.value) {
    return
  }
  await withSaving(async () => {
    await drainQueuedWrites()
    await refreshData()
  })
}

function handleSuggestedSlot() {
  // UI slot gets updated in composer via emitted event.
  errorMessage.value = null
}

onMounted(async () => {
  await loadPage()
  window.addEventListener('online', handleReconnect)
})

onUnmounted(() => {
  window.removeEventListener('online', handleReconnect)
})
</script>

<template>
  <AppShell
    :contexts="contextStore.contexts"
    :active-context="contextStore.activeContext"
    :switching-context="contextStore.switching"
    @switch-context="handleSwitchContext"
  >
    <section class="ordering-page">
      <header class="ordering-page__header">
        <p class="eyebrow">Ordering + scheduling</p>
        <h2>Place pickup or delivery concession orders with real slot capacity checks.</h2>
        <p>Quote and finalize both call authoritative backend checks and ETA calculation.</p>
      </header>

      <p v-if="errorMessage" class="error" role="alert" aria-live="assertive" aria-atomic="true">{{ errorMessage }}</p>
      <p v-if="contextStore.errorMessage" class="error" role="alert" aria-live="assertive" aria-atomic="true">
        {{ contextStore.errorMessage }}
      </p>
      <p v-if="offlineNotice" class="notice" role="status" aria-live="polite" aria-atomic="true">{{ offlineNotice }}</p>
      <p v-if="loading" role="status" aria-live="polite" aria-atomic="true">Loading ordering workspace…</p>

      <template v-else>
        <AddressBookManager
          :addresses="addresses"
          :loading="loading"
          :saving="saving"
          :sync-states="addressSyncStates"
          :sync-errors="addressSyncErrors"
          @create="handleCreateAddress"
          @update="handleUpdateAddress"
          @delete="handleDeleteAddress"
        />

        <OrderComposer
          :menu-items="menuItems"
          :addresses="addresses"
          :current-order="currentOrder"
          :loading="loading"
          :saving="saving"
          :network-online="syncStore.networkOnline"
          :current-order-sync-state="currentOrder?.sync_state ?? null"
          :current-order-sync-error="currentOrder?.sync_error ?? null"
          :queued-confirm-conflict="currentOrderQueuedConfirmConflict"
          :quote-conflict-slots="quoteConflictSlots"
          @save-draft="handleSaveDraft"
          @quote="handleQuote"
          @confirm="handleConfirm"
          @cancel="handleCancel"
          @choose-suggested-slot="handleSuggestedSlot"
        />

        <section class="ordering-page__summary" v-if="currentOrder">
          <h3>Current order summary</h3>
          <p>
            Status: <strong>{{ currentOrder.status }}</strong> · Type: <strong>{{ currentOrder.order_type }}</strong> · Slot:
            <strong>{{ currentOrder.slot_start }}</strong>
          </p>
          <p>
            Subtotal: <strong>${{ (currentOrder.subtotal_cents / 100).toFixed(2) }}</strong>
            · Delivery fee: <strong>${{ (currentOrder.delivery_fee_cents / 100).toFixed(2) }}</strong>
            · Total: <strong>${{ (currentOrder.total_cents / 100).toFixed(2) }}</strong>
          </p>
          <p>Meal-ready ETA: <strong>{{ currentOrder.eta_minutes ?? '—' }}</strong> minutes</p>

          <section v-if="canRequestPickupCode" class="ordering-page__pickup-code">
            <p>
              Pickup verification code is required at handoff.
              <strong>This code rotates and expires quickly.</strong>
            </p>
            <div class="ordering-page__pickup-code-actions">
              <button type="button" class="secondary" :disabled="saving" @click="handleIssuePickupCode">
                Generate / rotate pickup code
              </button>
              <p v-if="pickupCode" class="ordering-page__pickup-code-value">
                Code: <strong>{{ pickupCode }}</strong>
                <span v-if="pickupCodeExpiresAt"> · Expires at {{ pickupCodeExpiresAt }}</span>
              </p>
              <p v-else-if="currentOrder.pickup_code_expires_at">A pickup code is active. Generate to rotate and view it.</p>
            </div>
          </section>

          <ul>
            <li v-for="line in currentOrder.lines" :key="line.id">
              {{ line.item_name }} × {{ line.quantity }} = ${{ (line.line_total_cents / 100).toFixed(2) }}
            </li>
          </ul>
        </section>

        <section class="ordering-page__history">
          <h3>My orders in active context</h3>
          <ul>
            <li v-for="order in orders" :key="order.id">
              <button type="button" class="order-link" :disabled="saving" @click="currentOrderId = order.id">
                {{ order.id.slice(0, 8) }} · {{ order.status }} · ${{ (order.total_cents / 100).toFixed(2) }}
              </button>
              <span v-if="order.sync_state" class="sync-pill" :class="`sync-pill--${order.sync_state}`">{{ order.sync_state }}</span>
            </li>
            <li v-if="orders.length === 0">No orders yet in this context.</li>
          </ul>
        </section>

        <section v-if="queueItems.length > 0" class="ordering-page__sync">
          <h3>Offline sync queue</h3>
          <p>
            Writes listed below are not considered successful until server-committed. Conflicts include server reasons and next-step
            guidance.
          </p>
          <ul>
            <li v-for="item in queueItems" :key="item.id">
              <div>
                <strong>{{ item.action }}</strong> · {{ item.entity_type }} {{ item.entity_id.slice(0, 10) }} ·
                <span class="sync-pill" :class="`sync-pill--${item.status}`">{{ item.status }}</span>
              </div>
              <p v-if="item.last_error" class="sync-error" role="alert" aria-live="assertive" aria-atomic="true">
                {{ item.last_error }}
              </p>
              <p v-if="item.conflict" role="alert" aria-live="assertive" aria-atomic="true">
                Server reason: {{ item.conflict.message }}
              </p>
              <div class="ordering-page__sync-actions">
                <button
                  v-if="item.status === 'conflict' || item.status === 'failed_retrying'"
                  type="button"
                  class="secondary"
                  :disabled="saving"
                  @click="handleRetryQueuedMutation(item.id)"
                >
                  Retry
                </button>
                <button v-if="item.status === 'conflict'" type="button" class="secondary" :disabled="saving" @click="handleFocusConflict(item)">
                  Review in composer
                </button>
                <button type="button" class="danger" :disabled="saving" @click="handleDiscardQueuedMutation(item.id)">
                  Remove from queue
                </button>
              </div>
            </li>
          </ul>
        </section>

        <section v-if="canManageScheduling" class="ordering-page__scheduling">
          <h3>Staff scheduling controls</h3>
          <p>Manage ZIP delivery fees and 15-minute slot capacity for the active event/store context.</p>

          <div class="ordering-page__scheduling-grid">
            <DeliveryZoneManager
              :zones="deliveryZones"
              :loading="loading"
              :saving="saving"
              @save-zone="handleSaveDeliveryZone"
              @delete-zone="handleDeleteDeliveryZone"
            />

            <SlotCapacityManager
              :capacities="slotCapacities"
              :loading="loading"
              :saving="saving"
              @load-for-date="handleLoadSlotCapacitiesForDate"
              @upsert="handleUpsertSlotCapacity"
              @remove="handleDeleteSlotCapacity"
            />
          </div>
        </section>
      </template>
    </section>
  </AppShell>
</template>

<style scoped>
.ordering-page {
  display: grid;
  gap: 1rem;
}

.ordering-page__header,
.ordering-page__summary,
.ordering-page__history,
.ordering-page__scheduling,
.ordering-page__sync {
  border: 1px solid rgba(21, 39, 61, 0.14);
  border-radius: 1rem;
  padding: 1rem;
  background: rgba(251, 250, 246, 0.92);
}

.eyebrow {
  margin: 0;
  font-size: 0.73rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #2a4f75;
}

h2,
h3 {
  margin: 0.35rem 0;
  font-family: 'Fraunces', serif;
}

.ordering-page__header p,
.ordering-page__summary p {
  margin: 0.2rem 0 0;
  color: #314c6a;
}

.ordering-page__summary ul,
.ordering-page__history ul {
  margin: 0.5rem 0 0;
  padding-left: 1rem;
}

.ordering-page__scheduling-grid {
  margin-top: 0.75rem;
  display: grid;
  gap: 0.9rem;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
}

.order-link {
  border: none;
  background: transparent;
  color: #1f446b;
  text-decoration: underline;
  cursor: pointer;
  padding: 0;
}

.ordering-page__pickup-code {
  margin-top: 0.7rem;
  border: 1px dashed rgba(31, 68, 107, 0.26);
  border-radius: 0.7rem;
  padding: 0.65rem;
}

.ordering-page__pickup-code-actions {
  display: grid;
  gap: 0.35rem;
}

.ordering-page__pickup-code-value {
  margin: 0;
  color: #1f446b;
}

.error {
  margin: 0;
  color: #8a1e35;
}

.notice {
  margin: 0;
  color: #34506e;
}

.sync-pill {
  margin-left: 0.45rem;
  border-radius: 999px;
  font-size: 0.72rem;
  padding: 0.18rem 0.48rem;
  border: 1px solid transparent;
}

.sync-pill--local_queued,
.sync-pill--syncing {
  background: rgba(250, 204, 21, 0.2);
  color: #734d00;
  border-color: rgba(250, 204, 21, 0.35);
}

.sync-pill--server_committed {
  background: rgba(34, 197, 94, 0.15);
  color: #0b5e47;
  border-color: rgba(34, 197, 94, 0.4);
}

.sync-pill--failed_retrying,
.sync-pill--conflict {
  background: rgba(244, 63, 94, 0.2);
  color: #6a0f1b;
  border-color: rgba(244, 63, 94, 0.4);
}

.ordering-page__sync ul {
  margin: 0.5rem 0 0;
  padding-left: 1rem;
  display: grid;
  gap: 0.6rem;
}

.ordering-page__sync p {
  margin: 0.2rem 0 0;
  color: #314c6a;
}

.sync-error {
  color: #8a1e35 !important;
}

.ordering-page__sync-actions {
  margin-top: 0.35rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.ordering-page__sync-actions button {
  border: none;
  border-radius: 0.5rem;
  background: #1d4673;
  color: #fff;
  padding: 0.38rem 0.62rem;
  cursor: pointer;
}

.ordering-page__sync-actions .secondary {
  background: rgba(22, 34, 55, 0.1);
  color: #1f3450;
}

.ordering-page__sync-actions .danger {
  background: #7c2342;
}
</style>
