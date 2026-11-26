import { appActivityLifecycle, type AppActivityState } from '@/utils/appActivityLifecycle'

/**
 * 后台管理器
 * 统一管理定时器和后台活动，减少iOS系统杀掉应用的概率
 */
class BackgroundManager {
  private timers: Map<
    string,
    {
      callback: () => void
      interval: number
      timer: ReturnType<typeof setInterval> | null
      runInBackground?: boolean
    }
  > = new Map()

  private readonly handleActivityStateChange = (state: AppActivityState) => {
    const wasBackground = this.isBackground
    this.isBackground = state === 'suspended'

    if (this.isBackground && !wasBackground) {
      this.pauseAllTimers()
    } else if (!this.isBackground && wasBackground) {
      this.resumeAllTimers()
    }
  }
  private readonly handleBeforeUnload = () => {
    this.destroy()
  }

  private isBackground = false
  private isDestroyed = false
  private isInitialized = false
  private releaseActivityLifecycle: (() => void) | null = null
  private stopActivityStateSubscription: (() => void) | null = null

  private ensureInitialized() {
    if (this.isInitialized || this.isDestroyed) return

    this.isInitialized = true
    this.releaseActivityLifecycle = appActivityLifecycle.acquire()
    this.stopActivityStateSubscription = appActivityLifecycle.subscribe(this.handleActivityStateChange)
    window.addEventListener('beforeunload', this.handleBeforeUnload)
  }

  private removeLifecycleListeners() {
    if (!this.isInitialized) return

    window.removeEventListener('beforeunload', this.handleBeforeUnload)
    this.stopActivityStateSubscription?.()
    this.stopActivityStateSubscription = null
    this.releaseActivityLifecycle?.()
    this.releaseActivityLifecycle = null
    this.isInitialized = false
  }

  /**
   * 添加定时器
   */
  addTimer(
    id: string,
    callback: () => void,
    interval: number,
    options: {
      runInBackground?: boolean
      skipInitialRun?: boolean
    } = {},
  ) {
    const { runInBackground = false, skipInitialRun = false } = options

    if (this.isDestroyed) return
    this.ensureInitialized()

    this.removeTimer(id)

    const timerConfig = {
      callback,
      interval,
      timer: null as ReturnType<typeof setInterval> | null,
      runInBackground,
    }

    // 创建定时器
    const wrappedCallback = () => {
      if (this.isDestroyed) return

      // 只有在前台运行，或者明确允许后台运行时才执行
      if (!this.isBackground || runInBackground) {
        try {
          callback()
        } catch (error) {
          console.error(`Background: 定时器 ${id} 执行错误:`, error)
        }
      }
    }

    timerConfig.timer = setInterval(wrappedCallback, interval)
    this.timers.set(id, timerConfig)

    // 如果不跳过初始运行，立即执行一次
    if (!skipInitialRun) {
      wrappedCallback()
    }
  }

  /**
   * 移除定时器
   */
  removeTimer(id: string) {
    const timerConfig = this.timers.get(id)
    if (timerConfig) {
      if (timerConfig.timer) {
        clearInterval(timerConfig.timer)
      }
      this.timers.delete(id)

      // 没有任务时释放监听，首屏只导入模块不会产生常驻开销。
      if (this.timers.size === 0) {
        this.removeLifecycleListeners()
      }
    }
  }

  /**
   * 暂停所有定时器
   */
  private pauseAllTimers() {
    this.timers.forEach((timerConfig, id) => {
      if (timerConfig.timer && !timerConfig.runInBackground) {
        clearInterval(timerConfig.timer)
        timerConfig.timer = null
      }
    })
  }

  /**
   * 恢复所有定时器
   */
  private resumeAllTimers() {
    this.timers.forEach((timerConfig, id) => {
      if (!timerConfig.timer) {
        const wrappedCallback = () => {
          if (this.isDestroyed) return

          if (!this.isBackground || timerConfig.runInBackground) {
            try {
              timerConfig.callback()
            } catch (error) {
              console.error(`Background: 定时器 ${id} 执行错误:`, error)
            }
          }
        }

        timerConfig.timer = setInterval(wrappedCallback, timerConfig.interval)
      }
    })
  }

  /**
   * 销毁管理器
   */
  destroy() {
    this.isDestroyed = true

    // 清理所有定时器
    this.timers.forEach((timerConfig, id) => {
      if (timerConfig.timer) {
        clearInterval(timerConfig.timer)
      }
    })
    this.timers.clear()

    // 清理按需注册的生命周期与活动监听
    this.removeLifecycleListeners()
  }
}

/**
 * 全局后台管理器实例
 */
const backgroundManager = new BackgroundManager()

/**
 * 便捷的定时器管理函数
 */
export function addBackgroundTimer(
  id: string,
  callback: () => void,
  interval: number,
  options?: {
    runInBackground?: boolean
    skipInitialRun?: boolean
  },
) {
  backgroundManager.addTimer(id, callback, interval, options)
}

export function removeBackgroundTimer(id: string) {
  backgroundManager.removeTimer(id)
}
