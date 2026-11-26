import { readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

function listFiles(directory: string, prefix = ''): string[] {
  return readdirSync(directory).flatMap(entry => {
    const relativePath = prefix ? `${prefix}/${entry}` : entry
    const absolutePath = join(directory, entry)
    return statSync(absolutePath).isDirectory() ? listFiles(absolutePath, relativePath) : [relativePath]
  })
}

describe('frontend asset scope', () => {
  it('only keeps assets consumed by the simplified application', () => {
    const files = listFiles('src/assets/images').sort()

    expect(files).toEqual([
      'avatars/avatar-1.png',
      'logo.png',
      'logo.svg',
      'logos/bangumi.png',
      'logos/downloader.png',
      'logos/emby.png',
      'logos/github.png',
      'logos/mediaserver.png',
      'logos/notification.png',
      'logos/python.png',
      'logos/qbittorrent.png',
      'logos/telegram.webp',
      'logos/tmdb.png',
      'misc/emby.png',
      'misc/smb.png',
      'misc/storage.png',
      'no-image.jpeg',
      'pages/404.svg',
    ])
  })
})
