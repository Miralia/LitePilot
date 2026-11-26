import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const source = readFileSync('src/api/types.ts', 'utf-8')

describe('API type scope', () => {
  it('does not retain unreachable upstream contract types', () => {
    for (const typeName of ['DownloadHistory', 'TmdbEpisode', 'CategoryRule', 'CategoryConfig']) {
      expect(source).not.toMatch(new RegExp(`export (interface|type) ${typeName}\\b`))
    }
  })

  it('does not retain backend localization fields that have no producer', () => {
    for (const fieldName of [
      'message_i18n',
      'detail_i18n',
      'text_i18n',
      'name_i18n',
      'provider_i18n',
      'status_i18n',
      'next_run_i18n',
      'progress_text_i18n',
      'error_i18n',
    ]) {
      expect(source).not.toContain(fieldName)
    }
  })
})
