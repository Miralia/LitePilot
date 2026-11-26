import { SSEManager, type SSEConnectionStatus, type SSEManagerOptions } from '@/utils/sseManager'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/** 提供 SSEManager 生命周期测试所需的最小 EventSource 协议。 */
class FakeEventSource {
  static readonly CLOSED = 2
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static instances: FakeEventSource[] = []
  static throwOnNextConstruction = false

  readonly url: string
  readyState = FakeEventSource.CONNECTING
  onerror: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onopen: ((event: Event) => void) | null = null
  close = vi.fn(() => {
    this.readyState = FakeEventSource.CLOSED
  })

  constructor(url: string | URL) {
    if (FakeEventSource.throwOnNextConstruction) {
      FakeEventSource.throwOnNextConstruction = false
      throw new Error('EventSource construction failed')
    }

    this.url = String(url)
    FakeEventSource.instances.push(this)
  }

  emit(data: unknown) {
    this.onmessage?.(new MessageEvent('message', { data }))
  }

  fail() {
    this.readyState = FakeEventSource.CLOSED
    this.onerror?.(new Event('error'))
  }

  open() {
    this.readyState = FakeEventSource.OPEN
    this.onopen?.(new Event('open'))
  }

  static reset() {
    FakeEventSource.instances = []
    FakeEventSource.throwOnNextConstruction = false
  }
}

const managerOptions: SSEManagerOptions = {
  backgroundCloseDelay: 500,
  maxReconnectAttempts: 2,
  maxReconnectDelay: 150,
  reconnectBackoffMultiplier: 10,
  reconnectDelay: 100,
}

