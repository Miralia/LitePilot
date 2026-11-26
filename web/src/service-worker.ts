import { cleanupOutdatedCaches, matchPrecache, precacheAndRoute } from 'workbox-precaching'
import { registerRoute, setCatchHandler } from 'workbox-routing'
import { CacheFirst, NetworkFirst, StaleWhileRevalidate } from 'workbox-strategies'
import { ExpirationPlugin } from 'workbox-expiration'
import { CacheableResponsePlugin } from 'workbox-cacheable-response'
import * as navigationPreload from 'workbox-navigation-preload'
import { corsSafeCachePlugin } from '@/utils/serviceWorkerCache'

// Service Worker 类型声明
declare let self: ServiceWorkerGlobalScope & {
  readonly __WB_MANIFEST: Array<{ url: string; revision?: string }>
}

const scopedAssetUrl = (path: string) => new URL(path, self.registration.scope).href

// 缓存版本控制
const RESOURCE_VERSION = 'V2'
// 开发态 dev-sw 可能拿不到 Vite define 注入；仅在开发环境做 dev 兜底
const hasAppVersion = typeof __APP_VERSION__ !== 'undefined'
const hasBuildTime = typeof __BUILD_TIME__ !== 'undefined'
const isDev = import.meta.env.DEV

if (!isDev && (!hasAppVersion || !hasBuildTime)) {
  throw new Error('[SW] Missing __APP_VERSION__ or __BUILD_TIME__ in production build')
}

const appVersion = hasAppVersion ? __APP_VERSION__ : 'dev'
const buildTime = hasBuildTime ? __BUILD_TIME__ : 'dev'
const CACHE_VERSION = `${appVersion}-${buildTime}`

// 启用导航预载
navigationPreload.enable()

// 自动清理旧的预缓存
cleanupOutdatedCaches()

// 预缓存并路由
precacheAndRoute(self.__WB_MANIFEST)

// 监听安装事件
self.addEventListener('install', () => {
  // 强制等待中的 Service Worker 立即激活
  self.skipWaiting()
})

// 监听激活事件
self.addEventListener('activate', event => {
  // 让 Service Worker 立即接管页面
  event.waitUntil(
    (async () => {
      await self.clients.claim()
      // 清理旧版本运行时缓存，并迁移删除已废弃的原生角标状态。
      await Promise.all([cleanupRuntimeCaches(true), cleanupLegacyBadgeState()])
    })(),
  )
})

// 开发环境使用轻量消息确认当前 Worker 身份；旧协议仅用于识别历史 Worker。
const SW_IDENTITY_PING = 'LITEPILOT_SW_PING'
const SW_IDENTITY_PONG = 'LITEPILOT_SW_PONG'
const LEGACY_UNREAD_COUNT_PROBE = 'GET_UNREAD_COUNT'

// 旧角标数据库和系统角标仅做尽力迁移清理，失败不能阻塞新版激活。
async function cleanupLegacyBadgeState(): Promise<void> {
  await new Promise<void>(resolve => {
    try {
      const request = indexedDB.deleteDatabase('mp_badge_db')
      request.onsuccess = () => resolve()
      request.onerror = () => resolve()
      request.onblocked = () => resolve()
    } catch {
      resolve()
    }
  })

  if ('clearAppBadge' in self.navigator) {
    await self.navigator.clearAppBadge().catch(() => undefined)
  }
}

// --- 缓存策略配置 ---

// 导航请求与 App Shell - 优先网络
// 子路径部署时（如 /litepilot/）不能只匹配根路径，否则导航会落到
// 静态资源的 StaleWhileRevalidate 分支，先返回旧页面再后台更新
const isNavigationRequest = ({ request, url }: { request: Request; url: URL }) =>
  request.mode === 'navigate' ||
  url.pathname === '/' ||
  url.pathname === '/index.html' ||
  url.pathname.endsWith('/') ||
  url.pathname.endsWith('/index.html')

