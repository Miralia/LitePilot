import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('product branding', () => {
  it('uses the LitePilot name in primary navigation without the upstream v2 marker', () => {
    const verticalNav = readFileSync('src/@layouts/components/VerticalNav.vue', 'utf-8')
    const defaultLayout = readFileSync('src/layouts/default/components/DefaultLayout.vue', 'utf-8')

    expect(verticalNav).toContain('>LitePilot<')
    expect(verticalNav).not.toContain('>MOVIEPILOT<')
    expect(verticalNav).not.toContain('>v2<')
    expect(defaultLayout).toContain('>LitePilot<')
    expect(defaultLayout).not.toContain('>MOVIEPILOT<')
  })
})
