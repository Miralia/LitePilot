import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('frontend dead export scope', () => {
  it('does not keep uncalled compatibility helpers', () => {
    const mediaIdentity = readFileSync('src/utils/mediaIdentity.ts', 'utf-8')
    const wallpaperTone = readFileSync('src/utils/glassWallpaperTone.ts', 'utf-8')
    const versionChecker = readFileSync('src/composables/useVersionChecker.ts', 'utf-8')
    const backgroundManager = readFileSync('src/utils/backgroundManager.ts', 'utf-8')
    const activityLifecycle = readFileSync('src/utils/appActivityLifecycle.ts', 'utf-8')

    expect(mediaIdentity).not.toContain('export function getMediaId(')
    expect(wallpaperTone).not.toContain('export async function loadGlassWallpaperToneProfile(')
    for (const name of ['reloadWithTimestamp', 'clearCachesAndServiceWorker', 'clearCacheAndReload']) {
      expect(versionChecker).not.toContain(name)
    }
    expect(backgroundManager).not.toContain('export class BackgroundManager')
    expect(backgroundManager).not.toContain('export const backgroundManager')
    for (const name of [
      'getTimerStatus',
      'getTimersInfo',
      'isUserActive',
      'getLastActivityTime',
      'getStatus',
      'getBackgroundTimerStatus',
      'pausedAt',
    ]) {
      expect(backgroundManager).not.toContain(name)
    }
    expect(activityLifecycle).not.toContain('getLastActivityAt()')
    expect(activityLifecycle).not.toContain('markActivity()')
  })
})
