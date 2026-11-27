import AccountSettingSystem from '@/views/setting/AccountSettingSystem.vue'
import { fireEvent, screen, waitFor, within } from '@testing-library/vue'
import { flushPromises } from '@vue/test-utils'
import { renderWithProviders } from '@tests/support/render'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  toastError: vi.fn(),
  toastInfo: vi.fn(),
  toastSuccess: vi.fn(),
}))

vi.mock('@/api', () => ({
  default: {
    get: mocks.apiGet,
    post: mocks.apiPost,
  },
}))

vi.mock('vue-toastification', () => ({
  useToast: () => ({
    error: mocks.toastError,
    info: mocks.toastInfo,
    success: mocks.toastSuccess,
  }),
}))

vi.mock('@/composables/useSilentSettingRefresh', () => ({
  useSilentSettingRefresh: vi.fn(),
}))

vi.mock('@/components/misc/BuiltinFeatureSettings.vue', async () => {
  const { defineComponent } = await import('vue')
  return { default: defineComponent({ name: 'BuiltinFeatureSettingsStub', template: '<div />' }) }
})

vi.mock('@/components/cards/DownloaderCard.vue', async () => {
  const { defineComponent } = await import('vue')
  return { default: defineComponent({ name: 'DownloaderCardStub', template: '<div />' }) }
})

vi.mock('@/components/cards/MediaServerCard.vue', async () => {
  const { defineComponent } = await import('vue')
  return { default: defineComponent({ name: 'MediaServerCardStub', template: '<div />' }) }
})

vi.mock('vuedraggable', async () => {
  const { defineComponent, h } = await import('vue')

  return {
    default: defineComponent({
      name: 'DraggableStub',
      setup(_props, { slots }) {
        return () => h('div', slots.default?.())
      },
    }),
  }
})

function mockSettings() {
  mocks.apiGet.mockImplementation((endpoint: string) => {
    if (endpoint === 'system/setting/Downloaders') return { data: { value: [] } }
    if (endpoint === 'system/setting/MediaServers') return { data: { value: [] } }
    if (endpoint === 'system/setting/ScrapingSwitchs') return { data: { value: {} }, success: true }
    if (endpoint === 'system/env') return { data: {}, success: true }
    throw new Error(`Unexpected GET ${endpoint}`)
  })
  mocks.apiPost.mockResolvedValue({ success: true })
}

async function clickSaveInCard(cardTitle: string) {
  const card = screen.getByText(cardTitle, { selector: '.v-card-title' }).closest('.v-card')
  expect(card).not.toBeNull()
  await fireEvent.click(within(card as HTMLElement).getByRole('button', { name: '保存' }))
}

describe('system settings save feedback', () => {
  beforeEach(() => {
    mocks.apiGet.mockReset()
    mocks.apiPost.mockReset()
    mocks.toastError.mockReset()
    mocks.toastInfo.mockReset()
    mocks.toastSuccess.mockReset()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it.each([
    ['基础设置', 'system/env', '设置保存失败：network failed！'],
    ['下载器', 'system/setting/Downloaders', '下载器设置保存失败！'],
    ['媒体服务器', 'system/setting/MediaServers', '媒体服务器设置保存失败！'],
  ])('reports network failures when saving %s', async (cardTitle, endpoint, message) => {
    mockSettings()
    mocks.apiPost.mockImplementation((calledEndpoint: string) => {
      if (calledEndpoint === endpoint) return Promise.reject(new Error('network failed'))
      return Promise.resolve({ success: true })
    })
    await renderWithProviders(AccountSettingSystem)

    await clickSaveInCard(cardTitle)

    await waitFor(() => expect(mocks.toastError).toHaveBeenCalledWith(message))
    expect(mocks.toastSuccess).not.toHaveBeenCalled()
  })

  it.each([
    ['基础设置', 'system/env'],
    ['下载器', 'system/setting/Downloaders'],
    ['媒体服务器', 'system/setting/MediaServers'],
  ])('does not report a canceled %s save request as a failure', async (cardTitle, endpoint) => {
    mockSettings()
    const canceled = Object.assign(new Error('canceled'), { code: 'ERR_CANCELED', name: 'CanceledError' })
    mocks.apiPost.mockImplementation((calledEndpoint: string) => {
      if (calledEndpoint === endpoint) return Promise.reject(canceled)
      return Promise.resolve({ success: true })
    })
    await renderWithProviders(AccountSettingSystem)

    await clickSaveInCard(cardTitle)
    await flushPromises()

    expect(mocks.toastError).not.toHaveBeenCalled()
    expect(mocks.toastSuccess).not.toHaveBeenCalled()
  })
})
