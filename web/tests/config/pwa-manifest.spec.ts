import { existsSync, readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const source = readFileSync('vite.config.ts', 'utf-8')

describe('PWA manifest scope', () => {
  it('only exposes shortcuts for routes that exist in the hash router', () => {
    expect(source).toContain("'url': './#/dashboard'")
    expect(source).toContain("'url': './#/history'")
    expect(source).toContain("'url': './#/filemanager'")
    expect(source).not.toContain("'url': './recommend'")
    expect(source).not.toContain("'url': './discover'")
    expect(source).not.toContain("'url': './apps'")
  })

  it('does not ship orphaned legacy shortcut icons', () => {
    for (const file of [
      'public/sparkles-icon-192x192.png',
      'public/clock-icon-192x192.png',
      'public/cog-icon-192x192.png',
      'public/user-icon-192x192.png',
    ]) {
      expect(existsSync(file)).toBe(false)
    }
  })

  it('does not advertise application icons as screenshots', () => {
    expect(source).not.toContain("'screenshots'")
  })

  it('does not register an unimplemented legacy protocol handler', () => {
    expect(source).not.toContain('protocol_handlers')
    expect(source).not.toContain('web+moviepilot')
  })
})
