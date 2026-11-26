import { h } from 'vue'
import { useToast } from 'vue-toastification'
import { Workbox } from 'workbox-window'
import i18n from '@/plugins/i18n'
import VersionUpdateToast from '@/components/toast/VersionUpdateToast.vue'
import {
  createServiceWorkerCoordinator,
  resolveServiceWorkerRegistration,
  type ServiceWorkerRegistrationConfig,
} from '@/utils/serviceWorkerCoordinator'

// 全局状态
let isUpdateToastShown = false

const serviceWorkerRegistration =
  'serviceWorker' in navigator
    ? resolveServiceWorkerRegistration(
        import.meta.env.BASE_URL,
        document.baseURI,
        import.meta.env.DEV,
        __PWA_DEVELOPMENT__,
      )
    : null

/** 显示全局唯一的版本更新通知。 */
function showUpdateNotification(message: string, refreshText?: string, onRefresh?: () => void): void {
  if (isUpdateToastShown) return
  isUpdateToastShown = true
  const component = h(VersionUpdateToast, {
    message,
    refreshText,
    onRefresh,
  })

  useToast().info(component, {
    timeout: false,
    closeButton: false,
    closeOnClick: false,
    draggable: false,
  })
}

const serviceWorkerCoordinator = createServiceWorkerCoordinator({
  registration: serviceWorkerRegistration,
  createClient: (registration: ServiceWorkerRegistrationConfig) =>
    new Workbox(registration.scriptUrl, {
      scope: registration.scope,
      type: registration.type,
    }),
  onUpdateActivated: () => {
    showUpdateNotification(i18n.global.t('common.swUpdateReady'), i18n.global.t('common.refresh'), reloadPage)
  },
  onError: error => console.error('[VersionChecker] Service Worker 注册失败:', error),
})

/**
 * 普通刷新页面
 */
export const reloadPage = (): void => {
  window.location.reload()
}

/**
 * 初始化应用唯一的 Service Worker coordinator。
 * 普通 dev 不注册；production 与显式 dev:pwa 复用同一个注册 Promise。
 */
export const initializeServiceWorker = (): Promise<ServiceWorkerRegistration | undefined> =>
  serviceWorkerCoordinator.initialize()
