import BuiltinFeatureSettings from '@/components/misc/BuiltinFeatureSettings.vue'
import { fireEvent, screen, waitFor } from '@testing-library/vue'
import { renderWithProviders } from '@tests/support/render'
import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}))

vi.mock('@/api', () => ({
  default: {
    get: (...args: unknown[]) => mocks.apiGet(...args),
    post: (...args: unknown[]) => mocks.apiPost(...args),
  },
}))

vi.mock('vue-toastification', () => ({
  useToast: () => ({
    error: mocks.toastError,
    success: mocks.toastSuccess,
  }),
}))

async function renderBuiltinFeatureSettings() {
  await renderWithProviders(BuiltinFeatureSettings)
  const button = await screen.findByRole('button', { name: '保存' })
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false))
  return button
}

describe('BuiltinFeatureSettings', () => {
  beforeEach(() => {
    mocks.apiGet.mockReset()
    mocks.apiPost.mockReset()
    mocks.toastError.mockReset()
    mocks.toastSuccess.mockReset()
    mocks.apiGet.mockResolvedValue({ data: { value: null }, success: true })
  })

  it('does not report route cancellation during save as a failure', async () => {
    let rejectSave!: (error: unknown) => void
    mocks.apiPost.mockImplementationOnce(
      () =>
        new Promise((_resolve, reject) => {
          rejectSave = reject
        }),
    )
    mocks.apiPost.mockImplementation(() => new Promise(() => {}))
    const button = await renderBuiltinFeatureSettings()

    await fireEvent.click(button)
    await waitFor(() => expect(mocks.apiPost).toHaveBeenCalled())
    rejectSave({ code: 'ERR_CANCELED' })
    await flushPromises()

    expect(mocks.toastError).not.toHaveBeenCalled()
  })

  it('keeps genuine save failures visible', async () => {
    mocks.apiPost.mockRejectedValue(new Error('save unavailable'))
    const button = await renderBuiltinFeatureSettings()

    await fireEvent.click(button)
    await flushPromises()

    expect(mocks.toastError).toHaveBeenCalledWith('内置功能配置保存失败')
  })
})
