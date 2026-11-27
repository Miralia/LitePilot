import { usePWAInstall } from '@/composables/usePWAInstall'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'

function createMediaQueryList(media: string): MediaQueryList {
  return {
    addEventListener: vi.fn(),
    addListener: vi.fn(),
    dispatchEvent: vi.fn(),
    matches: false,
    media,
    onchange: null,
    removeEventListener: vi.fn(),
    removeListener: vi.fn(),
  } as unknown as MediaQueryList
}

describe('usePWAInstall', () => {
  it('卸载时移除 display-mode 监听', () => {
    const queries = new Map<string, MediaQueryList>()
    vi.spyOn(window, 'matchMedia').mockImplementation(query => {
      if (!queries.has(query)) queries.set(query, createMediaQueryList(query))
      return queries.get(query) as MediaQueryList
    })
    const Harness = defineComponent({
      setup() {
        usePWAInstall()
        return () => h('div')
      },
    })

    const wrapper = mount(Harness)
    const standaloneQuery = queries.get('(display-mode: standalone)') as MediaQueryList
    const addListener = vi.mocked(standaloneQuery.addEventListener)
    const changeHandler = addListener.mock.calls.find(([event]) => event === 'change')?.[1]
    expect(changeHandler).toBeTypeOf('function')

    wrapper.unmount()

    expect(standaloneQuery.removeEventListener).toHaveBeenCalledWith('change', changeHandler)
  })
})
