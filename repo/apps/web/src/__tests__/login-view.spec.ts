import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

import LoginView from '@/views/LoginView.vue'
import { useAuthStore } from '@/stores/auth'

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/login', component: { template: '<div />' } }],
  })
}

describe('LoginView accessibility feedback', () => {
  it('announces MFA requirement and login errors with live regions', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    const authStore = useAuthStore()
    authStore.isMfaRequired = true
    authStore.errorMessage = 'Invalid credentials'

    const router = createTestRouter()
    await router.push('/login')
    await router.isReady()

    const wrapper = mount(LoginView, {
      global: {
        plugins: [pinia, router],
      },
    })

    const status = wrapper.get('[role="status"]')
    const alert = wrapper.get('[role="alert"]')

    expect(status.text()).toContain('Multi-factor authentication is required')
    expect(status.attributes('aria-live')).toBe('polite')
    expect(alert.text()).toContain('Invalid credentials')
    expect(alert.attributes('aria-live')).toBe('assertive')
  })
})
