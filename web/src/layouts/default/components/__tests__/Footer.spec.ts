import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { cwd } from 'node:process'
import { describe, expect, it } from 'vitest'

describe('Footer navigation boundaries', () => {
  it('does not link to the removed apps page', () => {
    const source = readFileSync(resolve(cwd(), 'src/layouts/default/components/Footer.vue'), 'utf8')

    expect(source).not.toContain('/apps')
    expect(source).not.toContain("t('nav.more')")
  })
})
