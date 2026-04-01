import { describe, expect, it } from 'vitest'

import { WriteQueue } from '@/offline/writeQueue'
import type { StorageLike } from '@/offline/storage'

function createMemoryStorage(): StorageLike {
  const map = new Map<string, string>()
  return {
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => {
      map.set(key, value)
    },
    removeItem: (key: string) => {
      map.delete(key)
    },
  }
}

describe('WriteQueue', () => {
  it('persists queued mutations across re-instantiation', () => {
    const storage = createMemoryStorage()
    const queueA = new WriteQueue(storage, 'test-queue')

    queueA.enqueue({
      action: 'address.create',
      entity_type: 'address',
      entity_id: 'local-address-1',
      context_key: 'user-1:ctx-1',
      user_id: 'user-1',
      payload: {
        local_address_id: 'local-address-1',
        input: {
          label: 'Home',
          recipient_name: 'Taylor',
          line1: '123 Main',
          line2: null,
          city: 'New York',
          state: 'NY',
          postal_code: '10001',
          phone: null,
          is_default: true,
        },
      },
    })

    const queueB = new WriteQueue(storage, 'test-queue')
    const items = queueB.listForScope('user-1:ctx-1', 'user-1')
    expect(items).toHaveLength(1)
    expect(items[0].status).toBe('local_queued')
  })

  it('retries failed mutations and commits on later success', async () => {
    const storage = createMemoryStorage()
    const queue = new WriteQueue(storage, 'test-queue')

    queue.enqueue({
      action: 'address.delete',
      entity_type: 'address',
      entity_id: 'addr-1',
      context_key: 'user-1:ctx-1',
      user_id: 'user-1',
      payload: { address_id: 'addr-1' },
    })

    await queue.processScope('user-1:ctx-1', 'user-1', async () => {
      throw new Error('Network unreachable')
    })

    let items = queue.listForScope('user-1:ctx-1', 'user-1')
    expect(items).toHaveLength(1)
    expect(items[0].status).toBe('failed_retrying')

    await queue.processScope('user-1:ctx-1', 'user-1', async () => ({ outcome: 'committed' }))
    items = queue.listForScope('user-1:ctx-1', 'user-1')
    expect(items).toHaveLength(0)
  })

  it('stores conflict payload when server rejects contested queued action', async () => {
    const storage = createMemoryStorage()
    const queue = new WriteQueue(storage, 'test-queue')

    queue.enqueue({
      action: 'order.confirm',
      entity_type: 'order',
      entity_id: 'order-1',
      context_key: 'user-1:ctx-1',
      user_id: 'user-1',
      payload: { order_id: 'order-1' },
    })

    await queue.processScope('user-1:ctx-1', 'user-1', async () => ({
      outcome: 'conflict',
      conflict: {
        code: 'VALIDATION_ERROR',
        message: 'Requested slot is at capacity',
        details: {
          next_slots: ['2026-04-02T12:45:00Z'],
        },
      },
    }))

    const items = queue.listForScope('user-1:ctx-1', 'user-1')
    expect(items).toHaveLength(1)
    expect(items[0].status).toBe('conflict')
    expect(items[0].conflict?.details.next_slots).toEqual(['2026-04-02T12:45:00Z'])
  })

  it('does not report committed state before server commit', async () => {
    const storage = createMemoryStorage()
    const queue = new WriteQueue(storage, 'test-queue')

    queue.enqueue({
      action: 'order.draft.save',
      entity_type: 'order',
      entity_id: 'local-order-1',
      context_key: 'user-1:ctx-1',
      user_id: 'user-1',
      payload: {
        order_id: 'local-order-1',
        input: {
          order_type: 'pickup',
          slot_start: new Date('2026-04-02T12:30:00Z').toISOString(),
          lines: [{ menu_item_id: 'menu-1', quantity: 1 }],
        },
      },
    })

    await queue.processScope('user-1:ctx-1', 'user-1', async () => ({
      outcome: 'retry',
      message: 'Still offline',
    }))

    const items = queue.listForScope('user-1:ctx-1', 'user-1')
    expect(items).toHaveLength(1)
    expect(items[0].status).not.toBe('server_committed')
  })

  it('removes all queued mutations for a specific user across contexts', () => {
    const storage = createMemoryStorage()
    const queue = new WriteQueue(storage, 'test-queue')

    queue.enqueue({
      action: 'order.confirm',
      entity_type: 'order',
      entity_id: 'order-1',
      context_key: 'user-1:ctx-1',
      user_id: 'user-1',
      payload: { order_id: 'order-1' },
    })
    queue.enqueue({
      action: 'address.delete',
      entity_type: 'address',
      entity_id: 'addr-2',
      context_key: 'user-1:ctx-2',
      user_id: 'user-1',
      payload: { address_id: 'addr-2' },
    })
    queue.enqueue({
      action: 'order.confirm',
      entity_type: 'order',
      entity_id: 'order-3',
      context_key: 'user-2:ctx-1',
      user_id: 'user-2',
      payload: { order_id: 'order-3' },
    })

    queue.removeForUser('user-1')

    const remaining = queue.listAll()
    expect(remaining).toHaveLength(1)
    expect(remaining[0].user_id).toBe('user-2')
  })
})
