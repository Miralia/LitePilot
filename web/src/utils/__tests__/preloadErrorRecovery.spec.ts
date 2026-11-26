import { describe, expect, it, vi } from 'vitest'

import {
  installPreloadErrorRecovery,
  PRELOAD_ERROR_RELOAD_COOLDOWN_MS,
  PRELOAD_ERROR_RELOAD_KEY,
} from '../preloadErrorRecovery'

function createStorage() {
  const values = new Map<string, string>()
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
  }
}

function dispatchPreloadError(target: EventTarget) {
  const event = new Event('vite:preloadError', { cancelable: true })
  target.dispatchEvent(event)
  return event
}

describe('preload error recovery', () => {
  it('reloads once when an online client cannot load a lazy chunk', () => {
    const target = new EventTarget()
    const reload = vi.fn()
    installPreloadErrorRecovery({
      target,
      storage: createStorage(),
      isOnline: () => true,
      now: () => 100_000,
      reload,
    })

    const event = dispatchPreloadError(target)

    expect(event.defaultPrevented).toBe(true)
    expect(reload).toHaveBeenCalledOnce()
  })

  it('does not reload offline because a refresh cannot fetch missing chunks', () => {
    const target = new EventTarget()
    const reload = vi.fn()
    installPreloadErrorRecovery({
      target,
      storage: createStorage(),
      isOnline: () => false,
      now: () => 100_000,
      reload,
    })

    const event = dispatchPreloadError(target)

    expect(event.defaultPrevented).toBe(false)
    expect(reload).not.toHaveBeenCalled()
  })

  it('uses a cooldown to prevent reload loops after a failed recovery', () => {
    const target = new EventTarget()
    const reload = vi.fn()
    const storage = createStorage()
    installPreloadErrorRecovery({
      target,
      storage,
      isOnline: () => true,
      now: () => 100_000,
      reload,
    })

    dispatchPreloadError(target)
    const secondEvent = dispatchPreloadError(target)

    expect(reload).toHaveBeenCalledOnce()
    expect(secondEvent.defaultPrevented).toBe(false)

    storage.setItem(PRELOAD_ERROR_RELOAD_KEY, String(100_000 - PRELOAD_ERROR_RELOAD_COOLDOWN_MS))
    dispatchPreloadError(target)
    expect(reload).toHaveBeenCalledTimes(2)
  })

  it('removes the listener when the recovery hook is disposed', () => {
    const target = new EventTarget()
    const reload = vi.fn()
    const dispose = installPreloadErrorRecovery({
      target,
      storage: createStorage(),
      isOnline: () => true,
      now: () => 100_000,
      reload,
    })

    dispose()
    dispatchPreloadError(target)

    expect(reload).not.toHaveBeenCalled()
  })
})
