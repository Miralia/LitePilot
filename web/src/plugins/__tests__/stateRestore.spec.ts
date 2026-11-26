import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { stateRestore } from '@/plugins/stateRestore'

describe('tab state restore', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T00:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('saves and restores the active tab for the same route', () => {
    stateRestore.tab.saveTabState('/setting', 'system')
    stateRestore.tab.saveTabState('/history', 'transfer')

    expect(stateRestore.tab.getTabState('/setting')).toBe('system')
    expect(stateRestore.tab.getTabState('/history')).toBe('transfer')
  })

  it('expires saved tabs after one hour', () => {
    stateRestore.tab.saveTabState('/setting', 'system')

    vi.setSystemTime(new Date('2026-01-01T01:00:01Z'))

    expect(stateRestore.tab.getTabState('/setting')).toBeNull()
  })
})
