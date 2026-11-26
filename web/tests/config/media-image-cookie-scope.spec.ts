import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const root = resolve(__dirname, '../..')
const files = [
  'src/api/types.ts',
  'src/components/cards/PosterCard.vue',
  'src/components/cards/PlayingBackdropCard.vue',
  'src/components/cards/LibraryCard.vue',
]

describe('media image cookie scope', () => {
  it('does not retain cookie-only media image plumbing for removed media servers', () => {
    for (const file of files) {
      const source = readFileSync(resolve(root, file), 'utf8')
      expect(source.includes('use_cookies'), `${file} must not reference use_cookies`).toBe(false)
    }
  })
})
