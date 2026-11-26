import { getCurrentInstance, onMounted, onUnmounted, ref, type Ref } from 'vue'
import { SSEManager, type SSEManagerOptions } from '@/utils/sseManager'
import { addBackgroundTimer, removeBackgroundTimer } from '@/utils/backgroundManager'

type SSEConnectionOptions = Partial<SSEManagerOptions>
type UseSSEOptions = SSEConnectionOptions & {
  connectDelay?: number
}

/**
 * 后台任务组合函数
 * 统一管理SSE连接和定时器，减少后台常驻活动。
 */
export function useBackground() {
  /**
   * 使用SSE连接
   * @param url SSE连接地址
   * @param messageHandler 消息处理函数
   * @param options 选项
   */
  const useSSE = (url: string, messageHandler: (event: MessageEvent) => void, options?: UseSSEOptions) => {
    const { connectDelay = 100, ...managerOptions } = options ?? {}
    const manager = new SSEManager(url, managerOptions)
    let connectTimer: ReturnType<typeof setTimeout> | null = null
    let isClosed = false
    let shouldListen = true
    let connectDelayElapsed = false

    const cleanup = () => {
      if (isClosed) return

      isClosed = true

      if (connectTimer) {
        clearTimeout(connectTimer)
        connectTimer = null
      }

      manager.destroy()
    }

    const startListening = () => {
      if (isClosed || !shouldListen) return

      manager.start(messageHandler)
    }

    const pause = () => {
      if (isClosed) return

      shouldListen = false
      manager.stop()
    }

    const resume = () => {
      if (isClosed) return

      shouldListen = true
      if (connectDelayElapsed) startListening()
    }

    onMounted(() => {
      // 延迟建立连接，确保组件完全挂载
      connectTimer = setTimeout(() => {
        connectTimer = null
        connectDelayElapsed = true
        startListening()
      }, connectDelay)
    })

    onUnmounted(cleanup)

    return {
      pause,
      resume,
    }
  }

  /**
   * 使用定时器
   * @param id 定时器ID
   * @param callback 回调函数
   * @param interval 间隔时间（毫秒）
   * @param options 选项
   */
  const useTimer = (
    id: string,
    callback: () => void,
    interval: number,
    options?: {
      runInBackground?: boolean
      skipInitialRun?: boolean
    },
  ) => {
    onMounted(() => {
      addBackgroundTimer(id, callback, interval, options)
    })

    onUnmounted(() => {
      removeBackgroundTimer(id)
    })

    return {
      remove: () => removeBackgroundTimer(id),
    }
  }

  /**
   * 使用延迟SSE连接（类似原来的setTimeout延迟）
   * @param url SSE连接地址
   * @param messageHandler 消息处理函数
   * @param delay 延迟时间（毫秒）
   * @param options SSE选项
   */
  const useDelayedSSE = (
    url: string,
    messageHandler: (event: MessageEvent) => void,
    delay: number = 3000,
    options?: SSEConnectionOptions,
  ) => {
    const manager = new SSEManager(url, options)
    let connectTimer: ReturnType<typeof setTimeout> | null = null
    let isClosed = false

    const cleanup = () => {
      if (isClosed) return

      isClosed = true

      if (connectTimer) {
        clearTimeout(connectTimer)
        connectTimer = null
      }

      manager.destroy()
    }

    onMounted(() => {
      connectTimer = setTimeout(() => {
        connectTimer = null
        if (isClosed) return

        manager.start(messageHandler)
      }, delay)
    })

    onUnmounted(cleanup)
  }

  /**
   * 使用进度SSE连接（用于进度监听）
   * @param url SSE连接地址
   * @param messageHandler 消息处理函数
   * @param isActive 是否激活的响应式变量
   */
  const useProgressSSE = (url: string, messageHandler: (event: MessageEvent) => void, isActive: Ref<boolean>) => {
    let manager: SSEManager | null = null

    const startProgress = () => {
      if (!isActive.value || manager) return

      manager = new SSEManager(url, {
        backgroundCloseDelay: 1000, // 进度SSE更快关闭
        reconnectDelay: 1000,
        maxReconnectAttempts: 5,
      })
      manager.start(messageHandler)
    }

    const stopProgress = () => {
      manager?.destroy()
      manager = null
    }

    // 进度监听有些场景会在用户操作后动态创建；只有 setup 阶段创建时才注册自动卸载钩子。
    if (getCurrentInstance()) {
      onUnmounted(stopProgress)
    }

    return {
      start: startProgress,
      stop: stopProgress,
    }
  }

  /**
   * 使用数据刷新定时器（用于仪表盘等数据刷新）
   * @param id 定时器ID
   * @param loadDataFunc 加载数据函数
   * @param interval 刷新间隔（毫秒）
   * @param immediate 是否立即执行
   */
  const useDataRefresh = (
    id: string,
    loadDataFunc: () => Promise<void> | void,
    interval: number = 3000,
    immediate: boolean = true,
  ) => {
    const loading = ref(false)
    let isMounted = false

    const wrappedLoadData = async () => {
      if (loading.value) return

      loading.value = true
      try {
        await loadDataFunc()
      } catch (error) {
        console.error(`数据刷新失败 [${id}]:`, error)
      } finally {
        loading.value = false
      }
    }

    onMounted(() => {
      isMounted = true

      void (async () => {
        if (immediate) {
          await wrappedLoadData()
        }

        // 初始请求较慢时组件可能已经卸载，卸载后的补注册会成为无人清理的常驻定时器。
        if (!isMounted) return

        addBackgroundTimer(id, wrappedLoadData, interval, {
          runInBackground: false, // 后台不刷新数据
          skipInitialRun: true, // 已经手动执行过了
        })
      })()
    })

    onUnmounted(() => {
      isMounted = false
      removeBackgroundTimer(id)
    })

    return {
      loading,
      refresh: wrappedLoadData,
      stop: () => removeBackgroundTimer(id),
    }
  }

  /**
   * 使用条件性数据刷新定时器（用于需要动态启停的场景）
   * @param id 定时器ID
   * @param loadDataFunc 加载数据函数
   * @param condition 条件响应式引用，为true时启动定时器
   * @param interval 刷新间隔（毫秒）
   * @param immediate 是否立即执行
   */
  const useConditionalDataRefresh = (
    id: string,
    loadDataFunc: () => Promise<void> | void,
    condition: Ref<boolean>,
    interval: number = 3000,
    immediate: boolean = true,
  ) => {
    const loading = ref(false)
    const isTimerActive = ref(false)

    const wrappedLoadData = async () => {
      if (loading.value || !condition.value) return

      loading.value = true
      try {
        await loadDataFunc()
      } catch (error) {
        console.error(`条件数据刷新失败 [${id}]:`, error)
      } finally {
        loading.value = false
      }
    }

    const startTimer = () => {
      if (!isTimerActive.value && condition.value) {
        addBackgroundTimer(id, wrappedLoadData, interval, {
          runInBackground: false,
          skipInitialRun: !immediate,
        })
        isTimerActive.value = true
      }
    }

    const stopTimer = () => {
      if (isTimerActive.value) {
        removeBackgroundTimer(id)
        isTimerActive.value = false
      }
    }

    onMounted(() => {
      if (condition.value) {
        startTimer()
      }

      // 监听条件变化
      watch(condition, (newValue: boolean) => {
        if (newValue) {
          startTimer()
        } else {
          stopTimer()
        }
      })
    })

    onUnmounted(() => {
      stopTimer()
    })

    return {
      loading,
      refresh: wrappedLoadData,
      stop: stopTimer,
      start: startTimer,
      isActive: isTimerActive,
    }
  }

  return {
    useSSE,
    useTimer,
    useDelayedSSE,
    useProgressSSE,
    useDataRefresh,
    useConditionalDataRefresh,
  }
}
