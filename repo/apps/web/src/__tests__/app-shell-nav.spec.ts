import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AppShell from '@/components/layout/AppShell.vue'
import { useAuthStore } from '@/stores/auth'

const syncStoreMock = {
  networkOnline: true,
  queueItems: [],
  initializeNetworkListener: vi.fn(),
  setQueueItems: vi.fn(),
}

vi.mock('@/stores/sync', () => ({
  useSyncStore: () => syncStoreMock,
}))

vi.mock('@/offline/writeQueue', () => ({
  writeQueueSingleton: {
    listForScope: vi.fn(() => []),
  },
}))

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/dashboard', component: { template: '<div />' } },
      { path: '/directory', component: { template: '<div />' } },
      { path: '/repertoire', component: { template: '<div />' } },
      { path: '/recommendations', component: { template: '<div />' } },
      { path: '/ordering', component: { template: '<div />' } },
      { path: '/roster', component: { template: '<div />' } },
      { path: '/login', component: { template: '<div />' } },
    ],
  })
}

describe('AppShell navigation visibility', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    syncStoreMock.initializeNetworkListener.mockClear()
    syncStoreMock.setQueueItems.mockClear()
  })

  it('hides recommendations link for non-managers and shows roster link for referee scope', async () => {
    const router = createTestRouter()
    await router.push('/dashboard')
    await router.isReady()

    const authStore = useAuthStore()
    authStore.user = { id: 'u-1', username: 'referee', is_active: true, mfa_totp_enabled: false }
    authStore.activeContext = {
      organization_id: 'org-1',
      program_id: 'prog-1',
      event_id: 'event-1',
      store_id: 'store-1',
      role: 'referee',
    }
    authStore.permissions = ['directory.view', 'repertoire.view', 'recommendations.view']

    const wrapper = mount(AppShell, {
      props: {
        contexts: [],
        activeContext: authStore.activeContext,
      },
      slots: {
        default: '<div />',
      },
      global: {
        plugins: [router],
        stubs: {
          ContextSwitcher: { template: '<div />' },
          SyncStatusBadge: { template: '<div />' },
        },
      },
    })

    expect(wrapper.text()).toContain('Roster')
    expect(wrapper.text()).not.toContain('Recommendations')
    const skipLink = wrapper.get('a.shell__skip-link')
    expect(skipLink.attributes('href')).toBe('#main-content')
  })

  it('shows recommendations link for managers', async () => {
    const router = createTestRouter()
    await router.push('/dashboard')
    await router.isReady()

    const authStore = useAuthStore()
    authStore.user = { id: 'u-2', username: 'staff', is_active: true, mfa_totp_enabled: false }
    authStore.activeContext = {
      organization_id: 'org-1',
      program_id: 'prog-1',
      event_id: 'event-1',
      store_id: 'store-1',
      role: 'staff',
    }
    authStore.permissions = ['directory.view', 'recommendations.view', 'recommendations.manage']

    const wrapper = mount(AppShell, {
      props: {
        contexts: [],
        activeContext: authStore.activeContext,
      },
      slots: {
        default: '<div />',
      },
      global: {
        plugins: [router],
        stubs: {
          ContextSwitcher: { template: '<div />' },
          SyncStatusBadge: { template: '<div />' },
        },
      },
    })

    expect(wrapper.text()).toContain('Recommendations')
  })
})
