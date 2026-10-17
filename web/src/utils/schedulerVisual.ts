import type { ScheduleInfo } from '@/api/types'

// 定时服务在捷径和仪表板中共用的视觉配置。
export type SchedulerVisual = {
  color: string
  icon: string
  rgb: string
}

// 已知定时服务的视觉匹配规则。
type SchedulerVisualRule = SchedulerVisual & {
  ids?: string[]
  names?: string[]
  providers?: string[]
}

const schedulerVisualRules: SchedulerVisualRule[] = [
  { ids: ['mediaserver_sync'], names: ['媒体服务器'], icon: 'mdi-television-play', color: '#42c336', rgb: '66, 195, 54' },
  { ids: ['transfer'], names: ['下载文件整理', '文件整理'], icon: 'mdi-folder-move-outline', color: '#3f8cff', rgb: '63, 140, 255' },
  { ids: ['random_wallpager'], names: ['壁纸'], icon: 'mdi-image-outline', color: '#9b6cf3', rgb: '155, 108, 243' },
  { ids: ['scheduler_job'], names: ['公共定时服务'], icon: 'mdi-clock-outline', color: '#42c336', rgb: '66, 195, 54' },
  { ids: ['clear_cache'], names: ['缓存清理'], icon: 'mdi-delete-sweep-outline', color: '#ffad1f', rgb: '255, 173, 31' },
  { ids: ['data_cleanup'], names: ['数据表清理'], icon: 'mdi-database-remove-outline', color: '#ff704d', rgb: '255, 112, 77' },
  { ids: ['full_gc'], names: ['内存回收'], icon: 'mdi-memory', color: '#25b6c8', rgb: '37, 182, 200' },
]

const schedulerFallbackVisual: SchedulerVisual = {
  icon: 'mdi-timer-cog-outline',
  color: '#25b6c8',
  rgb: '37, 182, 200',
}

/** 判断视觉规则中的任一文本是否命中任务信息。 */
function hasSchedulerRuleMatch(values: string[] | undefined, target: string) {
  if (!values?.length) return false

  return values.some(value => target.includes(value.toLocaleLowerCase()))
}

/** 使用任务 ID、名称和提供者返回统一的定时服务图标与主题色。 */
export function getSchedulerVisual(scheduler: ScheduleInfo): SchedulerVisual {
  const schedulerId = (scheduler.id || '').toLocaleLowerCase()
  const schedulerName = (scheduler.name || '').toLocaleLowerCase()
  const schedulerProvider = (scheduler.provider || '').toLocaleLowerCase()
  const matchedRule = schedulerVisualRules.find(rule => {
    return (
      hasSchedulerRuleMatch(rule.ids, schedulerId) ||
      hasSchedulerRuleMatch(rule.names, schedulerName) ||
      hasSchedulerRuleMatch(rule.providers, schedulerProvider)
    )
  })

  return matchedRule ?? schedulerFallbackVisual
}
