import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const source = readFileSync('src/plugins/vuetify/index.ts', 'utf-8')
const controls = [
  'VAutocomplete',
  'VCheckbox',
  'VCombobox',
  'VRadioGroup',
  'VSelect',
  'VSlider',
  'VSwitch',
  'VTextarea',
  'VTextField',
]

describe('vuetify responsive input loading', () => {
  it('keeps non-login form controls out of the entry dependency graph', () => {
    for (const control of controls) {
      expect(source).not.toContain(`import { ${control} } from 'vuetify/components/${control}'`)
      expect(source).toContain(`import('vuetify/components/${control}')`)
    }
  })
})
