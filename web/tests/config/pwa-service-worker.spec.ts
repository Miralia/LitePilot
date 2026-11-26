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
})
