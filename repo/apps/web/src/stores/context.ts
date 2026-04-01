import { defineStore } from 'pinia'

import { fetchAvailableContexts, me, setActiveContext } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import type { ActiveContext, ContextChoice } from '@/types'

type ContextState = {
  contexts: ContextChoice[]
  activeContext: ActiveContext | null
  loading: boolean
  switching: boolean
  errorMessage: string | null
}

export const useContextStore = defineStore('context', {
  state: (): ContextState => ({
    contexts: [],
    activeContext: null,
    loading: false,
    switching: false,
    errorMessage: null,
  }),
  getters: {
    activeContextKey: (state) =>
      state.activeContext
        ? `${state.activeContext.organization_id}:${state.activeContext.program_id}:${state.activeContext.event_id}:${state.activeContext.store_id}`
        : '',
  },
  actions: {
    _isLikelyNetworkError(error: unknown): boolean {
      const message = error instanceof Error ? error.message : ''
      return message.toLowerCase().includes('failed to fetch') || message.toLowerCase().includes('network')
    },

    _setOfflineAwareContextError(operation: 'load' | 'switch', error: unknown) {
      const offline = typeof navigator !== 'undefined' && !navigator.onLine
      const hasContextSnapshot = this.contexts.length > 0 || this.activeContext !== null

      if (offline || this._isLikelyNetworkError(error)) {
        if (operation === 'load' && hasContextSnapshot) {
          this.errorMessage = 'Offline: using your last available workspace context list.'
          return
        }
        if (operation === 'switch') {
          this.errorMessage = 'Context switching requires an online connection.'
          return
        }
        this.errorMessage = 'Offline: workspace context data is unavailable until reconnect.'
        return
      }

      this.errorMessage = error instanceof Error ? error.message : 'Unable to load contexts'
    },

    syncFromAuthStore() {
      const authStore = useAuthStore()
      this.contexts = authStore.availableContexts
      this.activeContext = authStore.activeContext
    },

    async loadContexts() {
      this.loading = true
      this.errorMessage = null
      const authStore = useAuthStore()
      try {
        this.contexts = await fetchAvailableContexts()
        this.activeContext = authStore.activeContext
      } catch (error) {
        this._setOfflineAwareContextError('load', error)
      } finally {
        this.loading = false
      }
    },

    async switchContext(next: ActiveContext) {
      this.switching = true
      this.errorMessage = null
      try {
        this.activeContext = await setActiveContext(next)
        const payload = await me()
        useAuthStore().hydrateFromMe(payload)
        this.contexts = payload.available_contexts
        this.activeContext = payload.active_context
      } catch (error) {
        this._setOfflineAwareContextError('switch', error)
        throw error
      } finally {
        this.switching = false
      }
    },
  },
})
