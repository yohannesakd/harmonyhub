import { beforeEach, describe, expect, it } from 'vitest'

import {
  cacheScopedRead,
  clearOrderingArtifactsForUser,
  clearScopedReadCacheForUser,
  loadScopedRead,
} from '@/offline/readCache'

describe('read cache isolation', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('clears only targeted user scoped keys', () => {
    cacheScopedRead('user-1:ctx-1', 'ordering_snapshot', {
      menu_items: [{ id: 'm1' }],
      delivery_zones: [],
      slot_capacities: [],
    })
    cacheScopedRead('user-1:ctx-1', 'ordering_id_map', {
      address_ids: { a: 'server-a' },
      order_ids: { o: 'server-o' },
    })
    cacheScopedRead('user-2:ctx-1', 'ordering_snapshot', {
      menu_items: [{ id: 'm2' }],
      delivery_zones: [],
      slot_capacities: [],
    })

    clearScopedReadCacheForUser('user-1')

    expect(loadScopedRead('user-1:ctx-1', 'ordering_snapshot')).toBeNull()
    expect(loadScopedRead('user-1:ctx-1', 'ordering_id_map')).toBeNull()
    expect(loadScopedRead('user-2:ctx-1', 'ordering_snapshot')).not.toBeNull()
  })

  it('clears ordering artifacts while retaining other scoped reads', () => {
    cacheScopedRead('user-1:ctx-1', 'ordering_snapshot', {
      menu_items: [{ id: 'm1' }],
      delivery_zones: [],
      slot_capacities: [],
    })
    cacheScopedRead('user-1:ctx-1', 'ordering_id_map', {
      address_ids: { a: 'server-a' },
      order_ids: { o: 'server-o' },
    })
    cacheScopedRead('user-1:ctx-1', 'directory_search', { results: [] })

    clearOrderingArtifactsForUser('user-1')

    expect(loadScopedRead('user-1:ctx-1', 'ordering_snapshot')).toBeNull()
    expect(loadScopedRead('user-1:ctx-1', 'ordering_id_map')).toBeNull()
    expect(loadScopedRead('user-1:ctx-1', 'directory_search')).toEqual({ results: [] })
  })
})
