import { existsSync, readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const source = readFileSync('src/service-worker.ts', 'utf-8')

describe('PWA service worker subpath assets', () => {
  it('resolves offline fallback and notification icon relative to the worker scope', () => {
    expect(source).toContain('self.registration.scope')
    expect(source).toContain("matchPrecache(scopedAssetUrl('offline.html'))")
    expect(source).not.toContain("icon: '/logo.png'")
    expect(source).not.toContain("caches.match('/offline.html')")
    expect(existsSync('src/types/workbox-precaching.d.ts')).toBe(false)
  })

  it('retires the font runtime route while still cleaning legacy font caches', () => {
    expect(source).not.toContain("request.destination === 'font'")
    expect(source).not.toContain('`font-cache-${RESOURCE_VERSION}`')
    expect(source).toContain("'font-cache'")
  })

  it('registers the TMDB image route before the generic image route', () => {
    const tmdbRouteIndex = source.indexOf("url.hostname === 'image.tmdb.org'")
    const imageRouteIndex = source.indexOf("request.destination === 'image'")

    expect(tmdbRouteIndex).toBeGreaterThanOrEqual(0)
    expect(imageRouteIndex).toBeGreaterThanOrEqual(0)
    expect(tmdbRouteIndex).toBeLessThan(imageRouteIndex)
  })

  it('keeps only the worker identity probes without badge storage or Web Push handlers', () => {
    expect(source).toContain('LITEPILOT_SW_PING')
    expect(source).toContain('LITEPILOT_SW_PONG')
    expect(source).toContain('GET_UNREAD_COUNT')
    expect(source).not.toContain('CLEAR_BADGE')
    expect(source).not.toContain('UPDATE_BADGE')
    expect(source).not.toContain('mp_unread_count')
    expect(source).not.toContain("addEventListener('push'")
    expect(source).not.toContain("addEventListener('notificationclick'")
    expect(source).not.toContain('showNotification')
  })

  it('cleans legacy badge database and native badge state during activation', () => {
    expect(source).toContain('cleanupLegacyBadgeState')
    expect(source).toContain("indexedDB.deleteDatabase('mp_badge_db')")
    expect(source).toContain('clearAppBadge')
    expect(source.match(/mp_badge_db/g) ?? []).toHaveLength(1)
    expect(source).not.toContain('objectStore')
    expect(source).not.toContain('mp_unread_count')
  })
})
