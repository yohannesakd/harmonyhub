import { createPinia, setActivePinia } from 'pinia'

import router from '@/router'
import { useAuthStore } from '@/stores/auth'

function setAuthenticatedSession(permissions: string[], role: 'student' | 'referee' | 'staff' | 'administrator' = 'staff') {
  const authStore = useAuthStore()
  authStore.isBootstrapping = false
  authStore.user = {
    id: 'user-1',
    username: 'staff',
    is_active: true,
    mfa_totp_enabled: false,
  }
  authStore.activeContext = {
    organization_id: 'org-1',
    program_id: 'program-1',
    event_id: 'event-1',
    store_id: 'store-1',
    role,
  }
  authStore.availableContexts = []
  authStore.permissions = permissions
}

describe('router permission guards', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    await router.push('/login')
  })

  it('redirects unauthenticated users to login', async () => {
    const authStore = useAuthStore()
    authStore.isBootstrapping = false
    authStore.user = null
    authStore.activeContext = null
    authStore.permissions = []

    await router.push('/operations')
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('redirects authenticated users away from unauthorized privileged routes', async () => {
    setAuthenticatedSession(['dashboard.view'])

    await router.push('/operations')
    expect(router.currentRoute.value.path).toBe('/dashboard')

    await router.push('/recommendations')
    expect(router.currentRoute.value.path).toBe('/dashboard')

    await router.push('/fulfillment')
    expect(router.currentRoute.value.path).toBe('/dashboard')

    await router.push('/policy-management')
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('allows authenticated users into privileged routes when permission is present', async () => {
    setAuthenticatedSession([
      'dashboard.view',
      'operations.view',
      'fulfillment.manage',
      'abac.policy.manage',
      'recommendations.manage',
      'directory.view',
    ])

    await router.push('/operations')
    expect(router.currentRoute.value.path).toBe('/operations')

    await router.push('/fulfillment')
    expect(router.currentRoute.value.path).toBe('/fulfillment')

    await router.push('/policy-management')
    expect(router.currentRoute.value.path).toBe('/policy-management')

    await router.push('/recommendations')
    expect(router.currentRoute.value.path).toBe('/recommendations')

    await router.push('/roster')
    expect(router.currentRoute.value.path).toBe('/roster')
  })

  it('enforces roster route role boundaries for student vs referee', async () => {
    setAuthenticatedSession(['dashboard.view', 'directory.view'], 'student')

    await router.push('/roster')
    expect(router.currentRoute.value.path).toBe('/dashboard')

    setAuthenticatedSession(['dashboard.view', 'directory.view'], 'referee')
    await router.push('/roster')
    expect(router.currentRoute.value.path).toBe('/roster')
  })
})
