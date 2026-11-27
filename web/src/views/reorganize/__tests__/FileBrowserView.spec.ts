import FileBrowserView from '@/views/reorganize/FileBrowserView.vue'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
}))

vi.mock('@/api', () => ({
  default: {
    get: mocks.apiGet,
  },
}))

const FileBrowserStub = defineComponent({
  name: 'FileBrowser',
  emits: ['pathchanged'],
  props: ['item', 'itemstack', 'storages'],
  template: '<div data-testid="file-browser" />',
})

function mockSettings(
  storages: Array<{ name: string; type: string }> | null,
  directories: Array<{ download_path?: string; storage: string }> | null,
) {
  mocks.apiGet.mockImplementation((endpoint: string) => {
    if (endpoint === 'system/setting/public/Storages') {
      return { data: { value: storages }, success: true }
    }
    if (endpoint === 'system/setting/public/Directories') {
      return { data: { value: directories }, success: true }
    }
    throw new Error(`Unexpected GET ${endpoint}`)
  })
}

async function mountView() {
  const wrapper = mount(FileBrowserView, {
    global: {
      stubs: {
        FileBrowser: FileBrowserStub,
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('FileBrowserView initialization', () => {
  beforeEach(() => {
    mocks.apiGet.mockReset()
    localStorage.clear()
  })

  it('falls back to the storage root when Directories is null', async () => {
    mockSettings([{ name: '本地', type: 'local' }], null)
    const wrapper = await mountView()

    const browser = wrapper.getComponent(FileBrowserStub)
    expect(browser.props('item')).toMatchObject({
      name: '/',
      path: '/',
      storage: 'local',
      type: 'dir',
    })
    expect(browser.props('itemstack')).toEqual([
      {
        fileid: 'root',
        name: '/',
        path: '/',
        storage: 'local',
        type: 'dir',
      },
    ])
  })

  it('falls back to local root when Storages and Directories are null', async () => {
    mockSettings(null, null)
    const browser = (await mountView()).getComponent(FileBrowserStub)

    expect(browser.props('storages')).toEqual([])
    expect(browser.props('item')).toMatchObject({
      name: '/',
      path: '/',
      storage: 'local',
      type: 'dir',
    })
  })

  it('uses the cached available storage and the common configured path', async () => {
    localStorage.setItem('fileBrowserView.activeStorage', 'smb')
    mockSettings(
      [
        { name: '本地', type: 'local' },
        { name: 'SMB共享', type: 'smb' },
      ],
      [
        { download_path: '/media/movies', storage: 'smb' },
        { download_path: '/media/tv', storage: 'smb' },
        { download_path: '/downloads', storage: 'local' },
      ],
    )

    const browser = (await mountView()).getComponent(FileBrowserStub)

    expect(browser.props('item')).toMatchObject({
      name: 'media',
      path: '/media/',
      storage: 'smb',
    })
    expect(browser.props('itemstack')).toHaveLength(2)
  })

  it('filters unavailable storage entries and selects the most populated available storage', async () => {
    mockSettings(
      [
        { name: '本地', type: 'local' },
        { name: 'SMB共享', type: 'smb' },
      ],
      [
        { download_path: '/ignored', storage: 'missing' },
        { download_path: '/one', storage: 'local' },
        { download_path: '/shows/a', storage: 'smb' },
        { download_path: '/shows/b', storage: 'smb' },
        { storage: 'smb' },
      ],
    )

    const browser = (await mountView()).getComponent(FileBrowserStub)

    expect(browser.props('item')).toMatchObject({
      name: 'shows',
      path: '/shows/',
      storage: 'smb',
    })
  })

  it('hides removed storage types even when they remain in saved settings', async () => {
    mockSettings(
      [
        { name: '本地', type: 'local' },
        { name: '云盘', type: 'rclone' },
      ],
      [{ download_path: '/cloud/media', storage: 'rclone' }],
    )

    const browser = (await mountView()).getComponent(FileBrowserStub)

    expect(browser.props('storages')).toEqual([{ name: '本地', type: 'local' }])
    expect(browser.props('item')).toMatchObject({
      path: '/',
      storage: 'local',
    })
  })

  it('updates storage persistence and rebuilds the root breadcrumb on navigation', async () => {
    mockSettings(
      [
        { name: '本地', type: 'local' },
        { name: 'SMB共享', type: 'smb' },
      ],
      [{ download_path: '/downloads/tv', storage: 'local' }],
    )
    const browser = (await mountView()).getComponent(FileBrowserStub)

    browser.vm.$emit('pathchanged', {
      fileid: 'remote-root',
      name: '/',
      path: '/',
      storage: 'smb',
      type: 'dir',
    })
    await flushPromises()

    expect(localStorage.getItem('fileBrowserView.activeStorage')).toBe('smb')
    expect(browser.props('item')).toMatchObject({ path: '/', storage: 'smb' })
    expect(browser.props('itemstack')).toEqual([
      {
        fileid: 'remote-root',
        name: '/',
        path: '/',
        storage: 'smb',
        type: 'dir',
      },
    ])
  })

  it('truncates the breadcrumb stack when navigating to an existing ancestor', async () => {
    mockSettings([{ name: '本地', type: 'local' }], [{ download_path: '/downloads/tv', storage: 'local' }])
    const browser = (await mountView()).getComponent(FileBrowserStub)

    browser.vm.$emit('pathchanged', {
      name: 'downloads',
      path: '/downloads/',
      storage: 'local',
      type: 'dir',
    })
    await flushPromises()

    expect(browser.props('itemstack').map((item: { path: string }) => item.path)).toEqual(['/', '/downloads/'])
  })

  it('builds Windows drive breadcrumbs without treating the drive as a POSIX child', async () => {
    mockSettings([{ name: '本地', type: 'local' }], [{ download_path: 'D:/media/movies', storage: 'local' }])

    const browser = (await mountView()).getComponent(FileBrowserStub)

    expect(browser.props('item')).toMatchObject({
      name: 'movies',
      path: 'D:/media/movies/',
      storage: 'local',
    })
    expect(browser.props('itemstack').map((item: { path: string }) => item.path)).toEqual([
      '/',
      'D:/',
      'D:/media/',
      'D:/media/movies/',
    ])
    expect(browser.props('itemstack').map((item: { name: string }) => item.name)).toEqual([
      '/',
      'D:',
      'media',
      'movies',
    ])
  })

})
