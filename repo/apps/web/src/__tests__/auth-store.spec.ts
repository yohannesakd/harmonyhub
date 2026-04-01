import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { cacheAuthMe, cacheScopedRead, loadCachedAuthMe, loadScopedRead } from '@/offline/readCache'
import { WriteQueue } from '@/offline/writeQueue'
import { ApiError } from '@/services/api'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/api')>()
  return {
    ...actual,
    login: vi.fn(),
    logout: vi.fn(),
    me: vi.fn(),
  }
})

vi.mock('@/pwa/registerServiceWorker', () => ({
  notifyAuthBoundaryChange: vi.fn().mockResolvedValue(undefined),
}))

import { login, logout, me } from '@/services/api'
import { notifyAuthBoundaryChange } from '@/pwa/registerServiceWorker'

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    localStorage.clear()
    document.cookie = 'hh_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
    document.cookie = 'hh_csrf=test-auth-cache-token; path=/'
  })

  it('hydrates authenticated session on bootstrap', async () => {
    vi.mocked(me).mockResolvedValue({
      user: { id: 'u1', username: 'admin', is_active: true, mfa_totp_enabled: false },
      permissions: ['dashboard.view'],
      active_context: {
        organization_id: 'o1',
        program_id: 'p1',
        event_id: 'e1',
        store_id: 's1',
        role: 'administrator',
      },
      available_contexts: [],
    })

    const store = useAuthStore()
    await store.bootstrap()

    expect(store.isAuthenticated).toBe(true)
    expect(store.permissions).toContain('dashboard.view')
    expect(store.activeContext?.role).toBe('administrator')
  })

  it('marks MFA-required login challenge', async () => {
    vi.mocked(login).mockRejectedValue(new ApiError('MFA code is required', 'MFA_REQUIRED', 401))

    const store = useAuthStore()
    await expect(store.signIn('staff', 'staff123!')).rejects.toThrow('MFA code is required')

    expect(store.isMfaRequired).toBe(true)
    expect(store.errorMessage).toContain('Multi-factor code required')
  })

  it('hydrates from cached /auth/me payload while offline', async () => {
    await cacheAuthMe({
      user: { id: 'u1', username: 'staff', is_active: true, mfa_totp_enabled: false },
      permissions: ['order.manage_own'],
      active_context: {
        organization_id: 'o1',
        program_id: 'p1',
        event_id: 'e1',
        store_id: 's1',
        role: 'staff',
      },
      available_contexts: [],
    })

    vi.mocked(me).mockRejectedValue(new Error('offline'))
    vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)

    const store = useAuthStore()
    await store.bootstrap()

    expect(store.isAuthenticated).toBe(true)
    expect(store.user?.username).toBe('staff')
    expect(store.errorMessage).toContain('Using cached session while offline')
  })

  it('switching authenticated users clears previous auth cache and notifies service worker boundary', async () => {
    const store = useAuthStore()
    const queue = new WriteQueue(localStorage)
    store.user = { id: 'u-1', username: 'staff', is_active: true, mfa_totp_enabled: false }
    await cacheAuthMe({
      user: { id: 'u-1', username: 'staff', is_active: true, mfa_totp_enabled: false },
      permissions: ['order.manage_own'],
      active_context: {
        organization_id: 'o1',
        program_id: 'p1',
        event_id: 'e1',
        store_id: 's1',
        role: 'staff',
      },
      available_contexts: [],
    })
    cacheScopedRead('u-1:o1:p1:e1:s1', 'ordering_snapshot', {
      menu_items: [],
      delivery_zones: [],
      slot_capacities: [],
    })
    queue.enqueue({
      action: 'address.update',
      entity_type: 'address',
      entity_id: 'addr-1',
      context_key: 'u-1:o1:p1:e1:s1',
      user_id: 'u-1',
      payload: {
        address_id: 'addr-1',
        input: {
          label: 'Home',
          recipient_name: 'Taylor',
          line1: '123 Main',
          city: 'NYC',
          state: 'NY',
          postal_code: '10001',
          is_default: true,
        },
      },
    })

    vi.mocked(login).mockResolvedValue({
      user: { id: 'u-2', username: 'referee', is_active: true, mfa_totp_enabled: false },
      permissions: ['order.manage_own'],
      active_context: {
        organization_id: 'o1',
        program_id: 'p1',
        event_id: 'e1',
        store_id: 's1',
        role: 'referee',
      },
      available_contexts: [],
    })

    await store.signIn('referee', 'ref123!')

    expect(await loadCachedAuthMe('u-1')).toBeNull()
    expect((await loadCachedAuthMe('u-2'))?.user.username).toBe('referee')
    expect(loadScopedRead('u-1:o1:p1:e1:s1', 'ordering_snapshot')).toBeNull()
    expect(queue.listAll().some((item) => item.user_id === 'u-1')).toBe(false)
    expect(notifyAuthBoundaryChange).toHaveBeenCalledTimes(1)
  })

  it('signOut clears cached auth payload and notifies service worker boundary', async () => {
    vi.mocked(logout).mockResolvedValue(undefined)

    const store = useAuthStore()
    const queue = new WriteQueue(localStorage)
    store.user = { id: 'u-signout', username: 'student', is_active: true, mfa_totp_enabled: false }
    await cacheAuthMe({
      user: { id: 'u-signout', username: 'student', is_active: true, mfa_totp_enabled: false },
      permissions: ['order.manage_own'],
      active_context: {
        organization_id: 'o1',
        program_id: 'p1',
        event_id: 'e1',
        store_id: 's1',
        role: 'student',
      },
      available_contexts: [],
    })
    cacheScopedRead('u-signout:o1:p1:e1:s1', 'ordering_snapshot', {
      menu_items: [],
      delivery_zones: [],
      slot_capacities: [],
    })
    queue.enqueue({
      action: 'order.draft.save',
      entity_type: 'order',
      entity_id: 'order-1',
      context_key: 'u-signout:o1:p1:e1:s1',
      user_id: 'u-signout',
      payload: {
        order_id: 'order-1',
        input: {
          order_type: 'pickup',
          slot_start: '2026-04-02T12:30:00Z',
          lines: [{ menu_item_id: 'menu-1', quantity: 1 }],
        },
      },
    })

    await store.signOut()

    expect(await loadCachedAuthMe('u-signout')).toBeNull()
    expect(loadScopedRead('u-signout:o1:p1:e1:s1', 'ordering_snapshot')).toBeNull()
    expect(queue.listAll().some((item) => item.user_id === 'u-signout')).toBe(false)
    expect(store.isAuthenticated).toBe(false)
    expect(notifyAuthBoundaryChange).toHaveBeenCalledTimes(1)
  })

  it('signOut clears local offline artifacts even when API logout fails', async () => {
    vi.mocked(logout).mockRejectedValue(new Error('logout failed'))

    const store = useAuthStore()
    const queue = new WriteQueue(localStorage)
    store.user = { id: 'u-fail', username: 'student', is_active: true, mfa_totp_enabled: false }
    await cacheAuthMe({
      user: { id: 'u-fail', username: 'student', is_active: true, mfa_totp_enabled: false },
      permissions: ['order.manage_own'],
      active_context: {
        organization_id: 'o1',
        program_id: 'p1',
        event_id: 'e1',
        store_id: 's1',
        role: 'student',
      },
      available_contexts: [],
    })
    cacheScopedRead('u-fail:o1:p1:e1:s1', 'ordering_snapshot', {
      menu_items: [],
      delivery_zones: [],
      slot_capacities: [],
    })
    queue.enqueue({
      action: 'order.draft.save',
      entity_type: 'order',
      entity_id: 'order-1',
      context_key: 'u-fail:o1:p1:e1:s1',
      user_id: 'u-fail',
      payload: {
        order_id: 'order-1',
        input: {
          order_type: 'pickup',
          slot_start: '2026-04-02T12:30:00Z',
          lines: [{ menu_item_id: 'menu-1', quantity: 1 }],
        },
      },
    })

    await expect(store.signOut()).rejects.toThrow('logout failed')

    expect(await loadCachedAuthMe('u-fail')).toBeNull()
    expect(loadScopedRead('u-fail:o1:p1:e1:s1', 'ordering_snapshot')).toBeNull()
    expect(queue.listAll().some((item) => item.user_id === 'u-fail')).toBe(false)
    expect(store.isAuthenticated).toBe(false)
    expect(notifyAuthBoundaryChange).toHaveBeenCalledTimes(1)
  })
})
