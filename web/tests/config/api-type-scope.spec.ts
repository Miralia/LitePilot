import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const source = readFileSync('src/api/types.ts', 'utf-8')

describe('API type scope', () => {
  it('does not retain unreachable upstream contract types', () => {
    for (const typeName of ['DownloadHistory', 'TmdbEpisode', 'CategoryRule', 'CategoryConfig']) {
      expect(source).not.toMatch(new RegExp(`export (interface|type) ${typeName}\\b`))
    }
  })
})
