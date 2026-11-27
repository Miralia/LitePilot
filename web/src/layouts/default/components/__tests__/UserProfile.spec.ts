import UserProfile from '@/layouts/default/components/UserProfile.vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  applyTransparency: vi.fn(),
  createConfirm: vi.fn(),
  logout: vi.fn(),
  openSharedDialog: vi.fn(),
  readThemeCustomizerSettings: vi.fn(),
  routerPush: vi.fn(),
  saveLocalTheme: vi.fn(),
  setTheme: vi.fn(),
  setUIMode: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
  userReset: vi.fn(),
}))

vi.mock('@/api', () => ({
  default: {
    get: mocks.apiGet,
    post: mocks.apiPost,
  },
}))

vi.mock('@/router', () => ({
  default: { push: mocks.routerPush },
}))

vi.mock('vue-toastification', () => ({
  useToast: () => ({
    error: mocks.toastError,
    success: mocks.toastSuccess,
  }),
}))

vi.mock('@/stores', () => ({
  useAuthStore: () => ({ logout: mocks.logout }),
  useUserStore: () => ({
    avatar: '',
    permissions: {},
    reset: mocks.userReset,
    superUser: false,
    userName: 'user',
  }),
}))

vi.mock('vue-i18n', async importOriginal => ({
  ...(await importOriginal<typeof import('vue-i18n')>()),
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('vuetify', async importOriginal => {
  const actual = await importOriginal<typeof import('vuetify')>()
  const { ref } = await import('vue')
  return {
    ...actual,
    useTheme: () => ({
      global: {
        current: ref({ dark: false }),
        name: ref('light'),
      },
    }),
  }
})

vi.mock('@/composables/usePWA', async () => {
  const { ref } = await import('vue')
  return {
    usePWA: () => ({
      appMode: ref(false),
      setUIMode: mocks.setUIMode,
      uiMode: ref('auto'),
    }),
  }
})

vi.mock('@/composables/useConfirm', () => ({
  useConfirm: () => ({ createConfirm: mocks.createConfirm }),
}))

vi.mock('@/composables/useSharedDialog', () => ({
  openSharedDialog: mocks.openSharedDialog,
}))

vi.mock('@/composables/useTransparencySettings', () => ({
  applyStoredTransparencySettings: mocks.applyTransparency,
}))

vi.mock('@/utils/themeManager', () => ({
  themeManager: { setTheme: mocks.setTheme },
}))

vi.mock('@/@core/utils', () => ({
  checkPrefersColorSchemeIsDark: () => false,
}))

vi.mock('@/@core/utils/theme', () => ({
  saveLocalTheme: mocks.saveLocalTheme,
}))

vi.mock('@/composables/useThemeCustomizer', () => ({
  THEME_CUSTOMIZER_CHANGE_EVENT: 'litepilot-theme-customizer-change',
  THEME_CUSTOMIZER_OPEN_EVENT: 'litepilot-theme-customizer-open',
  persistPartialThemeCustomizerSettings: vi.fn(),
  readThemeCustomizerSettings: mocks.readThemeCustomizerSettings,
}))

describe('UserProfile', () => {
  it('卸载时移除系统主题变化监听', async () => {
    const mediaQueryList = {
      addEventListener: vi.fn(),
      addListener: vi.fn(),
      dispatchEvent: vi.fn(),
      matches: false,
      media: '(prefers-color-scheme: dark)',
      onchange: null,
      removeEventListener: vi.fn(),
      removeListener: vi.fn(),
    } as unknown as MediaQueryList
    vi.spyOn(window, 'matchMedia').mockImplementation(query => (
      query === '(prefers-color-scheme: dark)'
        ? mediaQueryList
        : {
            ...mediaQueryList,
            media: query,
          }
    ))
    mocks.apiGet.mockResolvedValue({ is_otp: false })
    mocks.readThemeCustomizerSettings.mockReturnValue({ layout: 'vertical', theme: 'light' })

    const wrapper = shallowMount(UserProfile)
    await flushPromises()

    const addListener = vi.mocked(mediaQueryList.addEventListener)
    const changeHandler = addListener.mock.calls.find(([event]) => event === 'change')?.[1]
    expect(changeHandler).toBeTypeOf('function')

    wrapper.unmount()

    expect(mediaQueryList.removeEventListener).toHaveBeenCalledWith('change', changeHandler)
  })
})
