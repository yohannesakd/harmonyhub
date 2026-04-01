import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import RosterView from '@/views/RosterView.vue'

const bootstrapWorkspace = vi.fn().mockResolvedValue(undefined)
const switchWorkspaceContext = vi.fn().mockResolvedValue(undefined)

const authStore = {
  activeContext: {
    organization_id: 'org-1',
    program_id: 'prog-1',
    event_id: 'event-1',
    store_id: 'store-1',
    role: 'referee' as const,
  },
}

const contextStore = {
  contexts: [],
  activeContext: authStore.activeContext,
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
  }
})

import { fetchDirectory } from '@/services/api'

describe('RosterView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    authStore.activeContext.role = 'referee'
    vi.mocked(fetchDirectory).mockResolvedValue({
      total: 1,
      results: [
        {
          id: 'entry-1',
          display_name: 'Ava Martinez',
          stage_name: 'Ava M',
          region: 'North Region',
          tags: ['jazz'],
          repertoire: ['Moonlight Sonata'],
          availability_windows: [],
          contact: {
            email: 'a***@***.com',
            phone: '***-***-0000',
            address_line1: '*** Hidden address ***',
            masked: true,
          },
          can_reveal_contact: false,
        },
      ],
    })
  })

  it('renders limited roster visibility and supports search', async () => {
    const wrapper = mount(RosterView, {
      global: {
        stubs: {
          AppShell: { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Referee access is intentionally limited')
    expect(wrapper.text()).toContain('Ava Martinez')
    expect(fetchDirectory).toHaveBeenCalledWith({ q: undefined })

    await wrapper.find('input[placeholder="Name, stage alias, repertoire"]').setValue('Ava')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(fetchDirectory).toHaveBeenLastCalledWith({ q: 'Ava' })
  })
})
