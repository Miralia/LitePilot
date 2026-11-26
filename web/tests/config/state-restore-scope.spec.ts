import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('state restore scope', () => {
  it('keeps only the consumed tab state restore path', () => {
    const plugin = readFileSync('src/plugins/stateRestore.ts', 'utf-8')
    const composable = readFileSync('src/composables/useStateRestore.ts', 'utf-8')

    expect(plugin).toContain('TabStateManager')
    expect(plugin).toContain('pwa-active-tabs')
    expect(composable).toContain('useTabStateRestore')

    expect(plugin).not.toContain('RouteStateManager')
    expect(plugin).not.toContain('pwa-current-route')
    expect(plugin).not.toContain('pwa-state-restore')
    expect(plugin).not.toContain("window.addEventListener('popstate'")
    expect(composable).not.toContain('useRouteStateRestore')
    expect(composable).not.toContain('usePageStateRestore')
  })
})
