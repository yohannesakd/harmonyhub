import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '@/views/DashboardView.vue'
import DirectoryView from '@/views/DirectoryView.vue'
import FulfillmentView from '@/views/FulfillmentView.vue'
import ImportsAdminView from '@/views/ImportsAdminView.vue'
import LoginView from '@/views/LoginView.vue'
import OrderingView from '@/views/OrderingView.vue'
import OperationsView from '@/views/OperationsView.vue'
import PolicyManagementView from '@/views/PolicyManagementView.vue'
import RecommendationsView from '@/views/RecommendationsView.vue'
import RosterView from '@/views/RosterView.vue'
import RepertoireView from '@/views/RepertoireView.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/dashboard',
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { public: true },
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: DashboardView,
    },
    {
      path: '/directory',
      name: 'directory',
      component: DirectoryView,
    },
    {
      path: '/repertoire',
      name: 'repertoire',
      component: RepertoireView,
    },
    {
      path: '/recommendations',
      name: 'recommendations',
      component: RecommendationsView,
      meta: { requiredAnyPermissions: ['recommendations.manage'] },
    },
    {
      path: '/roster',
      name: 'roster',
      component: RosterView,
      meta: {
        requiredAnyPermissions: ['directory.view'],
        requiredRoles: ['referee', 'staff', 'administrator'],
      },
    },
    {
      path: '/ordering',
      name: 'ordering',
      component: OrderingView,
    },
    {
      path: '/fulfillment',
      name: 'fulfillment',
      component: FulfillmentView,
      meta: { requiredAnyPermissions: ['fulfillment.manage'] },
    },
    {
      path: '/imports-admin',
      name: 'imports-admin',
      component: ImportsAdminView,
      meta: { requiredAnyPermissions: ['imports.manage', 'account_control.manage'] },
    },
    {
      path: '/operations',
      name: 'operations',
      component: OperationsView,
      meta: {
        requiredAnyPermissions: [
          'operations.view',
          'audit.view',
          'export.manage',
          'backup.manage',
          'recovery_drill.manage',
        ],
      },
    },
    {
      path: '/policy-management',
      name: 'policy-management',
      component: PolicyManagementView,
      meta: {
        requiredAnyPermissions: ['abac.policy.manage'],
      },
    },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()
  if (authStore.isBootstrapping) {
    await authStore.bootstrap()
  }

  if (to.meta.public) {
    return true
  }

  if (!authStore.isAuthenticated) {
    return { path: '/login' }
  }

  const requiredAnyPermissions = to.meta.requiredAnyPermissions as string[] | undefined
  if (
    requiredAnyPermissions &&
    requiredAnyPermissions.length > 0 &&
    !requiredAnyPermissions.some((permission) => authStore.permissions.includes(permission))
  ) {
    return { path: '/dashboard' }
  }

  const requiredRoles = to.meta.requiredRoles as string[] | undefined
  if (requiredRoles && requiredRoles.length > 0) {
    const activeRole = authStore.activeContext?.role
    if (!activeRole || !requiredRoles.includes(activeRole)) {
      return { path: '/dashboard' }
    }
  }

  return true
})

export default router
