import type { DeliveryZone, MenuItem, MePayload, SlotCapacity } from '@/types'

import {
  isEncryptedAuthBootstrapPayload,
  protectAuthBootstrapPayload,
  unprotectAuthBootstrapPayload,
} from '@/offline/secureAuthCache'
import { getBrowserStorage, listStorageKeys, readJson, writeJson } from '@/offline/storage'

const READ_CACHE_PREFIX = 'hh_read_cache_v1'
const AUTH_ME_CACHE_PREFIX = `${READ_CACHE_PREFIX}:auth:me`
const AUTH_ME_LAST_USER_KEY = `${READ_CACHE_PREFIX}:auth:last_user_id`

type CachedEnvelope<T> = {
  stored_at: string
  data: T
}

type CachedAuthEnvelope = {
  stored_at: string
  payload: unknown
}

export type OrderingReadSnapshot = {
  menu_items: MenuItem[]
  delivery_zones: DeliveryZone[]
  slot_capacities: SlotCapacity[]
}

export type OrderingIdMap = {
  address_ids: Record<string, string>
  order_ids: Record<string, string>
}

const defaultIdMap: OrderingIdMap = {
  address_ids: {},
  order_ids: {},
}

function scopedKey(scope: string, resource: string): string {
  return `${READ_CACHE_PREFIX}:${scope}:${resource}`
}

export function cacheScopedRead<T>(scope: string, resource: string, data: T): void {
  const storage = getBrowserStorage()
  const key = scopedKey(scope, resource)
  writeJson(storage, key, {
    stored_at: new Date().toISOString(),
    data,
  } satisfies CachedEnvelope<T>)
}

export function loadScopedRead<T>(scope: string, resource: string): T | null {
  const storage = getBrowserStorage()
  const key = scopedKey(scope, resource)
  const envelope = readJson<CachedEnvelope<T>>(storage, key)
  return envelope?.data ?? null
}

export async function cacheAuthMe(payload: MePayload): Promise<void> {
  const storage = getBrowserStorage()
  const key = `${AUTH_ME_CACHE_PREFIX}:${payload.user.id}`

  try {
    const protectedPayload = await protectAuthBootstrapPayload(payload.user.id, payload)
    writeJson(storage, key, {
      stored_at: new Date().toISOString(),
      payload: protectedPayload,
    } satisfies CachedAuthEnvelope)
    storage.setItem(AUTH_ME_LAST_USER_KEY, payload.user.id)
  } catch {
    storage.removeItem(key)
    const lastUserId = storage.getItem(AUTH_ME_LAST_USER_KEY)
    if (lastUserId && lastUserId === payload.user.id) {
      storage.removeItem(AUTH_ME_LAST_USER_KEY)
    }
  }
}

export async function loadCachedAuthMe(userId?: string): Promise<MePayload | null> {
  const storage = getBrowserStorage()
  const scopedUserId = userId ?? storage.getItem(AUTH_ME_LAST_USER_KEY)
  if (!scopedUserId) {
    return null
  }

  const key = `${AUTH_ME_CACHE_PREFIX}:${scopedUserId}`
  const envelope = readJson<CachedAuthEnvelope>(storage, key)
  if (!envelope?.payload || !isEncryptedAuthBootstrapPayload(envelope.payload)) {
    storage.removeItem(key)
    const lastUserId = storage.getItem(AUTH_ME_LAST_USER_KEY)
    if (lastUserId && lastUserId === scopedUserId) {
      storage.removeItem(AUTH_ME_LAST_USER_KEY)
    }
    return null
  }

  try {
    return await unprotectAuthBootstrapPayload(scopedUserId, envelope.payload)
  } catch {
    storage.removeItem(key)
    const lastUserId = storage.getItem(AUTH_ME_LAST_USER_KEY)
    if (lastUserId && lastUserId === scopedUserId) {
      storage.removeItem(AUTH_ME_LAST_USER_KEY)
    }
    return null
  }
}

export function clearCachedAuthMe(userId?: string): void {
  const storage = getBrowserStorage()
  const scopedUserId = userId ?? storage.getItem(AUTH_ME_LAST_USER_KEY)
  if (scopedUserId) {
    storage.removeItem(`${AUTH_ME_CACHE_PREFIX}:${scopedUserId}`)
  }
  const lastUserId = storage.getItem(AUTH_ME_LAST_USER_KEY)
  if (!userId || (lastUserId && lastUserId === scopedUserId)) {
    storage.removeItem(AUTH_ME_LAST_USER_KEY)
  }
}

export function cacheOrderingSnapshot(scope: string, snapshot: OrderingReadSnapshot): void {
  cacheScopedRead(scope, 'ordering_snapshot', snapshot)
}

export function loadOrderingSnapshot(scope: string): OrderingReadSnapshot | null {
  return loadScopedRead<OrderingReadSnapshot>(scope, 'ordering_snapshot')
}

export function loadOrderingIdMap(scope: string): OrderingIdMap {
  const map = loadScopedRead<OrderingIdMap>(scope, 'ordering_id_map')
  if (!map) {
    return structuredClone(defaultIdMap)
  }
  return {
    address_ids: { ...(map.address_ids || {}) },
    order_ids: { ...(map.order_ids || {}) },
  }
}

export function saveOrderingIdMap(scope: string, map: OrderingIdMap): void {
  cacheScopedRead(scope, 'ordering_id_map', map)
}

export function clearScopedReadCacheForUser(userId: string): void {
  const storage = getBrowserStorage()
  const prefix = `${READ_CACHE_PREFIX}:${userId}:`

  for (const key of listStorageKeys(storage)) {
    if (key.startsWith(prefix)) {
      storage.removeItem(key)
    }
  }
}

export function clearOrderingArtifactsForUser(userId: string): void {
  const storage = getBrowserStorage()
  const prefix = `${READ_CACHE_PREFIX}:${userId}:`

  for (const key of listStorageKeys(storage)) {
    if (!key.startsWith(prefix)) {
      continue
    }
    if (key.endsWith(':ordering_snapshot') || key.endsWith(':ordering_id_map')) {
      storage.removeItem(key)
    }
  }
}
