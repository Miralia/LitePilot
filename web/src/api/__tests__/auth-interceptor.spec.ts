import api from '@/api'
import { useAuthStore } from '@/stores/auth'
import { server } from '@tests/support/msw/server'
import { createPinia, setActivePinia } from 'pinia'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const routerPush = vi.hoisted(() => vi.fn())

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

    await expect(api.get('test/unauthorized')).rejects.toMatchObject({
      response: { status: 401 },
    })

    const authStore = useAuthStore()
    expect(authStore.token).toBeNull()
    expect(authStore.originalPath).toBeNull()
    expect(routerPush).toHaveBeenCalledWith('/login')
  })
})
