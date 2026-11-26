import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { cwd } from 'node:process'
import { describe, expect, it } from 'vitest'

describe('index.html accessibility', () => {
  it('does not disable pinch zoom or lock the viewport scale', () => {
    const source = readFileSync(resolve(cwd(), 'index.html'), 'utf8')
    const viewportTag = source.match(/<meta\b[^>]*\bname="viewport"[^>]*>/)?.[0] ?? ''
    const viewport = viewportTag.match(/\bcontent="([^"]*)"/)?.[1] ?? ''

    expect(viewportTag).not.toBe('')
    expect(viewport).not.toBe('')
    expect(viewport).not.toContain('user-scalable=no')
    expect(viewport).not.toContain('maximum-scale')
    expect(viewport).not.toContain('minimum-scale')
  })
})
