import { getLogoUrl } from '@/utils/imageUtils'
import { describe, expect, it } from 'vitest'

describe('imageUtils logo boundary', () => {
  it.each([
    'bangumi',
    'downloader',
    'emby',
    'github',
    'mediaserver',
    'notification',
    'python',
    'qbittorrent',
    'telegram',
    'tmdb',
  ])('keeps the active %s logo available', logo => {
    expect(getLogoUrl(logo)).toBeTruthy()
  })

  it.each(['chrome', 'douban'])('does not expose the removed %s logo', logo => {
    expect(getLogoUrl(logo)).toBe('')
  })
})
