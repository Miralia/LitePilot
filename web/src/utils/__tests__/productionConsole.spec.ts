import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { cwd } from 'node:process'
import { describe, expect, it } from 'vitest'

const quietProductionFiles = [
  'src/composables/useStateRestore.ts',
  'src/composables/useVersionChecker.ts',
  'src/plugins/stateRestore.ts',
  'src/service-worker.ts',
  'src/utils/appDeepLink.ts',
  'src/utils/backgroundManager.ts',
  'src/utils/requestOptimizer.ts',
  'src/views/reorganize/TransferHistoryView.vue',
]

describe('production console output', () => {
  it.each(quietProductionFiles)('keeps %s free of debug console.log output', file => {
    const source = readFileSync(resolve(cwd(), file), 'utf8')

    expect(source).not.toMatch(/console\.log\(/)
  })

  it('does not expose deep-link internals in console output', () => {
    const source = readFileSync(resolve(cwd(), 'src/utils/appDeepLink.ts'), 'utf8')

    expect(source).not.toMatch(/console\.(?:log|info|debug)\(/)
    expect(source).not.toContain('originalUrl: playUrl')
    expect(source).not.toContain('deepLinkUrl: appUrl')
  })
})
