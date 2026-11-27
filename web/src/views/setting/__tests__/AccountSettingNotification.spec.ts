import AccountSettingNotification from '@/views/setting/AccountSettingNotification.vue'
import { fireEvent, screen, waitFor, within } from '@testing-library/vue'
import { flushPromises } from '@vue/test-utils'
import { renderWithProviders } from '@tests/support/render'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  toastError: vi.fn(),
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
    success: mocks.toastSuccess,
  }),
}))

vi.mock('@/composables/useSilentSettingRefresh', () => ({
  useSilentSettingRefresh: vi.fn(),
}))

vi.mock('@/components/cards/NotificationChannelCard.vue', async () => {
  const { defineComponent } = await import('vue')
  return { default: defineComponent({ name: 'NotificationChannelCardStub', template: '<div />' }) }
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
    if (endpoint === 'system/setting/Notifications') return { data: { value: [] } }
    if (endpoint === 'system/setting/NotificationSwitchs') return { data: { value: [] } }
    if (endpoint === 'system/setting/NotificationSendTime') {
      return { data: { value: { end: '23:59', start: '00:00' } } }
    }
    if (endpoint === 'system/setting/NotificationTemplates') return { data: { value: {} } }
    throw new Error(`Unexpected GET ${endpoint}`)
  })
  mocks.apiPost.mockResolvedValue({ success: true })
}

async function clickSaveInCard(cardTitle: string) {
  const card = screen.getByText(cardTitle, { selector: '.v-card-title' }).closest('.v-card')
  expect(card).not.toBeNull()
  await fireEvent.click(within(card as HTMLElement).getByRole('button', { name: '保存' }))
}

describe('notification settings save feedback', () => {
  beforeEach(() => {
    mocks.apiGet.mockReset()
    mocks.apiPost.mockReset()
    mocks.toastError.mockReset()
    mocks.toastSuccess.mockReset()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it.each([
    ['通知渠道', 'system/setting/Notifications', '通知设置保存失败！'],
    ['通知发送范围', 'system/setting/NotificationSwitchs', '消息类型开关保存失败！'],
    ['通知发送时间', 'system/setting/NotificationSendTime', '通知发送时间保存失败！'],
  ])('reports network failures when saving %s', async (cardTitle, endpoint, message) => {
    mockSettings()
    mocks.apiPost.mockImplementation((calledEndpoint: string) => {
      if (calledEndpoint === endpoint) return Promise.reject(new Error('network failed'))
      return Promise.resolve({ success: true })
    })
    await renderWithProviders(AccountSettingNotification)

    await clickSaveInCard(cardTitle)

    await waitFor(() => expect(mocks.toastError).toHaveBeenCalledWith(message))
    expect(mocks.toastSuccess).not.toHaveBeenCalled()
  })

  it.each([
    ['通知渠道', 'system/setting/Notifications'],
    ['通知发送范围', 'system/setting/NotificationSwitchs'],
    ['通知发送时间', 'system/setting/NotificationSendTime'],
  ])('does not report a canceled %s save request as a failure', async (cardTitle, endpoint) => {
    mockSettings()
    const canceled = Object.assign(new Error('canceled'), { code: 'ERR_CANCELED', name: 'CanceledError' })
    mocks.apiPost.mockImplementation((calledEndpoint: string) => {
      if (calledEndpoint === endpoint) return Promise.reject(canceled)
      return Promise.resolve({ success: true })
    })
    await renderWithProviders(AccountSettingNotification)

    await clickSaveInCard(cardTitle)
    await flushPromises()

    expect(mocks.toastError).not.toHaveBeenCalled()
    expect(mocks.toastSuccess).not.toHaveBeenCalled()
  })
})
