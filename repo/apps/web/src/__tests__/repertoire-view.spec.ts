import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import RepertoireView from '@/views/RepertoireView.vue'

const bootstrapWorkspace = vi.fn().mockResolvedValue(undefined)
const switchWorkspaceContext = vi.fn().mockResolvedValue(undefined)

const authStore = {
  user: {
    id: 'user-1',
    username: 'student',
    is_active: true,
    mfa_totp_enabled: false,
  },
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
    fetchRepertoire: vi.fn(),
    fetchRepertoireRecommendations: vi.fn(),
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

import { fetchRepertoire, fetchRepertoireRecommendations } from '@/services/api'
import { cacheScopedRead, loadScopedRead } from '@/offline/readCache'

describe('RepertoireView offline browse fallback', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    contextStore.errorMessage = null
  })

  it('caches live repertoire payloads per user+context scope', async () => {
    vi.mocked(fetchRepertoire).mockResolvedValue({
      total: 1,
      results: [
        {
          id: 'rep-live',
          title: 'Live Overture',
          composer: 'L. Composer',
          tags: [],
          performer_names: ['Ava'],
          regions: ['North Region'],
        },
      ],
    })
    vi.mocked(fetchRepertoireRecommendations).mockResolvedValue({
      config_scope: 'event_store',
      results: [],
    })
    vi.mocked(loadScopedRead).mockReturnValue(null)

    const wrapper = mount(RepertoireView, {
      global: {
        stubs: {
          AppShell: { template: '<div><slot /></div>' },
          RepertoireSearchForm: { template: '<div />' },
          RepertoireRecommendationRail: { template: '<div />' },
          RepertoireResultCard: {
            props: ['item'],
            template: '<article>{{ item.title }}</article>',
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Data source: live context data')
    expect(wrapper.text()).toContain('Live Overture')
    expect(cacheScopedRead).toHaveBeenCalledWith(
      'user-1:org-1:prog-1:event-1:store-1',
      expect.stringContaining('repertoire_search:'),
      expect.objectContaining({ total: 1 }),
    )
    expect(cacheScopedRead).toHaveBeenCalledWith(
      'user-1:org-1:prog-1:event-1:store-1',
      expect.stringContaining('repertoire_recommendations:'),
      expect.any(Array),
    )
  })

  it('falls back to cached repertoire results when offline fetch fails', async () => {
    vi.mocked(fetchRepertoire).mockRejectedValue(new TypeError('Failed to fetch'))
    vi.mocked(fetchRepertoireRecommendations).mockRejectedValue(new TypeError('Failed to fetch'))
    vi.mocked(loadScopedRead).mockImplementation((_, resource) => {
      if (resource.startsWith('repertoire_search:')) {
        return {
          total: 1,
          results: [
            {
              id: 'rep-cached',
              title: 'Cached Suite',
              composer: 'C. Offline',
              tags: [],
              performer_names: ['Offline Performer'],
              regions: ['West Region'],
            },
          ],
        }
      }
      if (resource.startsWith('repertoire_recommendations:')) {
        return []
      }
      return null
    })

    const wrapper = mount(RepertoireView, {
      global: {
        stubs: {
          AppShell: { template: '<div><slot /></div>' },
          RepertoireSearchForm: { template: '<div />' },
          RepertoireRecommendationRail: { template: '<div />' },
          RepertoireResultCard: {
            props: ['item'],
            template: '<article>{{ item.title }}</article>',
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Offline: showing cached repertoire results for this context and filter set.')
    expect(wrapper.text()).toContain('Data source: cached offline snapshot')
    expect(wrapper.text()).toContain('Cached Suite')
    expect(cacheScopedRead).not.toHaveBeenCalled()
  })
})
