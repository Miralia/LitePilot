import UserNotification from '@/layouts/default/components/UserNotification.vue'
import { fireEvent, screen, waitFor } from '@testing-library/vue'
import { renderWithProviders } from '@tests/support/render'
import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  apiDelete: vi.fn(),
  apiGet: vi.fn(),
  createConfirm: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
  useDelayedSSE: vi.fn(),
}))

vi.mock('@/api', () => ({
  default: {
    delete: (...args: unknown[]) => mocks.apiDelete(...args),
    get: (...args: unknown[]) => mocks.apiGet(...args),
  },
}))

vi.mock('@/composables/useBackground', () => ({
  useBackground: () => ({
    useDelayedSSE: mocks.useDelayedSSE,
  }),
}))

vi.mock('@/composables/useConfirm', () => ({
  useConfirm: () => mocks.createConfirm,
}))

vi.mock('vue-toastification', () => ({
  useToast: () => ({
    error: mocks.toastError,
    success: mocks.toastSuccess,
  }),
}))

function createNotification() {
  return {
    id: 1,
    date: '2026-11-27 12:00:00',
    image: '',
    link: '',
    mtype: '其它',
    note: '',
    read: true,
    text: '系统通知内容',
    title: '系统通知标题',
    type: 'system',
  }
}

async function openNotificationClearMenu(container: Element) {
  const activator = container.querySelector('button')
  expect(activator).not.toBeNull()
  await fireEvent.click(activator as HTMLButtonElement)
  expect(await screen.findByText('系统通知标题')).toBeInTheDocument()

  const clearActivator = Array.from(document.querySelectorAll('button'))[1]
  expect(clearActivator).toBeDefined()
  await fireEvent.click(clearActivator)
}

describe('UserNotification', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
    mocks.apiGet.mockResolvedValue([createNotification()])
    mocks.createConfirm.mockResolvedValue(true)
  })

  it('does not report route cancellation while clearing notifications as a failure', async () => {
    let rejectClear!: (error: unknown) => void
    mocks.apiDelete.mockImplementationOnce(
      () =>
        new Promise((_resolve, reject) => {
          rejectClear = reject
        }),
    )
    const { container } = await renderWithProviders(UserNotification)

    await openNotificationClearMenu(container)
    await fireEvent.click(await screen.findByText('清理全部消息'))
    await waitFor(() =>
      expect(mocks.apiDelete).toHaveBeenCalledWith('message/notification', {
        params: { scope: 'all' },
      }),
    )
    rejectClear({ code: 'ERR_CANCELED' })
    await flushPromises()

    expect(mocks.toastError).not.toHaveBeenCalled()
  })

  it('keeps genuine notification clear failures visible', async () => {
    mocks.apiDelete.mockRejectedValue(new Error('clear unavailable'))
    const { container } = await renderWithProviders(UserNotification)

    await openNotificationClearMenu(container)
    await fireEvent.click(await screen.findByText('清理全部消息'))
    await flushPromises()

    expect(mocks.toastError).toHaveBeenCalledWith('clear unavailable')
  })
})
