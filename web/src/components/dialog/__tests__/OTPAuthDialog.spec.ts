import OTPAuthDialog from '@/components/dialog/OTPAuthDialog.vue'
import { fireEvent, screen, waitFor } from '@testing-library/vue'
import { renderWithProviders } from '@tests/support/render'
import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  apiPost: vi.fn(),
  qrCodeToDataURL: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}))

vi.mock('@/api', () => ({
  default: {
    post: (...args: unknown[]) => mocks.apiPost(...args),
  },
}))

vi.mock('qrcode', () => ({
  default: {
    toDataURL: (...args: unknown[]) => mocks.qrCodeToDataURL(...args),
  },
}))

vi.mock('vue-toastification', () => ({
  useToast: () => ({
    error: mocks.toastError,
    success: mocks.toastSuccess,
  }),
}))

async function renderOtpDialog(props: Record<string, unknown>) {
  return renderWithProviders(OTPAuthDialog, {
    props: {
      modelValue: true,
      ...props,
    },
    global: {
      stubs: { VDialogCloseBtn: true },
    },
  })
}

async function renderGeneratedOtpDialog() {
  await renderOtpDialog({ isOtp: false })
  return screen.findByLabelText('输入 6 位验证码')
}

describe('OTPAuthDialog', () => {
  beforeEach(() => {
    mocks.apiPost.mockReset()
    mocks.qrCodeToDataURL.mockReset()
    mocks.toastError.mockReset()
    mocks.toastSuccess.mockReset()
    mocks.qrCodeToDataURL.mockResolvedValue('data:image/png;base64,qrcode')
  })

  it('does not report route cancellation while generating OTP as a failure', async () => {
    let rejectGenerate!: (error: unknown) => void
    mocks.apiPost.mockImplementationOnce(
      () =>
        new Promise((_resolve, reject) => {
          rejectGenerate = reject
        }),
    )

    await renderOtpDialog({ isOtp: false })
    await waitFor(() => expect(mocks.apiPost).toHaveBeenCalledWith('mfa/otp/generate'))
    rejectGenerate({ code: 'ERR_CANCELED' })
    await flushPromises()

    expect(mocks.toastError).not.toHaveBeenCalled()
  })

  it('does not report route cancellation while enabling OTP as a failure', async () => {
    let rejectVerify!: (error: unknown) => void
    mocks.apiPost.mockImplementation((path: string) => {
      if (path === 'mfa/otp/generate') {
        return Promise.resolve({ success: true, data: { uri: 'otpauth://totp/test', secret: 'ABC123' } })
      }
      if (path === 'mfa/otp/verify') {
        return new Promise((_resolve, reject) => {
          rejectVerify = reject
        })
      }
      return Promise.reject(new Error(`unexpected post ${path}`))
    })

    const input = await renderGeneratedOtpDialog()
    await fireEvent.update(input, '123456')
    await fireEvent.click(screen.getByRole('button', { name: '确认' }))
    await waitFor(() => expect(mocks.apiPost).toHaveBeenCalledWith('mfa/otp/verify', expect.anything()))
    rejectVerify({ code: 'ERR_CANCELED' })
    await flushPromises()

    expect(mocks.toastError).not.toHaveBeenCalled()
  })

  it('does not report route cancellation while disabling OTP as a failure', async () => {
    let rejectDisable!: (error: unknown) => void
    let verifyPasswordCallback!: (password: string) => Promise<void>
    mocks.apiPost.mockImplementationOnce(
      () =>
        new Promise((_resolve, reject) => {
          rejectDisable = reject
        }),
    )

    await renderOtpDialog({
      isOtp: true,
      onVerifyPassword: (payload: { callback: (password: string) => Promise<void> }) => {
        verifyPasswordCallback = payload.callback
      },
    })
    await fireEvent.click(await screen.findByRole('button', { name: '关闭二次验证' }))
    expect(verifyPasswordCallback).toBeDefined()
    const disabling = verifyPasswordCallback('password')
    await waitFor(() => expect(mocks.apiPost).toHaveBeenCalledWith('mfa/otp/disable', expect.anything()))
    rejectDisable({ code: 'ERR_CANCELED' })
    await disabling
    await flushPromises()

    expect(mocks.toastError).not.toHaveBeenCalled()
  })

  it('keeps genuine OTP enable failures visible', async () => {
    mocks.apiPost.mockImplementation((path: string) => {
      if (path === 'mfa/otp/generate') {
        return Promise.resolve({ success: true, data: { uri: 'otpauth://totp/test', secret: 'ABC123' } })
      }
      if (path === 'mfa/otp/verify') return Promise.reject(new Error('verify unavailable'))
      return Promise.reject(new Error(`unexpected post ${path}`))
    })

    const input = await renderGeneratedOtpDialog()
    await fireEvent.update(input, '123456')
    await fireEvent.click(screen.getByRole('button', { name: '确认' }))
    await flushPromises()

    expect(mocks.toastError).toHaveBeenCalledWith('二次验证启用失败：verify unavailable')
  })
})
