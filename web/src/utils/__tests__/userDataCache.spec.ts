import { describe, expect, it, vi } from 'vitest'

import { clearUserDataCaches, isUserDataRuntimeCache } from '../userDataCache'

function createCacheStorage(names: string[]) {
  const deleted: string[] = []
  const storage = {
    keys: vi.fn(async () => names),
    delete: vi.fn(async (name: string) => {
      deleted.push(name)
      return true
    }),
  }

  return { deleted, storage }
}

describe('user data runtime caches', () => {
  it('identifies only cache namespaces that can contain user library data', () => {
    expect(isUserDataRuntimeCache('api-cache-v0.1.0')).toBe(true)
    expect(isUserDataRuntimeCache('image-cache-V2')).toBe(true)
    expect(isUserDataRuntimeCache('tmdb-image-cache-V2')).toBe(true)

    expect(isUserDataRuntimeCache('app-shell-v0.1.0')).toBe(false)
    expect(isUserDataRuntimeCache('static-resources-v0.1.0')).toBe(false)
    expect(isUserDataRuntimeCache('font-cache-V2')).toBe(false)
    expect(isUserDataRuntimeCache('workbox-precache-v2')).toBe(false)
  })

  it('deletes user data caches without removing the public app shell or static assets', async () => {
    const { deleted, storage } = createCacheStorage([
      'api-cache-v0.1.0',
      'image-cache-V2',
      'tmdb-image-cache-V2',
      'app-shell-v0.1.0',
      'static-resources-v0.1.0',
      'workbox-precache-v2',
    ])

    await clearUserDataCaches(storage as unknown as CacheStorage)

    expect(deleted).toEqual(['api-cache-v0.1.0', 'image-cache-V2', 'tmdb-image-cache-V2'])
  })

  it('does nothing when the Cache Storage API is unavailable', async () => {
    await expect(clearUserDataCaches(undefined)).resolves.toBeUndefined()
  })
})
