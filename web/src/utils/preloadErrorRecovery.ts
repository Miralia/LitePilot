export const PRELOAD_ERROR_RELOAD_KEY = 'litepilot:preload-error-reload'
export const PRELOAD_ERROR_RELOAD_COOLDOWN_MS = 60_000

type PreloadErrorTarget = Pick<EventTarget, 'addEventListener' | 'removeEventListener'>
type PreloadErrorStorage = Pick<Storage, 'getItem' | 'setItem'>

interface PreloadErrorRecoveryOptions {
  target?: PreloadErrorTarget
  storage?: PreloadErrorStorage
  isOnline?: () => boolean
  now?: () => number
  reload?: () => void
}

/**
 * 安装 Vite 懒加载失败恢复监听。
 *
 * 部署新版本后，旧页面仍可能引用已经替换的哈希 chunk。在线时刷新一次可以拿到新入口；
 * 离线时不能刷新，否则会把仍可使用的缓存页面变成加载失败页面。
 */
export function installPreloadErrorRecovery(options: PreloadErrorRecoveryOptions = {}): () => void {
  const target = options.target ?? window
  const storage = options.storage ?? window.sessionStorage
  const isOnline = options.isOnline ?? (() => navigator.onLine)
  const now = options.now ?? (() => Date.now())
  const reload = options.reload ?? (() => window.location.reload())

  const handlePreloadError = (event: Event) => {
    if (!isOnline()) return

    const currentTime = now()
    const lastReloadAt = Number(storage.getItem(PRELOAD_ERROR_RELOAD_KEY))
    if (Number.isFinite(lastReloadAt) && currentTime - lastReloadAt < PRELOAD_ERROR_RELOAD_COOLDOWN_MS) return

    event.preventDefault()
    storage.setItem(PRELOAD_ERROR_RELOAD_KEY, String(currentTime))
    reload()
  }

  target.addEventListener('vite:preloadError', handlePreloadError)
  return () => target.removeEventListener('vite:preloadError', handlePreloadError)
}
