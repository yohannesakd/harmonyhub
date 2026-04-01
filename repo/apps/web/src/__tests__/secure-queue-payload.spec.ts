import { beforeEach, describe, expect, it } from 'vitest'

import { protectQueuedPayload, unprotectQueuedPayload } from '@/offline/secureQueuePayload'
import type { StorageLike } from '@/offline/storage'
import { WriteQueue } from '@/offline/writeQueue'

function createInspectableMemoryStorage(): { storage: StorageLike; map: Map<string, string> } {
  const map = new Map<string, string>()
  return {
    map,
    storage: {
      getItem: (key: string) => map.get(key) ?? null,
      setItem: (key: string, value: string) => {
        map.set(key, value)
      },
      removeItem: (key: string) => {
        map.delete(key)
      },
    },
  }
}

describe('secure queued payload protection', () => {
  beforeEach(() => {
    document.cookie = 'hh_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
  })

  it('encrypts sensitive queued payloads and decrypts them for replay', async () => {
    document.cookie = 'hh_csrf=test-csrf-token; path=/'

    const payload = {
      local_address_id: 'local-address-1',
      input: {
        label: 'Home',
        recipient_name: 'Taylor',
        line1: '123 Main',
        city: 'New York',
        state: 'NY',
        postal_code: '10001',
        is_default: true,
      },
    }

    const protectedPayload = await protectQueuedPayload('address.create', 'user-1', payload)

    expect(protectedPayload).toMatchObject({ encrypted: true, algorithm: 'AES-GCM', version: 1 })
    expect(JSON.stringify(protectedPayload)).not.toContain('123 Main')
    expect(JSON.stringify(protectedPayload)).not.toContain('Taylor')

    const unprotected = await unprotectQueuedPayload<typeof payload>('address.create', 'user-1', protectedPayload)
    expect(unprotected).toEqual(payload)
  })

  it('does not transform non-sensitive queue payloads', async () => {
    document.cookie = 'hh_csrf=test-csrf-token; path=/'

    const payload = { order_id: 'order-1' }
    const protectedPayload = await protectQueuedPayload('order.confirm', 'user-1', payload)

    expect(protectedPayload).toEqual(payload)
  })

  it('rejects decrypt when user key does not match', async () => {
    document.cookie = 'hh_csrf=test-csrf-token; path=/'

    const payload = {
      order_id: 'local-order-1',
      input: {
        order_type: 'pickup',
        slot_start: '2026-04-01T12:30:00Z',
        lines: [{ menu_item_id: 'menu-1', quantity: 1 }],
      },
    }

    const protectedPayload = await protectQueuedPayload('order.draft.save', 'user-1', payload)

    await expect(unprotectQueuedPayload('order.draft.save', 'user-2', protectedPayload)).rejects.toThrow()
  })

  it('persists encrypted envelope without plaintext sensitive fields', async () => {
    document.cookie = 'hh_csrf=test-csrf-token; path=/'

    const { storage, map } = createInspectableMemoryStorage()
    const queue = new WriteQueue(storage, 'secure-test-queue')
    const sensitivePayload = {
      local_address_id: 'local-address-1',
      input: {
        label: 'Home',
        recipient_name: 'Taylor',
        line1: '123 Main',
        city: 'New York',
        state: 'NY',
        postal_code: '10001',
        is_default: true,
      },
    }

    const protectedPayload = await protectQueuedPayload('address.create', 'user-1', sensitivePayload)
    queue.enqueue({
      action: 'address.create',
      entity_type: 'address',
      entity_id: 'local-address-1',
      context_key: 'user-1:ctx-1',
      user_id: 'user-1',
      payload: protectedPayload,
    })

    const persisted = map.get('secure-test-queue')
    expect(persisted).toBeTruthy()
    expect(persisted).toContain('"encrypted":true')
    expect(persisted).not.toContain('123 Main')
    expect(persisted).not.toContain('Taylor')
  })
})
