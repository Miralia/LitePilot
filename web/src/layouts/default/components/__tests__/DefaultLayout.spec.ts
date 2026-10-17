import DefaultLayout from '@/layouts/default/components/DefaultLayout.vue'
import { THEME_CUSTOMIZER_CHANGE_EVENT, THEME_CUSTOMIZER_OPEN_EVENT } from '@/composables/useThemeCustomizer'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

interface UserStoreMock {
  permissions: Record<string, unknown>
  superUser: boolean
}

const mocks = vi.hoisted(() => ({
  emptyComponent: { template: '<div><slot /></div>' },
  navLink: {
    name: 'VerticalNavLink',
    props: ['item'],
    template: '<span data-testid="vertical-nav-link">{{ item.title }}</span>',
  },
  userStore: undefined as UserStoreMock | undefined,
  verticalNavLayout: { template: '<div><slot name="vertical-nav-content" /></div>' },
}))

vi.mock('@layouts/components/VerticalNavLayout.vue', () => ({ default: mocks.verticalNavLayout }))
vi.mock('@layouts/components/VerticalNavLink.vue', () => ({ default: mocks.navLink }))
vi.mock('@layouts/components/VerticalNavSectionTitle.vue', () => ({ default: mocks.emptyComponent }))
vi.mock('@/components/misc/ThemeLogoMark.vue', () => ({ default: mocks.emptyComponent }))
vi.mock('@/components/theme/ThemeCustomizer.vue', () => ({ default: mocks.emptyComponent }))
vi.mock('@/layouts/default/components/Footer.vue', () => ({ default: mocks.emptyComponent }))
vi.mock('@/layouts/default/components/HeaderTab.vue', () => ({ default: mocks.emptyComponent }))
vi.mock('@/layouts/default/components/OfflinePage.vue', () => ({ default: mocks.emptyComponent }))
vi.mock('@/layouts/default/components/ShortcutBar.vue', () => ({ default: mocks.emptyComponent }))
vi.mock('@/layouts/default/components/UserNotification.vue', () => ({ default: mocks.emptyComponent }))
vi.mock('@/layouts/default/components/UserProfile.vue', () => ({ default: mocks.emptyComponent }))

vi.mock('@/stores', async () => {
  const { reactive } = await import('vue')
  mocks.userStore = reactive({
    permissions: {
      admin: true,
      features: {},
      manage: true,
    },
    superUser: true,
  })

  return {
    useGlobalSettingsStore: () => ({ get: vi.fn(() => true) }),
    useUserStore: () => mocks.userStore,
  }
})

vi.mock('@/router/i18n-menu', () => ({
  getNavMenus: () => [{ header: 'menu.start', title: 'Built-in dashboard', to: '/dashboard' }],
}))
vi.mock('@/composables/useOfflineStatus', () => ({
  useGlobalOfflineStatus: () => ({ isOffline: { value: false } }),
}))
vi.mock('@/composables/usePWA', () => ({ usePWA: () => ({ appMode: { value: false } }) }))
vi.mock('vue-i18n', async importOriginal => ({
  ...(await importOriginal<typeof import('vue-i18n')>()),
  useI18n: () => ({ t: (key: string) => key }),
}))
vi.mock('vue-router', async importOriginal => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRoute: () => ({ path: '/' }),
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('vuetify', async importOriginal => ({
  ...(await importOriginal<typeof import('vuetify')>()),
  useDisplay: () => ({ mdAndDown: { value: false } }),
}))

describe('DefaultLayout', () => {
  it('渲染内置菜单并在卸载时移除主题定制器监听', async () => {
    const addEventListener = vi.spyOn(window, 'addEventListener')
    const removeEventListener = vi.spyOn(window, 'removeEventListener')
    const wrapper = shallowMount(DefaultLayout, {
      global: {
        renderStubDefaultSlot: true,
        stubs: {
          IconBtn: mocks.emptyComponent,
          RouterLink: mocks.emptyComponent,
          VerticalNavLayout: mocks.verticalNavLayout,
          VerticalNavLink: mocks.navLink,
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Built-in dashboard')

    const changeHandler = addEventListener.mock.calls.find(
      ([event]) => String(event) === THEME_CUSTOMIZER_CHANGE_EVENT,
    )?.[1]
    const openHandler = addEventListener.mock.calls.find(
      ([event]) => String(event) === THEME_CUSTOMIZER_OPEN_EVENT,
    )?.[1]

    expect(changeHandler).toBeTypeOf('function')
    expect(openHandler).toBeTypeOf('function')

    wrapper.unmount()

    expect(removeEventListener).toHaveBeenCalledWith(THEME_CUSTOMIZER_CHANGE_EVENT, changeHandler)
    expect(removeEventListener).toHaveBeenCalledWith(THEME_CUSTOMIZER_OPEN_EVENT, openHandler)
  })
})
