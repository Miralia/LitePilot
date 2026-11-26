const USER_DATA_CACHE_PREFIXES = ['api-cache-', 'image-cache-', 'tmdb-image-cache-']

/** 判断运行时缓存是否可能包含媒体库、文件或浏览痕迹等用户数据。 */
export function isUserDataRuntimeCache(cacheName: string): boolean {
  return USER_DATA_CACHE_PREFIXES.some(prefix => cacheName.startsWith(prefix))
}

/**
 * 清理用户数据缓存，保留公共 App Shell 与静态资源。
 *
 * 退出登录或凭证失效后不能继续保留 API 与媒体图片副本，否则同一浏览器会话中的
 * 后续使用者仍可能通过离线缓存看到上一账户的媒体库信息。
 */
export async function clearUserDataCaches(cacheStorage: CacheStorage | undefined = globalThis.caches): Promise<void> {
  if (!cacheStorage) return

  const cacheNames = await cacheStorage.keys()
  await Promise.all(cacheNames.filter(isUserDataRuntimeCache).map(cacheName => cacheStorage.delete(cacheName)))
}