registerRoute(
  isNavigationRequest,
  new NetworkFirst({
    cacheName: `app-shell-${CACHE_VERSION}`,
    plugins: [
      new ExpirationPlugin({
        maxEntries: 10,
        maxAgeSeconds: 7 * 24 * 60 * 60, // 7天
      }),
    ],
  }),
)

// 静态资源 (JS, CSS, HTML) - 优先缓存
registerRoute(
  ({ request }) => ['style', 'script', 'worker'].includes(request.destination),
  new StaleWhileRevalidate({
    cacheName: `static-resources-${CACHE_VERSION}`,
    plugins: [
      new CacheableResponsePlugin({
        statuses: [0, 200],
      }),
    ],
  }),
)

// TMDB 图片 - 优先缓存；专用路由必须先于通用图片路由注册。
registerRoute(
  ({ url }) => url.hostname === 'image.tmdb.org',
  new CacheFirst({
    cacheName: `tmdb-image-cache-${RESOURCE_VERSION}`,
    plugins: [
      corsSafeCachePlugin,
      new CacheableResponsePlugin({
        statuses: [0, 200],
      }),
      new ExpirationPlugin({
        maxEntries: 300,
        maxAgeSeconds: 7 * 24 * 60 * 60, // 7天
      }),
    ],
  }),
)

// 图片资源 - 优先缓存
registerRoute(
  ({ request }) => request.destination === 'image',
  new CacheFirst({
    cacheName: `image-cache-${RESOURCE_VERSION}`,
    plugins: [
      corsSafeCachePlugin,
      new CacheableResponsePlugin({
        statuses: [0, 200],
      }),
      new ExpirationPlugin({
        maxEntries: 200,
        maxAgeSeconds: 30 * 24 * 60 * 60, // 30天
      }),
    ],
  }),
)

// API GET 请求 - 优先网络
registerRoute(
  ({ url, request }) =>
    url.pathname.includes('/api/v1/') &&
    request.method === 'GET' &&
    !url.pathname.includes('/api/v1/system/message') && // SSE实时消息流
    !url.pathname.includes('/api/v1/system/progress/') && // SSE实时进度流
    !url.pathname.includes('/api/v1/system/logging') && // SSE实时日志流
    !url.pathname.includes('/api/v1/message/') && // 用户消息接口
    !url.pathname.includes('/api/v1/system/global') && // 系统配置接口
    !url.pathname.includes('/api/v1/auth/') && // 登录认证入口与票据交换
    !url.pathname.includes('/api/v1/login/') && // 登录与登出接口，命中缓存会返回过期 token
    !url.pathname.includes('/api/v1/dashboard/') && // Dashboard实时监控数据
    !url.pathname.includes('/api/v1/tmdb/'), // 识别缓存接口
  new NetworkFirst({
    cacheName: `api-cache-${CACHE_VERSION}`,
    networkTimeoutSeconds: 5,
    plugins: [
      new CacheableResponsePlugin({
        statuses: [0, 200],
      }),
      new ExpirationPlugin({
        maxEntries: 500,
        maxAgeSeconds: 24 * 60 * 60, // 24小时
      }),
    ],
  }),
)

// 设置默认离线页面
setCatchHandler(async ({ request }) => {
  if (request?.destination === 'document') {
    return (await matchPrecache(scopedAssetUrl('offline.html'))) || Response.error()
  }
  return Response.error()
})

// --- 辅助函数 (通知与徽章) ---

// 清理运行时缓存
async function cleanupRuntimeCaches(onlyOld: boolean = false) {
  const cacheNames = await caches.keys()
  // font-cache 已随系统字体栈退役；保留前缀只用于清除旧客户端中的远程字体缓存。
  const runtimeCachePrefixes = [
    'app-shell',
    'static-resources',
    'image-cache',
    'font-cache',
    'api-cache',
    'tmdb-image-cache',
  ]

  // 当前版本的缓存全名
  const currentCacheNames = [
    `app-shell-${CACHE_VERSION}`,
    `static-resources-${CACHE_VERSION}`,
    `image-cache-${RESOURCE_VERSION}`,
    `tmdb-image-cache-${RESOURCE_VERSION}`,
    `api-cache-${CACHE_VERSION}`,
  ]

  await Promise.all(
    cacheNames.map(cacheName => {
      const isRuntimeCache = runtimeCachePrefixes.some(prefix => cacheName.startsWith(prefix))
      if (isRuntimeCache) {
        if (!onlyOld || !currentCacheNames.includes(cacheName)) {
          return caches.delete(cacheName)
        }
      }
      return Promise.resolve()
    }),
  )
}

