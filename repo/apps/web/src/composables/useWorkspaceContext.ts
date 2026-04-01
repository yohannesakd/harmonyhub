import { useAuthStore } from '@/stores/auth'
import { useContextStore } from '@/stores/context'
import type { ActiveContext } from '@/types'

export function useWorkspaceContext() {
  const authStore = useAuthStore()
  const contextStore = useContextStore()

  async function bootstrapWorkspace() {
    await authStore.bootstrap()
    contextStore.syncFromAuthStore()
    await contextStore.loadContexts()
  }

  async function switchWorkspaceContext(next: ActiveContext) {
    await contextStore.switchContext(next)
  }

  return {
    authStore,
    contextStore,
    bootstrapWorkspace,
    switchWorkspaceContext,
  }
}
