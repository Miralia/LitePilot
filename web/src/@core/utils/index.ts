export function isNullOrEmptyObject(obj: any): boolean {
  // 首先判断是否为 null 或 undefined
  if (obj === null || obj === undefined) return true

  // 然后判断是否为空对象
  return !!(typeof obj === 'object' && Object.keys(obj).length === 0)
}

// 判断系统配置色是否是黑暗的
export function checkPrefersColorSchemeIsDark(): boolean {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  } catch (e) {
    return false
  }
}

// 从URL中获取参数值
export function getQueryValue(key: string, url = window.location.href): string {
  const reg = new RegExp(`[?&]${key}=([^&#]*)`, 'i')
  const res = reg.exec(url)
  return res ? res[1] : ''
}

// 导出 navigator 相关函数
export { isMobileDevice, isIOSDevice, isAndroidDevice } from './navigator'
