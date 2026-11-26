import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('frontend dead export scope', () => {
  it('does not keep uncalled compatibility helpers', () => {
    const mediaIdentity = readFileSync('src/utils/mediaIdentity.ts', 'utf-8')
    const wallpaperTone = readFileSync('src/utils/glassWallpaperTone.ts', 'utf-8')
    const versionChecker = readFileSync('src/composables/useVersionChecker.ts', 'utf-8')
    const backgroundManager = readFileSync('src/utils/backgroundManager.ts', 'utf-8')
    const activityLifecycle = readFileSync('src/utils/appActivityLifecycle.ts', 'utf-8')
    const coreFormatters = readFileSync('src/@core/utils/formatters.ts', 'utf-8')
    const coreIndex = readFileSync('src/@core/utils/index.ts', 'utf-8')
    const coreDom = readFileSync('src/@core/utils/dom.ts', 'utf-8')
    const coreNavigator = readFileSync('src/@core/utils/navigator.ts', 'utf-8')
    const layoutsUtils = readFileSync('src/@layouts/utils.ts', 'utf-8')

    expect(mediaIdentity).not.toContain('export function getMediaId(')
    expect(layoutsUtils).not.toContain('getComputedNavLinkToProp')
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

    for (const pattern of [
      /^export function avatarText\(/m,
      /^export function kFormatter\(/m,
      /^export function formatDownloadCount\(/m,
      /^export function formatDate\(/m,
      /^export function formatDateToMonthShort\(/m,
      /^export const prefixWithPlus/m,
      /^export const formatSeason/m,
      /^export function formatSeasonEpisode\(/m,
      /^export function formatSeconds\(/m,
      /^export function parseDate\(/m,
      /^export function formatEp\(/m,
      /^export function formatRating\(/m,
    ]) {
      expect(coreFormatters).not.toMatch(pattern)
    }
    for (const pattern of [
      /^export function isEmpty\(/m,
      /^export function isNullOrUndefined\(/m,
      /^export function isEmptyArray\(/m,
      /^export function isObject\(/m,
      /^export function isToday\(/m,
      /^export function isContained\(/m,
      /^export function isIntersected\(/m,
    ]) {
      expect(coreIndex).not.toMatch(pattern)
    }
    expect(coreDom).not.toMatch(/^export function useDefer\(/m)
    for (const pattern of [
      /^export async function getClipboardContent\(/m,
      /^export function urlBase64ToUint8Array\(/m,
      /^export function bufferToBase64Url\(/m,
      /^export function base64UrlToUint8Array\(/m,
      /^export const isPWA\s/m,
    ]) {
      expect(coreNavigator).not.toMatch(pattern)
    }
  })
})
