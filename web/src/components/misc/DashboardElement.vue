<script setup lang="ts">
import { h, nextTick, onUnmounted, provide, ref, resolveComponent, watch } from 'vue'
import { PropType } from 'vue'
import { DashboardItem } from '@/api/types'
import { useToast } from 'vue-toastification'

type DashboardComponentLoader = () => Promise<any>

// 仪表板联邦组件复用主应用 Toast 实例。
const $toast = useToast()
provide('moviepilot:toast', $toast)

const DashboardSkeleton = {
  // 创建无需模板编译的仪表板加载骨架。
  setup() {
    const SkeletonLoader = resolveComponent('VSkeletonLoader')

    // 用 render 函数避免 runtime-only Vue 为异步 loadingComponent 解析模板。
    return () => h(SkeletonLoader, { type: 'card' })
  },
}

const asyncDashboardOptions = {
  loadingComponent: DashboardSkeleton,
}

// 内置仪表盘组件加载器（插件仪表板随插件体系删除，不再有远程组件渲染）
const builtInDashboardComponentLoaders: Record<string, DashboardComponentLoader> = {
  storage: () => import('@/views/dashboard/AnalyticsStorage.vue'),
  mediaStatistic: () => import('@/views/dashboard/AnalyticsMediaStatistic.vue'),
  weeklyOverview: () => import('@/views/dashboard/AnalyticsWeeklyOverview.vue'),
  speed: () => import('@/views/dashboard/AnalyticsSpeed.vue'),
  scheduler: () => import('@/views/dashboard/AnalyticsScheduler.vue'),
  cpu: () => import('@/views/dashboard/AnalyticsCpu.vue'),
  memory: () => import('@/views/dashboard/AnalyticsMemory.vue'),
  network: () => import('@/views/dashboard/AnalyticsNetwork.vue'),
  library: () => import('@/views/dashboard/MediaServerLibrary.vue'),
  playing: () => import('@/views/dashboard/MediaServerPlaying.vue'),
  latest: () => import('@/views/dashboard/MediaServerLatest.vue'),
  recentImports: () => import('@/views/dashboard/DashboardRecentImports.vue'),
  quickActions: () => import('@/views/dashboard/DashboardQuickActions.vue'),
  systemInfo: () => import('@/views/dashboard/DashboardSystemInfo.vue'),
}

const builtInDashboardComponentPromises = new Map<string, Promise<any>>()

// 复用内置仪表盘组件加载 Promise，让页面层可以等待异步组件模块真正加载完成。
function loadBuiltInDashboardComponent(id: string) {
  const loader = builtInDashboardComponentLoaders[id]
  if (!loader) return Promise.resolve()

  let loadPromise = builtInDashboardComponentPromises.get(id)
  if (!loadPromise) {
    loadPromise = loader().catch(error => {
      builtInDashboardComponentPromises.delete(id)
      throw error
    })
    builtInDashboardComponentPromises.set(id, loadPromise)
  }

  return loadPromise
}

// 创建内置仪表盘异步组件，并与加载完成上报共享同一份加载 Promise。
function createAsyncDashboardComponent(id: string) {
  return defineAsyncComponent({
    loader: () => loadBuiltInDashboardComponent(id),
    ...asyncDashboardOptions,
  })
}

// 内置仪表盘按需加载，关闭的卡片不再挤进 dashboard 首屏 chunk。
const AnalyticsStorage = createAsyncDashboardComponent('storage')
const AnalyticsMediaStatistic = createAsyncDashboardComponent('mediaStatistic')
const AnalyticsWeeklyOverview = createAsyncDashboardComponent('weeklyOverview')
const AnalyticsSpeed = createAsyncDashboardComponent('speed')
const AnalyticsScheduler = createAsyncDashboardComponent('scheduler')
const AnalyticsCpu = createAsyncDashboardComponent('cpu')
const AnalyticsMemory = createAsyncDashboardComponent('memory')
const AnalyticsNetwork = createAsyncDashboardComponent('network')
const MediaServerLibrary = createAsyncDashboardComponent('library')
const MediaServerPlaying = createAsyncDashboardComponent('playing')
const MediaServerLatest = createAsyncDashboardComponent('latest')
const DashboardRecentImports = createAsyncDashboardComponent('recentImports')
const DashboardQuickActions = createAsyncDashboardComponent('quickActions')
const DashboardSystemInfo = createAsyncDashboardComponent('systemInfo')

