import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DirectoryView from '@/views/DirectoryView.vue'

const bootstrapWorkspace = vi.fn().mockResolvedValue(undefined)
const switchWorkspaceContext = vi.fn().mockResolvedValue(undefined)

const authStore = {
  user: {
    id: 'user-1',
    username: 'student',
    is_active: true,
    mfa_totp_enabled: false,
  },
  permissions: ['directory.view'],
}

const contextStore = {
  contexts: [],
  activeContext: {
    organization_id: 'org-1',
    program_id: 'prog-1',
    event_id: 'event-1',
    store_id: 'store-1',
    role: 'student' as const,
  },
  activeContextKey: 'org-1:prog-1:event-1:store-1',
  switching: false,
  errorMessage: null,
}

vi.mock('@/composables/useWorkspaceContext', () => ({
  useWorkspaceContext: () => ({
    authStore,
    contextStore,
    bootstrapWorkspace,
    switchWorkspaceContext,
  }),
}))

vi.mock('@/services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/api')>()
  return {
    ...actual,
    fetchDirectory: vi.fn(),
    fetchDirectoryRecommendations: vi.fn(),
  }
})

vi.mock('@/offline/readCache', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/offline/readCache')>()
  return {
    ...actual,
    cacheScopedRead: vi.fn(),
    loadScopedRead: vi.fn(),
  }
})

import { fetchDirectory, fetchDirectoryRecommendations } from '@/services/api'
import { cacheScopedRead, loadScopedRead } from '@/offline/readCache'

describe('DirectoryView offline browse fallback', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    contextStore.errorMessage = null
  })

  it('caches live directory payloads per user+context scope', async () => {
    vi.mocked(fetchDirectory).mockResolvedValue({
      total: 1,
      results: [
        {
          id: 'entry-live',
          display_name: 'Ava Live',
          stage_name: null,
          region: 'North Region',
          tags: [],
          repertoire: ['Live Piece'],
          availability_windows: [],
          contact: { email: 'a***@example.com', phone: '***', address_line1: '***', masked: true },
          can_reveal_contact: false,
        },
      ],
    })
    vi.mocked(fetchDirectoryRecommendations).mockResolvedValue({
      config_scope: 'event_store',
      results: [],
    })
    vi.mocked(loadScopedRead).mockReturnValue(null)

    const wrapper = mount(DirectoryView, {
      global: {
        stubs: {
          AppShell: { template: '<div><slot /></div>' },
          DirectorySearchForm: { template: '<div />' },
          DirectoryRecommendationRail: { template: '<div />' },
          DirectoryResultCard: {
            props: ['entry'],
            template: '<article>{{ entry.display_name }}</article>',
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Data source: live context data')
    expect(wrapper.text()).toContain('Ava Live')
    expect(cacheScopedRead).toHaveBeenCalledWith(
      'user-1:org-1:prog-1:event-1:store-1',
      expect.stringContaining('directory_search:'),
      expect.objectContaining({ total: 1 }),
    )
    expect(cacheScopedRead).toHaveBeenCalledWith(
      'user-1:org-1:prog-1:event-1:store-1',
      expect.stringContaining('directory_recommendations:'),
      expect.any(Array),
    )
  })

  it('falls back to cached directory results when offline fetch fails', async () => {
    vi.mocked(fetchDirectory).mockRejectedValue(new TypeError('Failed to fetch'))
    vi.mocked(fetchDirectoryRecommendations).mockRejectedValue(new TypeError('Failed to fetch'))
    vi.mocked(loadScopedRead).mockImplementation((_, resource) => {
      if (resource.startsWith('directory_search:')) {
        return {
          total: 1,
          results: [
            {
              id: 'entry-cached',
              display_name: 'Cached Performer',
              stage_name: null,
              region: 'West Region',
              tags: [],
              repertoire: ['Cached Piece'],
              availability_windows: [],
              contact: { email: 'c***@example.com', phone: '***', address_line1: '***', masked: true },
              can_reveal_contact: false,
            },
          ],
        }
      }
      if (resource.startsWith('directory_recommendations:')) {
        return []
      }
      return null
    })

    const wrapper = mount(DirectoryView, {
      global: {
        stubs: {
          AppShell: { template: '<div><slot /></div>' },
          DirectorySearchForm: { template: '<div />' },
          DirectoryRecommendationRail: { template: '<div />' },
          DirectoryResultCard: {
            props: ['entry'],
            template: '<article>{{ entry.display_name }}</article>',
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Offline: showing cached directory results for this context and filter set.')
    expect(wrapper.text()).toContain('Data source: cached offline snapshot')
    expect(wrapper.text()).toContain('Cached Performer')
    expect(cacheScopedRead).not.toHaveBeenCalled()
  })
})
