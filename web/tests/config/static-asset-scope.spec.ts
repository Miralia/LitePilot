import { existsSync, readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('static asset scope', () => {
  it('does not ship unreferenced legacy icon variants or precache them by a dead glob', () => {
    const viteConfig = readFileSync('vite.config.ts', 'utf-8')

    expect(existsSync('public/icon.png')).toBe(false)
    expect(existsSync('public/icon-black.png')).toBe(false)
    expect(existsSync('public/icon-white.png')).toBe(false)
    expect(viteConfig.split('\n').map(line => line.trim())).not.toContain("'icon*.png',")
  })

  it('keeps robots.txt as an explicit private-instance crawler boundary', () => {
    expect(readFileSync('public/robots.txt', 'utf-8')).toContain('Disallow: /')
  })
})
