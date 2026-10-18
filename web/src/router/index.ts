import { createRouter, createWebHashHistory } from 'vue-router'
import { configureNProgress } from '@/api/nprogress'
import { useAuthStore, useUserStore } from '@/stores'
import { setNavigatingState as setRequestNavigatingState } from '@/utils/requestOptimizer'
import {
  buildUserPermissionContext,
  hasItemPermission,
  PERMISSION_FEATURE,
  type PermissionProtectedItem,
  type UserPermissionKey,
} from '@/utils/permission'

// Nprogress
configureNProgress()

// Router
const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  scrollBehavior(to: any, from: any, savedPosition: any) {
    // 如果页面有缓存那么恢复其位置, 否则始终滚动到顶部
    if (to.meta.keepAlive && savedPosition) return savedPosition
    return { top: 0 }
  },
  routes: [
    {
      path: '/',
      redirect: () => {
        const authStore = useAuthStore()
        if (!authStore.token) return '/login'
        return '/dashboard'
      },
    },
    {
      path: '/',
      component: () => import('../layouts/default.vue'),
      children: [
        {
          path: '/dashboard',
          component: () => import('../pages/dashboard.vue'),
          meta: {
            keepAlive: true,
            requiresAuth: true,
            permission: 'admin',
          },
        },
        {
          path: '/history',
          component: () => import('../pages/history.vue'),
          meta: {
            keepAlive: true,
            requiresAuth: true,
            permission: 'manage',
            feature: PERMISSION_FEATURE.MANAGE_HISTORY,
            hideFooter: true,
          },
        },
        {
          path: '/setting',
          component: () => import('../pages/setting.vue'),
          meta: {
            keepAlive: true,
            requiresAuth: true,
            permission: 'admin',
          },
        },
        {
          path: '/filemanager',
          component: () => import('../pages/filemanager.vue'),
          meta: {
            keepAlive: true,
            requiresAuth: true,
            permission: 'manage',
            feature: PERMISSION_FEATURE.MANAGE_FILEMANAGER,
            hideFooter: true,
          },
        },
      ],
    },
    {
      path: '/',
      component: () => import('../layouts/blank.vue'),
      children: [
        {
          path: 'login',
          component: () => import('../pages/login.vue'),
        },
        {
          path: '/:pathMatch(.*)*',
          component: () => import('../pages/[...all].vue'),
        },
      ],
    },
  ],
})

async function getRoutePermission(to: any): Promise<PermissionProtectedItem> {
  if (to.meta.permission) {
    return {
      permission: to.meta.permission as UserPermissionKey,
      feature: to.meta.feature,
    }
  }

  return {}
}

// 路由导航守卫
router.beforeEach(async (to: any, from: any, next: any) => {
  // 设置导航状态 - 同时中断API请求
  setRequestNavigatingState(true)

  // 认证 Store
  const authStore = useAuthStore()
  // 登录页的实验参数不是登录后可恢复的业务目标。
  if (to.path !== '/login') authStore.originalPath = to.fullPath
  const isAuthenticated = authStore.token !== null

  if (to.meta.requiresAuth && !isAuthenticated) {
    // 用户未登录，重定向到登录页
    setRequestNavigatingState(false)
    next('/login')
  } else if (to.meta.requiresAuth) {
    const routePermission = await getRoutePermission(to)
    if (!routePermission.permission && !routePermission.feature) {
      next()
      return
    }

    const userStore = useUserStore()
    const allowed = hasItemPermission(
      routePermission,
      buildUserPermissionContext(userStore.superUser, userStore.permissions),
    )
    if (!allowed) {
      setRequestNavigatingState(false)
      next('/dashboard')
      return
    }
    next()
  } else {
    next()
  }
})

// 路由导航完成后
router.afterEach(() => {
  setTimeout(() => {
    setRequestNavigatingState(false)
  }, 100)
})

// 导出默认对象
export default router
