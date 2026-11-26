import { useBackground } from '@/composables/useBackground'
import { addBackgroundTimer, removeBackgroundTimer } from '@/utils/backgroundManager'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/utils/backgroundManager', () => ({
  addBackgroundTimer: vi.fn(),
  removeBackgroundTimer: vi.fn(),
}))

class FakeEventSource {
  static readonly CLOSED = 2
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static instances: FakeEventSource[] = []

  readonly url: string
  readyState = FakeEventSource.CONNECTING
  onerror: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onopen: ((event: Event) => void) | null = null
  close = vi.fn(() => {
    this.readyState = FakeEventSource.CLOSED
  })

  constructor(url: string | URL) {
    this.url = String(url)
    FakeEventSource.instances.push(this)
  }

  static reset() {
    FakeEventSource.instances = []
  }
}

describe('useBackground', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    FakeEventSource.reset()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('does not register a data refresh timer after the component unmounts during the initial load', async () => {
    let finishInitialLoad!: () => void
    const initialLoad = new Promise<void>(resolve => {
      finishInitialLoad = resolve
    })
    const loadData = vi.fn(() => initialLoad)
    const TestComponent = defineComponent({
      setup() {
        useBackground().useDataRefresh('test-data-refresh', loadData, 1000, true)
        return {}
      },
      template: '<div />',
    })

    const wrapper = mount(TestComponent)
    expect(loadData).toHaveBeenCalledTimes(1)

    wrapper.unmount()
    expect(removeBackgroundTimer).toHaveBeenCalledWith('test-data-refresh')

    finishInitialLoad()
    await flushPromises()

    expect(addBackgroundTimer).not.toHaveBeenCalled()
  })
  it('registers the data refresh timer after a mounted component finishes the initial load', async () => {
    const loadData = vi.fn().mockResolvedValue(undefined)
    const TestComponent = defineComponent({
      setup() {
        useBackground().useDataRefresh('test-data-refresh-ready', loadData, 1000, true)
        return {}
      },
      template: '<div />',
    })

    const wrapper = mount(TestComponent)
    await flushPromises()

    expect(addBackgroundTimer).toHaveBeenCalledWith('test-data-refresh-ready', expect.any(Function), 1000, {
      runInBackground: false,
      skipInitialRun: true,
    })

    wrapper.unmount()
    expect(removeBackgroundTimer).toHaveBeenCalledWith('test-data-refresh-ready')
  })
  it('does not overlap refresh calls while the previous load is still pending', async () => {
    let finishFirstLoad!: () => void
    const firstLoad = new Promise<void>(resolve => {
      finishFirstLoad = resolve
    })
    const loadData = vi.fn().mockReturnValueOnce(firstLoad).mockResolvedValue(undefined)
    let refresh!: () => Promise<void>
    const TestComponent = defineComponent({
      setup() {
        const dataRefresh = useBackground().useDataRefresh('test-data-refresh-overlap', loadData, 1000, true)
        refresh = dataRefresh.refresh
        return {}
      },
      template: '<div />',
    })

    const wrapper = mount(TestComponent)
    expect(loadData).toHaveBeenCalledTimes(1)

    void refresh()
    void refresh()
    expect(loadData).toHaveBeenCalledTimes(1)

    finishFirstLoad()
    await flushPromises()
    await refresh()
    expect(loadData).toHaveBeenCalledTimes(2)

    wrapper.unmount()
  })
  it('isolates simultaneous SSE consumers', () => {
    vi.useFakeTimers()
    vi.stubGlobal('EventSource', FakeEventSource as unknown as typeof EventSource)
    const TestComponent = defineComponent({
      setup() {
        useBackground().useSSE('/api/events', vi.fn())
        return {}
      },
      template: '<div />',
    })

    const first = mount(TestComponent)
    const second = mount(TestComponent)
    vi.advanceTimersByTime(100)

    expect(FakeEventSource.instances).toHaveLength(2)

    first.unmount()
    expect(FakeEventSource.instances[0].close).toHaveBeenCalledOnce()
    expect(FakeEventSource.instances[1].close).not.toHaveBeenCalled()
    second.unmount()
  })
  it('does not connect when paused during the initial connection delay', () => {
    vi.useFakeTimers()
    vi.stubGlobal('EventSource', FakeEventSource as unknown as typeof EventSource)
    let controls!: { pause: () => void; resume: () => void }
    const TestComponent = defineComponent({
      setup() {
        controls = useBackground().useSSE('/api/events', vi.fn())
        return {}
      },
      template: '<div />',
    })

    const wrapper = mount(TestComponent)
    controls.pause()
    vi.advanceTimersByTime(1_000)
    expect(FakeEventSource.instances).toHaveLength(0)

    controls.resume()
    expect(FakeEventSource.instances).toHaveLength(1)
    wrapper.unmount()
  })

  it('pauses and resumes an established SSE connection', () => {
    vi.useFakeTimers()
    vi.stubGlobal('EventSource', FakeEventSource as unknown as typeof EventSource)
    let controls!: { pause: () => void; resume: () => void }
    const TestComponent = defineComponent({
      setup() {
        controls = useBackground().useSSE('/api/events', vi.fn())
        return {}
      },
      template: '<div />',
    })

    const wrapper = mount(TestComponent)
    vi.advanceTimersByTime(100)
    expect(FakeEventSource.instances).toHaveLength(1)

    controls.pause()
    expect(FakeEventSource.instances[0].close).toHaveBeenCalledOnce()

    controls.resume()
    expect(FakeEventSource.instances).toHaveLength(2)
    wrapper.unmount()
  })
})
