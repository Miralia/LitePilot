import { existsSync, readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('PWA badge removal boundary', () => {
  it('removes the unused native badge utility while keeping notification-center unread state', () => {
    const app = readFileSync('src/App.vue', 'utf-8')
    const notification = readFileSync('src/layouts/default/components/UserNotification.vue', 'utf-8')

    expect(existsSync('src/utils/badge.ts')).toBe(false)
    expect(app).not.toContain('checkAndEmitUnreadMessages')
    expect(notification).not.toContain('appUnreadMessageCount')
    expect(notification).not.toContain('clearUnreadMessages')
    expect(notification).toContain('hasUnreadNotifications')
    expect(notification).toContain('VBadge v-if="hasUnreadMessageIndicator"')
    expect(notification).toContain('notification-row--unread')
  })
})
