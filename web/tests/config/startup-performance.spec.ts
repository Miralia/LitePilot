import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('startup performance', () => {
  it('does not start noncritical preloads immediately when idle callbacks are unavailable', () => {
    const main = readFileSync('src/main.ts', 'utf-8')

    expect(main).not.toContain('globalThis.setTimeout(callback, 0)')
    expect(main).toContain('globalThis.setTimeout(callback, 1200)')
  })
})
