/**
 * PWA 标签页状态恢复插件。
 * 只保留 HeaderTab 实际使用的激活标签恢复能力。
 */

import type { App } from 'vue'

interface TabState {
  activeTab: string
  timestamp: number
}

class TabStateManager {
  private readonly STORAGE_KEY = 'pwa-active-tabs'

  // 保存标签页状态
  saveTabState(routePath: string, activeTab: string) {
    try {
      const allTabs = this.getAllTabStates()
      allTabs[routePath] = {
        activeTab,
        timestamp: Date.now(),
      }
      sessionStorage.setItem(this.STORAGE_KEY, JSON.stringify(allTabs))
    } catch (error) {
      console.warn('保存标签页状态失败:', error)
    }
  }

  // 获取标签页状态
  getTabState(routePath: string): string | null {
    try {
      const allTabs = this.getAllTabStates()
      const tabState = allTabs[routePath]

      if (!tabState) return null

      // 检查是否过期（1小时）
      if (Date.now() - tabState.timestamp > 60 * 60 * 1000) {
        delete allTabs[routePath]
        sessionStorage.setItem(this.STORAGE_KEY, JSON.stringify(allTabs))
        return null
      }

      return tabState.activeTab
    } catch {
      return null
    }
  }

  // 获取所有标签页状态
  private getAllTabStates(): Record<string, TabState> {
    try {
      const saved = sessionStorage.getItem(this.STORAGE_KEY)
      return saved ? JSON.parse(saved) : {}
    } catch {
      return {}
    }
  }
}

class StateRestore {
  public tab = new TabStateManager()
}

const stateRestore = new StateRestore()

export default {
  install(app: App) {
    app.provide('stateRestore', stateRestore)
  },
}

// 导出管理器实例
export { stateRestore }

// 导出类型
export type { TabStateManager, StateRestore }
