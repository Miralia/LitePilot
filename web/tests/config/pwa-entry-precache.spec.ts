import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const source = readFileSync('vite.config.ts', 'utf-8')

describe('PWA entry precache scope', () => {
  it('uses distinct entry chunk names so lazy chunks are not precached', () => {
    expect(source).toContain("entryFileNames: 'assets/entry-[hash].js'")
    expect(source).toContain("chunkFileNames: 'assets/chunk-[name]-[hash].js'")
    expect(source).toContain("'assets/entry-*.js'")
    expect(source).toContain("'assets/entry-*.css'")
    expect(source).not.toContain("'assets/index-*.js'")
    expect(source).not.toContain("'assets/index-*.css'")
  })
})
