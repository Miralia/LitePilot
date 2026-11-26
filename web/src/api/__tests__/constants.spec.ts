import { describe, expect, it } from 'vitest'
import * as apiConstants from '@/api/constants'
import { storageAttributes, storageRemoteDict } from '@/api/constants'

describe('storage constants boundary', () => {
  it('only exposes the active local and SMB storage types', () => {
    expect(storageAttributes.map(item => item.type)).toEqual(['local', 'smb'])
    expect(storageRemoteDict).toEqual({
      local: false,
      smb: true,
    })
  })

  it('does not expose removed cloud or custom storage types', () => {
    for (const type of ['alipan', 'u115', 'rclone', 'alist', 'alistgo', 'custom']) {
      expect(storageAttributes.some(item => item.type === type)).toBe(false)
    }
  })
})
it('does not expose notification option internals as public API', () => {
  expect('notificationSwitchOptions' in apiConstants).toBe(false)
  expect(apiConstants.notificationSwitchDict['整理入库']).toBeTruthy()
})
