import copy from 'copy-to-clipboard'

// 将内容复制到剪贴板
export async function copyToClipboard(content: string) {
  const success = copy(content)
  return success
}

// 判断是否为PWA
const isPWA = async (): Promise<boolean> => {
  if ('serviceWorker' in navigator) {
    const registrations = await navigator.serviceWorker.getRegistrations()
    return registrations.length > 0
  }
  return (window.navigator as any).standalone === true
}

// 同步检测PWA显示模式
export const isPWADisplayMode = (): boolean => {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    (window.navigator as any).standalone ||
    document.referrer.includes('android-app://')
  )
}

// 全面的PWA检测（推荐使用）
export const checkPWAStatus = async () => {
  const hasServiceWorker = await isPWA()
  const isStandaloneMode = isPWADisplayMode()

  return {
    // 是否有PWA功能（Service Worker）
    hasPWAFeatures: hasServiceWorker,
    // 是否在独立显示模式下运行
    isStandaloneMode,
    // 综合判断：更宽松的检测，在移动设备上默认启用PWA功能
    isPWAEnvironment: hasServiceWorker || isStandaloneMode || isMobileDevice(),
    // 完整的PWA体验：既有功能又在独立模式下运行
    isFullPWA: hasServiceWorker && isStandaloneMode,
  }
}

// 检测是否为移动设备
export const isMobileDevice = (): boolean => {
  // 检查用户代理字符串
  const userAgent = navigator.userAgent || ''
  const mobileRegex = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|mobile|CriOS/i

  // 检查触摸屏支持
  const hasTouchScreen = 'ontouchstart' in window || navigator.maxTouchPoints > 0

  // 检查屏幕尺寸（小于768px认为是移动设备）
  const isMobileSize = window.innerWidth < 768

  return mobileRegex.test(userAgent) || hasTouchScreen || isMobileSize
}

// 检测是否为iOS设备
export const isIOSDevice = (): boolean => {
  const userAgent = navigator.userAgent.toLowerCase()
  return /iphone|ipad|ipod/.test(userAgent) && !(window as any).MSStream
}

// 检测是否为Android设备
export const isAndroidDevice = (): boolean => {
  const userAgent = navigator.userAgent.toLowerCase()
  return /android/.test(userAgent)
}
