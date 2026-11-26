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

  it('loads colorthief only when dominant color extraction runs', () => {
    const imageUtils = readFileSync('src/@core/utils/image.ts', 'utf-8')

    expect(imageUtils).not.toContain("from 'colorthief'")
    expect(imageUtils).toContain("await import('colorthief')")
  })

  it('uses native scrolling instead of the perfect-scrollbar integration', () => {
    const packageJson = JSON.parse(readFileSync('package.json', 'utf-8'))
    const main = readFileSync('src/main.ts', 'utf-8')
    const styles = readFileSync('src/styles/main.scss', 'utf-8')
    const verticalNav = readFileSync('src/@layouts/components/VerticalNav.vue', 'utf-8')

    expect(packageJson.dependencies).not.toHaveProperty('vue3-perfect-scrollbar')
    expect(main).not.toContain('PerfectScrollbarPlugin')
    expect(styles).not.toContain('vue3-perfect-scrollbar')
    expect(verticalNav).not.toContain('PerfectScrollbar')
  })
})
