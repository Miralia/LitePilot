export type SSEConnectionStatus = 'idle' | 'connecting' | 'open' | 'error' | 'closed'

export interface SSEManagerOptions {
  backgroundCloseDelay: number
  reconnectDelay: number
  maxReconnectAttempts: number
  reconnectBackoffMultiplier: number
  maxReconnectDelay: number
}

type SSEMessageListener = (event: MessageEvent) => void
type SSEStatusListener = (status: SSEConnectionStatus) => void

/**
 * SSE连接管理器
 * 统一收口 EventSource 生命周期，避免后台常驻连接和重复重连。
 */
export class SSEManager {
  private eventSource: EventSource | null = null
  private readonly url: string
  private readonly statusListener?: SSEStatusListener
  private isBackground = document.hidden
  private reconnectTimer: number | null = null
  private backgroundCloseTimer: number | null = null
  private messageListener: SSEMessageListener | null = null
  private readonly options: SSEManagerOptions
  private reconnectAttempts = 0
  private isConnecting = false
  private isDestroyed = false
  private connectionStatus: SSEConnectionStatus = 'idle'
  private readonly handleVisibilityChange = () => {
    if (document.hidden) {
      this.handleBackground()
    } else {
      this.handleForeground()
    }
  }
  private readonly handleBeforeUnload = () => {
    this.destroy()
  }

  constructor(url: string, options: Partial<SSEManagerOptions> = {}, statusListener?: SSEStatusListener) {
    this.url = url
    this.statusListener = statusListener
    this.options = {
      backgroundCloseDelay: 5000, // 5秒后关闭后台连接
      reconnectDelay: 3000, // 3秒后重连
      maxReconnectAttempts: 3,
      reconnectBackoffMultiplier: 1.5,
      maxReconnectDelay: 30_000,
      ...options,
    }

    this.setupVisibilityListener()
  }

  private setupVisibilityListener() {
    document.addEventListener('visibilitychange', this.handleVisibilityChange)
    window.addEventListener('beforeunload', this.handleBeforeUnload)
  }

  private removeVisibilityListener() {
    document.removeEventListener('visibilitychange', this.handleVisibilityChange)
    window.removeEventListener('beforeunload', this.handleBeforeUnload)
  }

  private handleBackground() {
    if (this.isDestroyed) return

    this.isBackground = true
    this.clearReconnectTimer()

    // 延迟关闭SSE连接，避免频繁切换
    this.clearBackgroundCloseTimer()

    this.backgroundCloseTimer = window.setTimeout(() => {
      if (this.isBackground && this.eventSource) {
        this.closeCurrentEventSource()
        this.setConnectionStatus('closed')
      }
    }, this.options.backgroundCloseDelay)
  }

  private handleForeground() {
    if (this.isDestroyed) return

    this.isBackground = false

    // 清除后台关闭定时器
    this.clearBackgroundCloseTimer()

    // 只有在监听仍处于激活状态时才重新建立连接
    if (this.messageListener && (!this.eventSource || this.eventSource.readyState === EventSource.CLOSED)) {
      this.reconnectSSE(0)
    }
  }

  private reconnectSSE(attemptCount = 0) {
    if (this.isDestroyed || this.isBackground || !this.messageListener) {
      return
    }

    if (attemptCount > this.options.maxReconnectAttempts) {
      this.reconnectAttempts = this.options.maxReconnectAttempts
      this.setConnectionStatus('closed')
      return
    }

    if (this.isConnecting) {
      return
    }

    this.clearReconnectTimer()
    this.closeCurrentEventSource()
    this.isConnecting = true
    this.reconnectAttempts = attemptCount
    this.setConnectionStatus('connecting')

    try {
      const source = new EventSource(this.url)
      this.eventSource = source

      source.onopen = () => {
        if (source !== this.eventSource) return
        this.isConnecting = false
        this.reconnectAttempts = 0
        this.setConnectionStatus('open')
      }

      source.onerror = () => {
        if (source !== this.eventSource) return

        this.isConnecting = false
        this.setConnectionStatus('error')

        if (source.readyState === EventSource.CLOSED) {
          this.closeCurrentEventSource()
          this.scheduleReconnect(this.reconnectAttempts + 1)
        }
      }

      source.onmessage = event => {
        if (source !== this.eventSource || this.isDestroyed || !this.messageListener) return

        try {
          this.messageListener(event)
        } catch (error) {
          console.error('SSE: 消息监听器错误', error)
        }
      }
    } catch (error) {
      this.isConnecting = false
      this.setConnectionStatus('error')

      // 连接创建失败，尝试重连
      this.scheduleReconnect(this.reconnectAttempts + 1)
      console.error('SSE: 连接创建失败', error)
    }
  }

  private scheduleReconnect(attemptCount: number) {
    if (this.isDestroyed || this.isBackground || !this.messageListener) {
      return
    }

    if (attemptCount > this.options.maxReconnectAttempts) {
      this.reconnectAttempts = this.options.maxReconnectAttempts
      this.setConnectionStatus('closed')
      return
    }

    this.clearReconnectTimer()
    this.reconnectAttempts = attemptCount

    // 失败越多等待越久，避免网络波动时短时间内打满连接。
    const reconnectDelay = Math.min(
      this.options.reconnectDelay * this.options.reconnectBackoffMultiplier ** Math.max(0, attemptCount - 1),
      this.options.maxReconnectDelay,
    )

    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null
      this.reconnectSSE(attemptCount)
    }, reconnectDelay)
  }

  private closeCurrentEventSource() {
    if (!this.eventSource) {
      return
    }

    this.eventSource.onopen = null
    this.eventSource.onerror = null
    this.eventSource.onmessage = null
    this.eventSource.close()
    this.eventSource = null
    this.isConnecting = false
  }

  private clearReconnectTimer() {
    if (!this.reconnectTimer) return

    clearTimeout(this.reconnectTimer)
    this.reconnectTimer = null
  }

  private clearBackgroundCloseTimer() {
    if (!this.backgroundCloseTimer) return

    clearTimeout(this.backgroundCloseTimer)
    this.backgroundCloseTimer = null
  }

  private setConnectionStatus(status: SSEConnectionStatus) {
    if (this.connectionStatus === status) return

    this.connectionStatus = status
    if (!this.statusListener) return

    try {
      this.statusListener(status)
    } catch (error) {
      console.error('SSE: 状态监听器错误', error)
    }
  }

  /**
   * 开始监听消息并按需建立连接
   */
  start(listener: SSEMessageListener) {
    if (this.isDestroyed) return

    this.messageListener = listener

    // 如果还没有连接且不在后台，现在建立连接
    if (
      !this.isBackground &&
      !this.isConnecting &&
      (!this.eventSource || this.eventSource.readyState === EventSource.CLOSED)
    ) {
      this.reconnectSSE(0)
    }
  }

  /**
   * 停止监听并关闭当前连接
   */
  stop() {
    if (this.isDestroyed) return

    this.messageListener = null
    this.resetConnection()
  }

  /**
   * 销毁管理器并清理所有引用
   */
  destroy() {
    if (this.isDestroyed) return

    this.isDestroyed = true
    this.messageListener = null
    this.resetConnection()
    this.removeVisibilityListener()
  }

  private resetConnection() {
    this.closeCurrentEventSource()
    this.clearReconnectTimer()
    this.clearBackgroundCloseTimer()
    this.isConnecting = false
    this.reconnectAttempts = 0
    this.setConnectionStatus('idle')
  }
}
