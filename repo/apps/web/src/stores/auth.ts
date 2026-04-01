import { defineStore } from 'pinia'

import { cacheAuthMe, clearCachedAuthMe, clearScopedReadCacheForUser, loadCachedAuthMe } from '@/offline/readCache'
import { writeQueueSingleton } from '@/offline/writeQueue'
import { notifyAuthBoundaryChange } from '@/pwa/registerServiceWorker'
import { ApiError, login as apiLogin, logout as apiLogout, me } from '@/services/api'
import type { ActiveContext, ContextChoice, UserSummary } from '@/types'

type AuthState = {
  user: UserSummary | null
  permissions: string[]
  availableContexts: ContextChoice[]
  activeContext: ActiveContext | null
  isBootstrapping: boolean
  isMfaRequired: boolean
  errorMessage: string | null
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: null,
    permissions: [],
    availableContexts: [],
    activeContext: null,
    isBootstrapping: true,
    isMfaRequired: false,
    errorMessage: null,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.user),
    roleLabel: (state) => state.activeContext?.role ?? 'unknown',
  },
  actions: {
    async clearUserOfflineArtifacts(userId: string) {
      clearCachedAuthMe(userId)
      clearScopedReadCacheForUser(userId)
      writeQueueSingleton.removeForUser(userId)
      await notifyAuthBoundaryChange()
    },

    hydrateFromMe(payload: {
      user: UserSummary
      permissions: string[]
      available_contexts: ContextChoice[]
      active_context: ActiveContext | null
    }) {
      this.user = payload.user
      this.permissions = payload.permissions
      this.availableContexts = payload.available_contexts
      this.activeContext = payload.active_context
    },

    async bootstrap() {
      this.isBootstrapping = true
      this.errorMessage = null
      try {
        const payload = await me()
        this.hydrateFromMe(payload)
        await cacheAuthMe(payload)
      } catch {
        const cachedPayload = await loadCachedAuthMe()
        if (typeof navigator !== 'undefined' && !navigator.onLine && cachedPayload) {
          this.hydrateFromMe(cachedPayload)
          this.errorMessage = 'Using cached session while offline. Security-sensitive actions remain online-only.'
        } else {
          clearCachedAuthMe()
          this.user = null
          this.permissions = []
          this.availableContexts = []
          this.activeContext = null
        }
      } finally {
        this.isBootstrapping = false
      }
    },

    async signIn(username: string, password: string, totpCode?: string) {
      const previousUserId = this.user?.id ?? null
      this.errorMessage = null
      this.isMfaRequired = false
      try {
        const payload = await apiLogin(username, password, totpCode)

        if (previousUserId && previousUserId !== payload.user.id) {
          await this.clearUserOfflineArtifacts(previousUserId)
        }

        this.hydrateFromMe(payload)
        await cacheAuthMe(payload)
      } catch (error) {
        this.user = null
        this.permissions = []
        this.availableContexts = []
        this.activeContext = null

        if (error instanceof ApiError && error.code === 'MFA_REQUIRED') {
          this.isMfaRequired = true
          this.errorMessage = 'Multi-factor code required. Enter your TOTP code to continue.'
        } else {
          this.errorMessage = error instanceof Error ? error.message : 'Unable to sign in'
        }
        throw error
      }
    },

    async signOut() {
      const activeUserId = this.user?.id
      let logoutError: unknown = null

      try {
        await apiLogout()
      } catch (error) {
        logoutError = error
      } finally {
        if (activeUserId) {
          await this.clearUserOfflineArtifacts(activeUserId)
        } else {
          clearCachedAuthMe()
          await notifyAuthBoundaryChange()
        }
      }

      this.user = null
      this.permissions = []
      this.availableContexts = []
      this.activeContext = null
      this.isMfaRequired = false

      if (logoutError) {
        throw logoutError
      }
    },
  },
})
