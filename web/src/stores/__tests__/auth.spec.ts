import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/stores/auth'
import { clearUserDataCaches } from '@/utils/userDataCache'

vi.mock('@/utils/userDataCache', () => ({
  clearUserDataCaches: vi.fn(() => Promise.resolve()),
}))

describe('auth store', () => {
  beforeEach(() => {
    vi.mocked(clearUserDataCaches).mockClear()
    setActivePinia(createPinia())
  })

  it('starts with the unauthenticated state and matching getters', () => {
    const authStore = useAuthStore()

    expect(authStore.$state).toEqual({ token: null, remember: false, originalPath: null })
    expect(authStore.getToken).toBeNull()
    expect(authStore.getRemember).toBe(false)
    expect(authStore.getOriginalPath).toBeNull()
  })

  it('logs in and updates independent authentication fields', () => {
    const authStore = useAuthStore()

    authStore.setOriginalPath('/recommend')
    authStore.login({ token: 'test-token', remember: true, originalPath: '/ignored' })

    expect(authStore.token).toBe('test-token')
    expect(authStore.remember).toBe(true)
    expect(authStore.originalPath).toBe('/recommend')

    authStore.setRemember(false)
    authStore.clearToken()
    expect(authStore.getRemember).toBe(false)
    expect(authStore.getToken).toBeNull()
  })

  it('logs out and clears authentication state', async () => {
    const authStore = useAuthStore()

    authStore.login({ token: 'test-token', remember: true })
    authStore.setOriginalPath('/history')

    await authStore.logout()

    expect(authStore.token).toBeNull()
    expect(authStore.originalPath).toBeNull()
    expect(authStore.remember).toBe(true)
    expect(clearUserDataCaches).toHaveBeenCalledOnce()
  })

  it('returns a promise that settles after user data cache cleanup', async () => {
    const authStore = useAuthStore()
    let resolveCleanup: (() => void) | undefined
    vi.mocked(clearUserDataCaches).mockReturnValueOnce(
      new Promise(resolve => {
        resolveCleanup = resolve
      }),
    )

    const logoutPromise = authStore.logout()
    let settled = false
    void logoutPromise.then(() => {
      settled = true
    })

    expect(authStore.token).toBeNull()
    await Promise.resolve()
    expect(settled).toBe(false)

    resolveCleanup?.()
    await logoutPromise
    expect(settled).toBe(true)
  })
})
