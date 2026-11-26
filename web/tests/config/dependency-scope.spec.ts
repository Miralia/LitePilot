import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('frontend dependency scope', () => {
  it('does not ship the unused VueUse math integration', () => {
    const packageJson = JSON.parse(readFileSync('package.json', 'utf-8'))
    const viteConfig = readFileSync('vite.config.ts', 'utf-8')

    expect(packageJson.dependencies).not.toHaveProperty('@vueuse/math')
    expect(viteConfig).not.toContain('@vueuse/math')
  })
})
