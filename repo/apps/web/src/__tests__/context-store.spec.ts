import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore } from '@/stores/auth'
import { useContextStore } from '@/stores/context'

vi.mock('@/services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/api')>()
  return {
    ...actual,
    fetchAvailableContexts: vi.fn(),
    setActiveContext: vi.fn(),
    me: vi.fn(),
  }
})

import { fetchAvailableContexts, me, setActiveContext } from '@/services/api'

describe('context store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('switches context and hydrates auth state', async () => {
    const authStore = useAuthStore()
    authStore.hydrateFromMe({
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

    vi.mocked(fetchAvailableContexts).mockResolvedValue([
      {
        organization_id: 'o1',
        organization_name: 'Org 1',
        program_id: 'p1',
        program_name: 'Program 1',
        event_id: 'e1',
        event_name: 'Event 1',
        store_id: 's1',
        store_name: 'Store 1',
        role: 'administrator',
      },
    ])
    vi.mocked(setActiveContext).mockResolvedValue({
      organization_id: 'o1',
      program_id: 'p2',
      event_id: 'e2',
      store_id: 's2',
      role: 'administrator',
    })
    vi.mocked(me).mockResolvedValue({
      user: { id: 'u1', username: 'admin', is_active: true, mfa_totp_enabled: false },
      permissions: ['dashboard.view'],
      active_context: {
        organization_id: 'o1',
        program_id: 'p2',
        event_id: 'e2',
        store_id: 's2',
        role: 'administrator',
      },
      available_contexts: [
        {
          organization_id: 'o1',
          organization_name: 'Org 1',
          program_id: 'p2',
          program_name: 'Program 2',
          event_id: 'e2',
          event_name: 'Event 2',
          store_id: 's2',
          store_name: 'Store 2',
          role: 'administrator',
        },
      ],
    })

    const contextStore = useContextStore()
    await contextStore.loadContexts()
    await contextStore.switchContext({
      organization_id: 'o1',
      program_id: 'p2',
      event_id: 'e2',
      store_id: 's2',
      role: 'administrator',
    })

    expect(contextStore.activeContext?.event_id).toBe('e2')
    expect(authStore.activeContext?.event_id).toBe('e2')
  })

  it('shows intentional offline context message instead of raw fetch error', async () => {
    const authStore = useAuthStore()
    authStore.hydrateFromMe({
      user: { id: 'u1', username: 'student', is_active: true, mfa_totp_enabled: false },
      permissions: ['dashboard.view'],
      active_context: {
        organization_id: 'o1',
        program_id: 'p1',
        event_id: 'e1',
        store_id: 's1',
        role: 'student',
      },
      available_contexts: [
        {
          organization_id: 'o1',
          organization_name: 'Org 1',
          program_id: 'p1',
          program_name: 'Program 1',
          event_id: 'e1',
          event_name: 'Event 1',
          store_id: 's1',
          store_name: 'Store 1',
          role: 'student',
        },
      ],
    })

    vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    vi.mocked(fetchAvailableContexts).mockRejectedValue(new Error('Failed to fetch'))

    const contextStore = useContextStore()
    contextStore.syncFromAuthStore()
    await contextStore.loadContexts()

    expect(contextStore.errorMessage).toContain('Offline: using your last available workspace context list.')
    expect(contextStore.errorMessage).not.toContain('Failed to fetch')
  })
})
