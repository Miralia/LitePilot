import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('frontend dependency scope', () => {
  it('does not ship the unused VueUse math integration', () => {
    const packageJson = JSON.parse(readFileSync('package.json', 'utf-8'))
    const viteConfig = readFileSync('vite.config.ts', 'utf-8')

    expect(packageJson.dependencies).not.toHaveProperty('@vueuse/math')
    expect(viteConfig).not.toContain('@vueuse/math')
  })

  it('does not ship the never-started NProgress integration', () => {
    const packageJson = JSON.parse(readFileSync('package.json', 'utf-8'))
    const router = readFileSync('src/router/index.ts', 'utf-8')
    const styles = readFileSync('src/styles/common.scss', 'utf-8')

    expect(packageJson.dependencies).not.toHaveProperty('nprogress')
    expect(packageJson.devDependencies).not.toHaveProperty('@types/nprogress')
    expect(router).not.toContain('NProgress')
    expect(styles).not.toContain('#nprogress')
  })
})
