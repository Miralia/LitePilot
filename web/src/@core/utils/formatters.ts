import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import ZH_CN from 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale(ZH_CN)

// 格式化为xx[TGMK]B
export function formatFileSize(bytes: number, decimals = 2, prefix = false) {
  // 负数标记
  let negative = false
  let size = bytes
  if (bytes < 0) {
    negative = true
    size = Math.abs(bytes)
  }

  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let unitIndex = 0

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  if (negative) return `-${size.toFixed(decimals)} ${units[unitIndex]}`
  else
    return prefix ? `+${size.toFixed(decimals)} ${units[unitIndex]}` : `${size.toFixed(decimals)} ${units[unitIndex]}`
}

// 文件大小格式化
export function formatBytes(bytes: number, decimals = 2) {
  if (bytes === 0) return '0 bytes'

  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']

  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return `${Number.parseFloat((bytes / k ** i).toFixed(dm))} ${sizes[i]}`
}

// 将yyyy-mm-dd hh:mm:ss转换为时间差，如：1小时前，1天前
export function formatDateDifference(dateString: string): string {
  if (!dateString) return ''
  return dayjs(dateString).fromNow()
}
