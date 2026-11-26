import { existsSync, readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('typography scope', () => {
  it('uses the platform font stack without runtime Google font dependencies', () => {
    const packageJson = JSON.parse(readFileSync('package.json', 'utf-8'))
    const main = readFileSync('src/main.ts', 'utf-8')
    const indexHtml = readFileSync('index.html', 'utf-8')
    const variables = readFileSync('src/@core/scss/libs/vuetify/_variables.scss', 'utf-8')

    expect(packageJson.dependencies).not.toHaveProperty('webfontloader')
    expect(packageJson.devDependencies).not.toHaveProperty('@types/webfontloader')
    expect(main).not.toContain('@/plugins/webfontloader')
    expect(existsSync('src/plugins/webfontloader.ts')).toBe(false)
    expect(indexHtml).not.toContain('fonts.googleapis.com')
    expect(indexHtml).not.toContain('fonts.gstatic.com')
    expect(indexHtml).not.toContain('cdn.jsdelivr.net')

    const fontMarker = '$font-family-custom:'
    const fontStart = variables.indexOf(fontMarker)
    const fontEnd = variables.indexOf(';', fontStart)
    const fontStack = variables.slice(fontStart + fontMarker.length, fontEnd).trim()
    expect(fontStack).toContain('-apple-system')
    expect(fontStack).toContain('BlinkMacSystemFont')
    expect(fontStack).toContain('PingFang SC')
    expect(fontStack.indexOf('-apple-system')).toBeLessThan(fontStack.indexOf('sans-serif'))
    expect(fontStack).not.toContain("'Inter'")
    expect(fontStack).not.toContain("'Noto Sans SC'")
  })
})
