import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('preload error recovery entry boundary', () => {
  it('installs the recovery listener before the router resolves lazy routes', () => {
    const main = readFileSync('src/main.ts', 'utf-8')

    expect(main).toContain("import { installPreloadErrorRecovery } from '@/utils/preloadErrorRecovery'")
    expect(main.indexOf('installPreloadErrorRecovery()')).toBeGreaterThan(-1)
    expect(main.indexOf('installPreloadErrorRecovery()')).toBeLessThan(main.indexOf('app.use(router)'))
  })
})
