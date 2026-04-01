import { beforeEach, describe, expect, it } from 'vitest'

import { cacheAuthMe, clearCachedAuthMe, loadCachedAuthMe } from '@/offline/readCache'

const AUTH_CACHE_KEY_PREFIX = 'hh_read_cache_v1:auth:me'

describe('auth bootstrap cache hardening', () => {
  beforeEach(() => {
    localStorage.clear()
    document.cookie = 'hh_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
    document.cookie = 'hh_csrf=test-auth-bootstrap-key; path=/'
  })

  it('stores cached auth bootstrap payload encrypted at rest', async () => {
    await cacheAuthMe({
      user: { id: 'user-1', username: 'staff', is_active: true, mfa_totp_enabled: false },
      permissions: ['dashboard.view', 'order.manage_own'],
      active_context: {
        organization_id: 'org-1',
        program_id: 'prog-1',
        event_id: 'event-1',
        store_id: 'store-1',
        role: 'staff',
      },
      available_contexts: [],
    })

    const raw = localStorage.getItem(`${AUTH_CACHE_KEY_PREFIX}:user-1`)
    expect(raw).toBeTruthy()
    expect(raw).toContain('"encrypted":true')
    expect(raw).not.toContain('"username":"staff"')
    expect(raw).not.toContain('dashboard.view')

    const cached = await loadCachedAuthMe('user-1')
    expect(cached?.user.username).toBe('staff')
    expect(cached?.permissions).toContain('dashboard.view')
  })

  it('invalidates cached auth payload when decryption key material changes', async () => {
    await cacheAuthMe({
      user: { id: 'user-2', username: 'student', is_active: true, mfa_totp_enabled: false },
      permissions: ['order.manage_own'],
      active_context: {
        organization_id: 'org-1',
        program_id: 'prog-1',
        event_id: 'event-1',
        store_id: 'store-1',
        role: 'student',
      },
      available_contexts: [],
    })

    document.cookie = 'hh_csrf=different-auth-bootstrap-key; path=/'

    const cached = await loadCachedAuthMe('user-2')
    expect(cached).toBeNull()
    expect(localStorage.getItem(`${AUTH_CACHE_KEY_PREFIX}:user-2`)).toBeNull()
  })

  it('rejects and clears legacy plaintext cached auth payloads', async () => {
    localStorage.setItem(
      `${AUTH_CACHE_KEY_PREFIX}:legacy-user`,
      JSON.stringify({
        stored_at: new Date().toISOString(),
        data: {
          user: { id: 'legacy-user', username: 'legacy', is_active: true, mfa_totp_enabled: false },
          permissions: ['dashboard.view'],
          active_context: null,
          available_contexts: [],
        },
      }),
    )

    const cached = await loadCachedAuthMe('legacy-user')
    expect(cached).toBeNull()
    expect(localStorage.getItem(`${AUTH_CACHE_KEY_PREFIX}:legacy-user`)).toBeNull()
  })

  it('clears last-user pointer when cached auth item is explicitly cleared', async () => {
    await cacheAuthMe({
      user: { id: 'clear-user', username: 'staff', is_active: true, mfa_totp_enabled: false },
      permissions: ['dashboard.view'],
      active_context: {
        organization_id: 'org-1',
        program_id: 'prog-1',
        event_id: 'event-1',
        store_id: 'store-1',
        role: 'staff',
      },
      available_contexts: [],
    })

    clearCachedAuthMe('clear-user')

    expect(await loadCachedAuthMe('clear-user')).toBeNull()
    expect(localStorage.getItem('hh_read_cache_v1:auth:last_user_id')).toBeNull()
  })
})
