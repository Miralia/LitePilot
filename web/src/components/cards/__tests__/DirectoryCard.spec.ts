import type { TransferDirectoryConf } from '@/api/types'
import DirectoryCard from '@/components/cards/DirectoryCard.vue'
import { renderWithProviders } from '@tests/support/render'
import { waitFor } from '@testing-library/vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
}))

vi.mock('@/api', () => ({
  default: {
    get: mocks.apiGet,
  },
}))

function createDirectory(): TransferDirectoryConf {
  return {
    name: '跨存储整理',
    priority: 1,
    storage: 'smb',
    download_path: '/downloads',
    media_type: '',
    monitor_type: 'monitor',
    monitor_mode: 'fast',
    transfer_type: 'link',
    overwrite_mode: 'never',
    library_path: '/library',
    library_storage: 'local',
    renaming: true,
    scraping: true,
    notify: true,
  }
}

describe('DirectoryCard transfer type compatibility', () => {
  beforeEach(() => {
    mocks.apiGet.mockReset()
    mocks.apiGet.mockImplementation((endpoint: string) => {
      if (endpoint === 'storage/transtype/smb') {
        return Promise.resolve({ transtype: { move: '移动', copy: '复制', link: '硬链接' } })
      }
      if (endpoint === 'storage/transtype/local') {
        return Promise.resolve({ transtype: { copy: '复制', move: '移动', link: '硬链接', softlink: '软链接' } })
      }
      return Promise.reject(new Error(`Unexpected GET ${endpoint}`))
    })
  })

  it('removes hard links from choices when source and library use different storage backends', async () => {
    const directory = createDirectory()

    await renderWithProviders(DirectoryCard, {
      props: {
        type: 'download',
        directory,
        storages: [
          { type: 'local', name: '本地', config: {} },
          { type: 'smb', name: 'SMB', config: {} },
        ],
      },
      global: {
        stubs: {
          VDialogCloseBtn: true,
          IconBtn: true,
          VPathField: true,
        },
      },
    })

    await waitFor(() => {
      expect(directory.transfer_type).toBe('move')
    })
  })
})
