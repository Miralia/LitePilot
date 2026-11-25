import { describe, expect, it } from 'vitest'

import type { MediaInfo } from '@/api/types'
import { getMediaIdentity } from '@/utils/mediaIdentity'

describe('getMediaIdentity legacy source fallback', () => {
  it('prefers active Bangumi identity over legacy Douban when both exist without a declared source', () => {
    expect(getMediaIdentity({ douban_id: '35209731', bangumi_id: 400602 } as MediaInfo)).toEqual({
      mediaId: '400602',
      mediaKey: 'bangumi:400602',
      source: 'bangumi',
    })
  })

  it('keeps Douban-only historical media readable as a legacy identity', () => {
    expect(getMediaIdentity({ douban_id: '35209731' } as MediaInfo)).toEqual({
      mediaId: '35209731',
      mediaKey: 'douban:35209731',
      source: 'douban',
    })
  })
})