// 输入参数
const props = defineProps({
  // 仪表板配置
  config: Object as PropType<DashboardItem>,
  // 刷新状态
  refreshStatus: Boolean,
  // 是否允许刷新数据
  allowRefresh: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits(['update:refreshStatus', 'loaded'])

// 当前仪表盘节点是否已经向页面层报告过加载完成。
const isDashboardElementLoaded = ref(false)

let isDashboardElementUnmounted = false
let dashboardLoadGeneration = 0

// 判断当前配置是否对应内置异步仪表盘组件。
function isBuiltInDashboardElement() {
  return !!props.config?.id && !!builtInDashboardComponentLoaders[props.config.id]
}

// 向页面层上报当前仪表盘节点已完成首次组件加载。
function emitDashboardElementLoaded() {
  if (isDashboardElementLoaded.value || isDashboardElementUnmounted) return

  isDashboardElementLoaded.value = true
  emit('loaded')
}

// 等待当前仪表盘节点的异步组件加载完成。
async function waitForDashboardElementLoaded(generation: number) {
  if (isDashboardElementLoaded.value) return

  try {
    if (isBuiltInDashboardElement() && props.config?.id) {
      await loadBuiltInDashboardComponent(props.config.id)
    }

    await nextTick()
  } catch (error) {
    console.error(error)
  } finally {
    if (generation === dashboardLoadGeneration) emitDashboardElementLoaded()
  }
}

watch(
  () => [props.config?.id, props.config?.key],
  () => {
    isDashboardElementLoaded.value = false
    dashboardLoadGeneration += 1
    void waitForDashboardElementLoaded(dashboardLoadGeneration)
  },
  { immediate: true },
)

onUnmounted(() => {
  isDashboardElementUnmounted = true
  // 组件卸载时禁用刷新状态
  emit('update:refreshStatus', false)
})
</script>
<template>
  <!-- 系统内置的仪表板 -->
  <AnalyticsStorage v-if="config?.id === 'storage'" />
  <AnalyticsMediaStatistic v-else-if="config?.id === 'mediaStatistic'" />
  <AnalyticsWeeklyOverview v-else-if="config?.id === 'weeklyOverview'" />
  <AnalyticsSpeed v-else-if="config?.id === 'speed'" :allowRefresh="props.allowRefresh" />
  <AnalyticsScheduler v-else-if="config?.id === 'scheduler'" :allowRefresh="props.allowRefresh" />
  <AnalyticsCpu v-else-if="config?.id === 'cpu'" :allowRefresh="props.allowRefresh" />
  <AnalyticsMemory v-else-if="config?.id === 'memory'" :allowRefresh="props.allowRefresh" />
  <AnalyticsNetwork v-else-if="config?.id === 'network'" :allowRefresh="props.allowRefresh" />
  <MediaServerLibrary v-else-if="config?.id === 'library'" />
  <MediaServerPlaying v-else-if="config?.id === 'playing'" />
  <MediaServerLatest v-else-if="config?.id === 'latest'" />
  <DashboardRecentImports v-else-if="config?.id === 'recentImports'" />
  <DashboardQuickActions v-else-if="config?.id === 'quickActions'" />
  <DashboardSystemInfo v-else-if="config?.id === 'systemInfo'" :allow-refresh="props.allowRefresh" />
</template>

<style scoped>
/* stylelint-disable selector-pseudo-class-no-unknown */
</style>