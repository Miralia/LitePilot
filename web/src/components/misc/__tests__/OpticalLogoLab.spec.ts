import { shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import OpticalLogoLab from '@/components/misc/OpticalLogoLab.vue'
import source from '@/components/misc/OpticalLogoLab.vue?raw'

const runtimeModuleFactories = vi.hoisted(() => ({
  gsap: vi.fn(),
  three: vi.fn(),
}))

vi.mock('three', () => {
  runtimeModuleFactories.three()

  return {}
})

vi.mock('gsap', () => {
  runtimeModuleFactories.gsap()

  return {
    gsap: {
      ticker: { add: vi.fn(), remove: vi.fn() },
      timeline: vi.fn(),
      to: vi.fn(),
    },
  }
})

const routeState = vi.hoisted(() => ({ path: '/login', query: {} as Record<string, string> }))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
}))

vi.mock('@/composables/useThemeCustomizer', () => ({
  THEME_CUSTOMIZER_CHANGE_EVENT: 'litepilot-theme-customizer-change',
}))

vi.mock('vuetify', async importOriginal => {
  const actual = await importOriginal<typeof import('vuetify')>()

  return {
    ...actual,
    useTheme: () => ({
      global: {
        current: {
          value: {
            colors: {
              primary: '#0a84ff',
              'on-surface': '#1d1d1f',
            },
            dark: false,
          },
        },
        name: { value: 'light' },
      },
    }),
  }
})

function installAnimationFrameStub() {
  const callbacks = new Map<number, FrameRequestCallback>()
  let nextId = 0

  vi.spyOn(window, 'requestAnimationFrame').mockImplementation(callback => {
    nextId += 1
    callbacks.set(nextId, callback)

    return nextId
  })
  vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(handle => {
    callbacks.delete(handle)
  })

  return {
    flush() {
      const pending = [...callbacks.values()]
      callbacks.clear()
      pending.forEach(callback => callback(performance.now()))
    },
    size: () => callbacks.size,
  }
}

function mountLab() {
  return shallowMount(OpticalLogoLab, {
    props: { locale: 'zh-CN' },
    global: {
      stubs: {
        PrismaticLogo: true,
        VIcon: true,
        VSlider: true,
        VTooltip: {
          template: '<div><slot name="activator" :props="{}" /></div>',
        },
      },
    },
  })
}

describe('OpticalLogoLab', () => {
  afterEach(() => {
    routeState.query = {}
    Reflect.deleteProperty(window, 'requestIdleCallback')
    Reflect.deleteProperty(window, 'cancelIdleCallback')
  })

  it('keeps the static logo visible while the optical runtime is loading', () => {
    expect(source).toContain('.optical-logo-lab--loading .optical-logo-lab__fallback')
  })

  it('does not load the WebGL runtime for a persisted prismatic logo', async () => {
    const frames = installAnimationFrameStub()
    const idleCallbacks = new Map<number, IdleRequestCallback>()
    let nextIdleId = 0
    Object.defineProperty(window, 'requestIdleCallback', {
      configurable: true,
      value: vi.fn((callback: IdleRequestCallback) => {
        nextIdleId += 1
        idleCallbacks.set(nextIdleId, callback)

        return nextIdleId
      }),
    })
    localStorage.setItem(
      'moviepilot-optical-logo-lab-v2',
      JSON.stringify({
        bag: [],
        lastCombination: 'prismatic:none',
        lightIntensity: 45,
        logoSize: 112,
        pinned: true,
        pinnedCombination: 'prismatic:none',
        soundEnabled: false,
        staticMotion: 'steady',
        unifiedThemeFamily: true,
        version: 2,
      }),
    )

    const wrapper = mountLab()
    await nextTick()
    await nextTick()
    frames.flush()
    frames.flush()
    idleCallbacks.forEach(callback => callback({ didTimeout: false, timeRemaining: () => 20 }))
    await nextTick()
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(wrapper.classes()).toContain('optical-logo-lab--prismatic')
    expect(runtimeModuleFactories.three).not.toHaveBeenCalled()
    expect(runtimeModuleFactories.gsap).not.toHaveBeenCalled()
  })

  it('starts the WebGL runtime when a prismatic user selects a WebGL material', async () => {
    const frames = installAnimationFrameStub()
    const idleCallbacks = new Map<number, IdleRequestCallback>()
    let nextIdleId = 0
    Object.defineProperty(window, 'requestIdleCallback', {
      configurable: true,
      value: vi.fn((callback: IdleRequestCallback) => {
        nextIdleId += 1
        idleCallbacks.set(nextIdleId, callback)

        return nextIdleId
      }),
    })
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    localStorage.setItem(
      'moviepilot-optical-logo-lab-v2',
      JSON.stringify({
        bag: [],
        lastCombination: 'prismatic:none',
        lightIntensity: 45,
        logoSize: 112,
        pinned: true,
        pinnedCombination: 'prismatic:none',
        soundEnabled: false,
        staticMotion: 'steady',
        unifiedThemeFamily: true,
        version: 2,
      }),
    )
    routeState.query = { lab: '1' }

    const wrapper = mountLab()
    await nextTick()
    await nextTick()
    frames.flush()
    frames.flush()
    idleCallbacks.forEach(callback => callback({ didTimeout: false, timeRemaining: () => 20 }))
    await nextTick()

    const crystalButton = wrapper.find('[data-material="crystal"]')
    expect(crystalButton.attributes('disabled')).toBeUndefined()
    await crystalButton.trigger('click')

    expect(wrapper.classes()).toContain('optical-logo-lab--crystal')
    expect(wrapper.classes()).toContain('optical-logo-lab--loading')
    await vi.waitFor(() => expect(wrapper.classes()).toContain('optical-logo-lab--fallback'))
  })

  it('defers the heavy runtime until browser idle after first paint', async () => {
    const frames = installAnimationFrameStub()
    const idleCallbacks = new Map<number, IdleRequestCallback>()
    let nextIdleId = 0
    const requestIdleCallback = vi.fn((callback: IdleRequestCallback) => {
      nextIdleId += 1
      idleCallbacks.set(nextIdleId, callback)

      return nextIdleId
    })
    Object.defineProperty(window, 'requestIdleCallback', {
      configurable: true,
      value: requestIdleCallback,
    })

    mountLab()
    await nextTick()
    await nextTick()

    expect(frames.size()).toBe(1)
    frames.flush()
    expect(frames.size()).toBe(1)
    frames.flush()

    expect(requestIdleCallback).toHaveBeenCalledTimes(1)
  })
})
