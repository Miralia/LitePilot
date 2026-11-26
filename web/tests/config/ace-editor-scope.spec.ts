import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

const source = readFileSync('src/ace-config.ts', 'utf8')

describe('ace editor asset scope', () => {
  it('only registers generic modes that have active editors', () => {
    for (const mode of ['json', 'javascript', 'html', 'yaml', 'ini']) {
      expect(source).not.toContain(`ace/mode/${mode}'`)
      expect(source).not.toContain(`mode-${mode}?url`)
      expect(source).not.toContain(`worker-${mode}?url`)
    }

    expect(source).toContain("ace.config.setModuleUrl('ace/mode/css', modeCssUrl)")
  })

  it('does not distribute autocomplete assets when no editor enables autocomplete', () => {
    expect(source).not.toContain('ext-language_tools')
    expect(source).not.toContain('ace/snippets/')
    expect(source).not.toContain('snippets/')
  })

  it('only registers themes used by the application shell', () => {
    for (const theme of ['github', 'chrome', 'monokai']) {
      expect(source).not.toContain(`ace/theme/${theme}'`)
      expect(source).not.toContain(`theme-${theme}?url`)
    }

    expect(source).toContain("ace.config.setModuleUrl('ace/theme/github_dark', themeGithubDarkUrl)")
    expect(source).toContain("ace.config.setModuleUrl('ace/theme/github_light_default', themeGithubLightDefaultUrl)")
  })
})