describe('SSEManager', () => {
  const managers: SSEManager[] = []
  let hidden = false

  function createManager(
    options: Partial<SSEManagerOptions> = {},
    statusListener?: (status: SSEConnectionStatus) => void,
  ) {
    const manager = new SSEManager('/api/events', { ...managerOptions, ...options }, statusListener)
    managers.push(manager)
    return manager
  }

  beforeEach(() => {
    vi.useFakeTimers()
    FakeEventSource.reset()
    vi.stubGlobal('EventSource', FakeEventSource as unknown as typeof EventSource)
    vi.spyOn(document, 'hidden', 'get').mockImplementation(() => hidden)
    hidden = false
  })

  afterEach(() => {
    managers.splice(0).forEach(manager => manager.destroy())
    vi.useRealTimers()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('start 建立连接并分发消息，stop 关闭连接', () => {
    const messageListener = vi.fn()
    const statusListener = vi.fn()
    const manager = createManager({}, statusListener)

    manager.start(messageListener)

    expect(FakeEventSource.instances).toHaveLength(1)
    expect(FakeEventSource.instances[0].url).toBe('/api/events')
    expect(statusListener).toHaveBeenLastCalledWith('connecting')

    const source = FakeEventSource.instances[0]
    source.open()
    source.emit({ id: 1 })

    expect(messageListener).toHaveBeenCalledOnce()
    expect(messageListener.mock.calls[0][0].data).toEqual({ id: 1 })
    expect(statusListener.mock.calls.map(([status]) => status)).toEqual(['connecting', 'open'])

    manager.stop()
    expect(source.close).toHaveBeenCalledOnce()
    expect(statusListener).toHaveBeenLastCalledWith('idle')
  })

  it('消息和状态监听器错误不会中断连接生命周期', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const messageListener = vi.fn(() => {
      throw new Error('message listener failed')
    })
    const statusListener = vi.fn(() => {
      throw new Error('status listener failed')
    })
    const manager = createManager({}, statusListener)

    manager.start(messageListener)
    const source = FakeEventSource.instances[0]
    source.open()
    source.emit({ id: 1 })

    expect(messageListener).toHaveBeenCalledOnce()
    expect(consoleError).toHaveBeenCalledWith('SSE: 消息监听器错误', expect.any(Error))
    expect(consoleError).toHaveBeenCalledWith('SSE: 状态监听器错误', expect.any(Error))
  })

  it('按退避上限重连并在达到最大次数后关闭', () => {
    const statusListener = vi.fn()
    const manager = createManager({}, statusListener)
    manager.start(vi.fn())

    FakeEventSource.instances[0].fail()
    vi.advanceTimersByTime(99)
    expect(FakeEventSource.instances).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(FakeEventSource.instances).toHaveLength(2)

    FakeEventSource.instances[1].fail()
    vi.advanceTimersByTime(149)
    expect(FakeEventSource.instances).toHaveLength(2)
    vi.advanceTimersByTime(1)
    expect(FakeEventSource.instances).toHaveLength(3)

    FakeEventSource.instances[2].fail()
    expect(statusListener).toHaveBeenLastCalledWith('closed')

    vi.advanceTimersByTime(1_000)
    expect(FakeEventSource.instances).toHaveLength(3)
  })

  it('成功建连后清零失败次数，并从首档延迟重新退避', () => {
    const manager = createManager({ maxReconnectAttempts: 3 })
    manager.start(vi.fn())

    FakeEventSource.instances[0].fail()
    vi.advanceTimersByTime(100)
    FakeEventSource.instances[1].open()

    FakeEventSource.instances[1].fail()
    vi.advanceTimersByTime(99)
    expect(FakeEventSource.instances).toHaveLength(2)
    vi.advanceTimersByTime(1)
    expect(FakeEventSource.instances).toHaveLength(3)
  })

  it('EventSource 构造失败时记录错误并按相同策略恢复', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const statusListener = vi.fn()
    const manager = createManager({}, statusListener)
    FakeEventSource.throwOnNextConstruction = true

    manager.start(vi.fn())

    expect(statusListener).toHaveBeenLastCalledWith('error')
    expect(consoleError).toHaveBeenCalledWith('SSE: 连接创建失败', expect.any(Error))

    vi.advanceTimersByTime(100)
    expect(FakeEventSource.instances).toHaveLength(1)
    expect(statusListener).toHaveBeenLastCalledWith('connecting')
  })

  it('短暂进入后台会取消延迟关闭，长期后台关闭后在前台恢复', () => {
    const statusListener = vi.fn()
    const manager = createManager({}, statusListener)
    manager.start(vi.fn())
    const source = FakeEventSource.instances[0]
    source.open()

    hidden = true
    document.dispatchEvent(new Event('visibilitychange'))
    vi.advanceTimersByTime(499)
    expect(source.close).not.toHaveBeenCalled()

    hidden = false
    document.dispatchEvent(new Event('visibilitychange'))
    vi.advanceTimersByTime(500)
    expect(source.close).not.toHaveBeenCalled()

    hidden = true
    document.dispatchEvent(new Event('visibilitychange'))
    vi.advanceTimersByTime(500)
    expect(source.close).toHaveBeenCalledOnce()
    expect(statusListener).toHaveBeenLastCalledWith('closed')

    hidden = false
    document.dispatchEvent(new Event('visibilitychange'))
    expect(FakeEventSource.instances).toHaveLength(2)
    expect(statusListener).toHaveBeenLastCalledWith('connecting')
  })

  it('stop 清理待重连定时器并阻止后续自动建连', () => {
    const manager = createManager()
    manager.start(vi.fn())
    const firstSource = FakeEventSource.instances[0]

    firstSource.fail()
    expect(vi.getTimerCount()).toBe(1)

    manager.stop()
    expect(firstSource.close).toHaveBeenCalledOnce()
    expect(vi.getTimerCount()).toBe(0)

    vi.advanceTimersByTime(1_000)
    expect(FakeEventSource.instances).toHaveLength(1)
  })

  it('destroy 清理后台定时器、连接和构造时注册的 DOM 订阅', () => {
    const addDocumentListener = vi.spyOn(document, 'addEventListener')
    const addWindowListener = vi.spyOn(window, 'addEventListener')
    const removeDocumentListener = vi.spyOn(document, 'removeEventListener')
    const removeWindowListener = vi.spyOn(window, 'removeEventListener')
    const manager = createManager()
    manager.start(vi.fn())
    const source = FakeEventSource.instances[0]
    source.open()
    const visibilityHandler = addDocumentListener.mock.calls.find(([event]) => event === 'visibilitychange')?.[1]
    const beforeUnloadHandler = addWindowListener.mock.calls.find(([event]) => String(event) === 'beforeunload')?.[1]

    hidden = true
    document.dispatchEvent(new Event('visibilitychange'))
    expect(vi.getTimerCount()).toBe(1)

    manager.destroy()
    expect(source.close).toHaveBeenCalledOnce()
    expect(vi.getTimerCount()).toBe(0)
    vi.runAllTimers()

    expect(FakeEventSource.instances).toHaveLength(1)
    expect(removeDocumentListener).toHaveBeenCalledWith('visibilitychange', visibilityHandler)
    expect(removeWindowListener).toHaveBeenCalledWith('beforeunload', beforeUnloadHandler)

    manager.start(vi.fn())
    expect(FakeEventSource.instances).toHaveLength(1)
  })
})
