import api from '@/api'
import { useAuthStore, useUserStore } from '@/stores'
import { server } from '@tests/support/msw/server'
import { createPinia, setActivePinia } from 'pinia'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const routerPush = vi.hoisted(() => vi.fn())
const clearUserDataCachesMock = vi.hoisted(() => vi.fn(() => Promise.resolve()))

vi.mock('@/utils/userDataCache', () => ({
  clearUserDataCaches: clearUserDataCachesMock,
}))

vi.mock('@/router', () => ({
  default: {
    push: routerPush,
  },
}))

function mockStatus(path: string, status: number) {
  server.use(
    http.get(new URL(path, 'http://localhost/api/v1/').href, () =>
      HttpResponse.json({ detail: status === 401 ? '认证失效' : '用户权限不足' }, { status }),
    ),
  )
}

describe('API authentication interceptor', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    routerPush.mockClear()
    clearUserDataCachesMock.mockClear()
    const authStore = useAuthStore()
    authStore.login({ token: 'valid-token', remember: false })
    authStore.setOriginalPath('/dashboard')
  })

  it('keeps the session when the server denies access to a resource', async () => {
    mockStatus('test/forbidden', 403)

    await expect(api.get('test/forbidden')).rejects.toMatchObject({
      response: { status: 403 },
    })

    const authStore = useAuthStore()
    expect(authStore.token).toBe('valid-token')
    expect(authStore.originalPath).toBe('/dashboard')
    expect(routerPush).not.toHaveBeenCalled()
  })

  it('clears the session when the server rejects authentication', async () => {
    mockStatus('test/unauthorized', 401)
    useUserStore().loginUser({
      superUser: true,
      userID: 7,
      userName: 'library-admin',
      avatar: 'avatar.jpg',
      level: 2,
      permissions: { admin: true },
      wizard: false,
    })

    await expect(api.get('test/unauthorized')).rejects.toMatchObject({
      response: { status: 401 },
    })

    const authStore = useAuthStore()
    const userStore = useUserStore()
    expect(authStore.token).toBeNull()
    expect(authStore.originalPath).toBeNull()
    expect(userStore.userName).toBe('')
    expect(userStore.avatar).toBe('')
    expect(routerPush).toHaveBeenCalledWith('/login')
  })

  it('waits for user data cache cleanup before redirecting after authentication rejection', async () => {
    mockStatus('test/unauthorized-cleanup', 401)
    let resolveCleanup: (() => void) | undefined
    clearUserDataCachesMock.mockReturnValueOnce(
      new Promise(resolve => {
        resolveCleanup = resolve
      }),
    )

    const rejection = expect(api.get('test/unauthorized-cleanup')).rejects.toMatchObject({
      response: { status: 401 },
    })
    await vi.waitFor(() => expect(clearUserDataCachesMock).toHaveBeenCalledOnce())
    expect(routerPush).not.toHaveBeenCalled()

    resolveCleanup?.()
    await rejection
    expect(routerPush).toHaveBeenCalledWith('/login')
  })
})
