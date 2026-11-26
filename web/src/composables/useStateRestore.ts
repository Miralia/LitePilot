/**
 * 动态标签页状态恢复组合式 API。
 */

import { ref, onMounted, watch, inject } from 'vue'
import { useRoute } from 'vue-router'
import type { StateRestore } from '@/plugins/stateRestore'

/**
 * 自动保存和恢复 v-tabs 的当前激活标签。
 */
export function useTabStateRestore(defaultTab?: string) {
  const route = useRoute()
  const stateRestore = inject<StateRestore>('stateRestore')

  const activeTab = ref<string>(defaultTab || '')

  // 保存标签页状态
  const saveTabState = (tab: string) => {
    if (stateRestore && tab) {
      stateRestore.tab.saveTabState(route.path, tab)
    }
  }

  // 恢复标签页状态
  const restoreTabState = () => {
    if (stateRestore) {
      const savedTab = stateRestore.tab.getTabState(route.path)
      if (savedTab) {
        activeTab.value = savedTab
        return true
      }
    }
    return false
  }

  // 监听activeTab变化，自动保存
  watch(activeTab, newTab => {
    if (newTab) {
      saveTabState(newTab)
    }
  })

  // 组件挂载时恢复状态（仅在首次加载时）
  onMounted(() => {
    // 先尝试恢复，如果没有保存的状态则使用默认值
    if (!restoreTabState() && defaultTab) {
      activeTab.value = defaultTab
    }
  })

  return {
    activeTab,
    saveTabState,
    restoreTabState,
  }
}
