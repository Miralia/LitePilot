import ServiceView from '@/views/system/ServiceView.vue'
import { screen, waitFor } from '@testing-library/vue'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@tests/support/render'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}))

vi.mock('@/api', () => ({
  default: {
    get: mocks.apiGet,
  },
}))

vi.mock('vue-toastification', () => ({
  useToast: () => ({
    error: mocks.toastError,
    success: mocks.toastSuccess,
  }),
}))

vi.mock('@/composables/useBackground', async () => {
  const { ref } = await vi.importActual<typeof import('vue')>('vue')

  return {
    useBackground: () => ({
      useDataRefresh: (_id: string, loadData: () => Promise<void> | void) => {
        const loading = ref(false)
        loading.value = true
        void Promise.resolve()
          .then(() => loadData())
          .finally(() => {
            loading.value = false
          })

        return {
          loading,
          refresh: loadData,
          stop: vi.fn(),
        }
      },
    }),
  }
})

vi.mock('@/composables/useScheduleProgress', () => ({
  getScheduleName: (scheduler: { name: string }) => scheduler.name,
  getScheduleNextRunText: (scheduler: { next_run: string }) => scheduler.next_run,
  getScheduleProvider: (scheduler: { provider: string }) => scheduler.provider,
  getScheduleStatusText: (scheduler: { status: string }) => scheduler.status,
  isScheduleRunning: () => false,
  isScheduleWaiting: () => false,
  useScheduleProgress: () => ({
    getScheduleProgressText: () => '',
    getScheduleProgressValue: () => 0,
  }),
}))

const scheduler = {
  id: 'download_file_sync',
  name: '下载文件同步',
  provider: 'system',
  status: 'waiting',
  next_run: '5分钟后',
}

function mockSchedulerRequests(runRequest: Promise<unknown>) {
  mocks.apiGet.mockImplementation((url: string) => {
    if (url === 'dashboard/schedule') return Promise.resolve([scheduler])
    if (url === 'system/runscheduler') return runRequest
    return Promise.resolve([])
  })
}

async function renderAndRun(runRequest: Promise<unknown>) {
  mockSchedulerRequests(runRequest)
  await renderWithProviders(ServiceView)
  const executeButtons = await screen.findAllByRole('button', { name: '执行' })
  await userEvent.click(executeButtons[0])
}

describe('ServiceView scheduler execution', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows the success toast only after the execution request completes', async () => {
    let resolveRun!: (value: { success: boolean }) => void
    const runRequest = new Promise<{ success: boolean }>(resolve => {
      resolveRun = resolve
    })

    await renderAndRun(runRequest)

    expect(mocks.apiGet).toHaveBeenCalledWith('system/runscheduler', {
      params: { jobid: scheduler.id },
    })
    expect(mocks.toastSuccess).not.toHaveBeenCalled()

    resolveRun({ success: true })
    await waitFor(() => {
      expect(mocks.toastSuccess).toHaveBeenCalledWith('定时作业执行请求提交成功！')
    })
  })

  it('reports submission failure instead of showing a false success toast', async () => {
    let rejectRun!: (error: Error) => void
    const runRequest = new Promise((_resolve, reject) => {
      rejectRun = reject
    })

    await renderAndRun(runRequest)
    rejectRun(new Error('network failed'))

    await waitFor(() => {
      expect(mocks.toastError).toHaveBeenCalledWith('定时作业执行请求提交失败')
    })
    expect(mocks.toastSuccess).not.toHaveBeenCalled()
  })
})
