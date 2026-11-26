import { mount } from '@vue/test-utils'
import { defineComponent, h, resolveComponent } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import vuetify from '@/plugins/vuetify'

const Host = defineComponent({
  setup() {
    return () => h(resolveComponent('VTextField'), { label: '名称', modelValue: 'LitePilot' })
  },
})

describe('async responsive inputs', () => {
  it('resolves a globally registered input to the real vuetify control', async () => {
    const wrapper = mount(Host, {
      global: {
        plugins: [vuetify],
      },
    })

    await vi.waitFor(
      () => {
        expect(wrapper.find('input').exists()).toBe(true)
      },
      { interval: 20, timeout: 3000 },
    )

    expect(wrapper.text()).toContain('名称')
  })
})