// 监控缓存大小
async function monitorCacheSize() {
  const cacheSizes: Record<string, number> = {}

  try {
    const cacheNames = await caches.keys()

    // 并行处理所有缓存
    await Promise.all(
      cacheNames.map(async cacheName => {
        const cache = await caches.open(cacheName)
        const requests = await cache.keys()
        let cacheSize = 0

        // 遍历请求以获取响应头部，避免 matchAll 一次性加载大量响应对象到内存
        for (const request of requests) {
          const response = await cache.match(request)
          if (response) {
            const contentLength = response.headers.get('content-length')
            if (contentLength) {
              cacheSize += parseInt(contentLength, 10)
            }
          }
        }
        cacheSizes[cacheName] = cacheSize
      }),
    )

    const calculatedTotalSize = Object.values(cacheSizes).reduce((acc, size) => acc + size, 0)

    // 获取系统级存储估算
    let quota = 0
    let usage = 0
    if (self.navigator.storage && self.navigator.storage.estimate) {
      const estimate = await self.navigator.storage.estimate()
      quota = estimate.quota || 0
      usage = estimate.usage || 0
    }

    // 构造结果：满足 useCacheManager.ts 的需求
    const result = {
      cacheSizes,
      // 优先使用准确的 usage (真实磁盘占用)，如果不可用则退回到计算值
      totalSize: usage || calculatedTotalSize,
      totalSizeMB: ((usage || calculatedTotalSize) / 1024 / 1024).toFixed(2),
      // 额外信息保留，供未来扩展
      quota,
      usage,
      quotaMB: (quota / 1024 / 1024).toFixed(2),
      usageMB: (usage / 1024 / 1024).toFixed(2),
      calculatedTotalSize,
    }

    // 发送缓存统计信息给客户端
    const clients = await self.clients.matchAll()
    clients.forEach(client => {
      client.postMessage({
        type: 'CACHE_SIZE_UPDATE',
        data: result,
      })
    })

    return result
  } catch (error) {
    console.error('Failed to monitor cache size:', error)
    return {
      cacheSizes: {},
      totalSize: 0,
      totalSizeMB: '0.00',
      quota: 0,
      usage: 0,
      quotaMB: '0.00',
      usageMB: '0.00',
    }
  }
}

// --- 事件监听 ---

// 监听消息
self.addEventListener('message', function (event) {
  if (event.data && event.data.type === SW_IDENTITY_PING) {
    event.ports[0]?.postMessage({ type: SW_IDENTITY_PONG })
  } else if (event.data && event.data.type === LEGACY_UNREAD_COUNT_PROBE) {
    // 兼容只支持旧探测协议的历史 Worker 清理流程；未读角标状态已删除。
    event.ports[0]?.postMessage({ count: 0 })
  } else if (event.data && event.data.type === 'CLEANUP_CACHES') {
    // 手动清理: 清理所有运行时缓存
    const performCleanup = async () => {
      await cleanupRuntimeCaches(false)
      return await monitorCacheSize()
    }
    performCleanup()
      .then(cacheInfo => {
        event.ports[0]?.postMessage({ success: true, cacheInfo })
      })
      .catch(error => {
        event.ports[0]?.postMessage({ success: false, error: error instanceof Error ? error.message : String(error) })
      })
  } else if (event.data && event.data.type === 'GET_CACHE_INFO') {
    monitorCacheSize()
      .then(cacheInfo => {
        event.ports[0]?.postMessage({ success: true, cacheInfo })
      })
      .catch(error => {
        event.ports[0]?.postMessage({ success: false, error: error instanceof Error ? error.message : String(error) })
      })
  } else if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})
