/**
 * 静态资源导入工具函数
 * 用于在生产环境中正确引用静态资源
 */

// 导入所有 logo 图标
import qbittorrentLogo from '@/assets/images/logos/qbittorrent.png'
import embyLogo from '@/assets/images/logos/emby.png'
import telegramLogo from '@/assets/images/logos/telegram.webp'
import downloaderLogo from '@/assets/images/logos/downloader.png'
import mediaserverLogo from '@/assets/images/logos/mediaserver.png'
import notificationLogo from '@/assets/images/logos/notification.png'
import githubLogo from '@/assets/images/logos/github.png'
import tmdbLogo from '@/assets/images/logos/tmdb.png'
import bangumiLogo from '@/assets/images/logos/bangumi.png'
import pythonLogo from '@/assets/images/logos/python.png'

// 图标映射表
const logoMap: Record<string, string> = {
  qbittorrent: qbittorrentLogo,
  emby: embyLogo,
  telegram: telegramLogo,
  downloader: downloaderLogo,
  mediaserver: mediaserverLogo,
  notification: notificationLogo,
  github: githubLogo,
  tmdb: tmdbLogo,
  bangumi: bangumiLogo,
  python: pythonLogo,
}

/**
 * 获取图标 URL
 * @param logoName 图标名称
 * @returns 图标的 URL
 */
export function getLogoUrl(logoName: string): string {
  return logoMap[logoName] || ''
}

/**
 * 判断是否为需要强制走后端代理的 Bangumi 图片。
 * @param url 图片地址
 * @returns 是否为 Bangumi 图片地址
 */
export function isBangumiImageUrl(url: string): boolean {
  if (!url) return false
  try {
    const hostname = new URL(url).hostname.toLowerCase()
    return hostname === 'lain.bgm.tv' || hostname.endsWith('.lain.bgm.tv')
  } catch {
    return url.includes('lain.bgm.tv')
  }
}

/**
 * 将远程图片地址转换为前端可直接展示的地址。
 * @param url 原始图片地址
 * @param useCache 是否使用后端图片缓存
 * @returns 转换后的图片地址
 */
export function getDisplayImageUrl(url: string, useCache = false): string {
  if (!url || !/^https?:\/\//i.test(url)) return url
  const encodedUrl = encodeURIComponent(url)
  if (isBangumiImageUrl(url))
    return `${import.meta.env.VITE_API_BASE_URL}system/img/1?imgurl=${encodedUrl}${useCache ? '&cache=true' : ''}`
  if (useCache) return `${import.meta.env.VITE_API_BASE_URL}system/cache/image?url=${encodedUrl}`
  if (url.includes('doubanio.com')) return `${import.meta.env.VITE_API_BASE_URL}system/img/0?imgurl=${encodedUrl}`
  return url
}
