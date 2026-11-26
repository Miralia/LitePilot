import RecognitionCachePanel from '@/components/cache/RecognitionCachePanel.vue'
import { screen, waitFor } from '@testing-library/vue'
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

async function renderRecognitionCachePanel(recognitionSource = 'themoviedb') {
  return renderWithProviders(RecognitionCachePanel, {
    initialState: {
      globalSettings: {
        data: {
          GLOBAL_IMAGE_CACHE: false,
          RECOGNIZE_SOURCE: recognitionSource,
          TMDB_IMAGE_DOMAIN: 'image.tmdb.org',
        },
      },
    },
  })
}

describe('RecognitionCachePanel recognition statistics', () => {
  beforeEach(() => {
    mocks.apiGet.mockReset()
    mocks.toastError.mockReset()
    mocks.toastSuccess.mockReset()
  })

  it('does not render removed shared recognition statistics from legacy payloads', async () => {
    mocks.apiGet.mockResolvedValue({
      data: {
        count: 12,
        recognized: 9,
        unrecognized: 3,
        shared_recognized: 27,
        shared_recognize_enabled: true,
        data: [],
      },
    })

    await renderRecognitionCachePanel()

    expect(await screen.findByText('未识别')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.queryByText('共享识别')).not.toBeInTheDocument()
  })

  it('shows unrecognized statistics without depending on a sharing feature flag', async () => {
    mocks.apiGet.mockResolvedValue({
      data: {
        count: 12,
        recognized: 9,
        unrecognized: 3,
        data: [],
      },
    })

    await renderRecognitionCachePanel()

    expect(await screen.findByText('未识别')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('keeps the panel TMDB-specific when settings contain a legacy recognition source', async () => {
    mocks.apiGet.mockResolvedValue({
      data: {
        count: 0,
        recognized: 0,
        unrecognized: 0,
        data: [],
      },
    })

    await renderRecognitionCachePanel('douban')

    await waitFor(() => expect(mocks.apiGet).toHaveBeenCalledWith('tmdb/cache'))
  })
})
