import { createI18n } from 'vue-i18n'

// 本分支只维护简体中文：组件继续使用 t() 取文案，但不提供多语言切换，
// 避免每新增一个功能都要同步维护多份翻译。
import zhCN from '@/locales/zh-CN'

const LOCALE = 'zh-CN'

const i18n = createI18n({
  legacy: false,
  locale: LOCALE,
  fallbackLocale: LOCALE,
  messages: {
    'zh-CN': zhCN,
  },
  silentTranslationWarn: true,
  silentFallbackWarn: true,
})

// 保证 html lang 与实际语言一致，便于浏览器排版与无障碍工具识别
document.querySelector('html')?.setAttribute('lang', LOCALE)

/**
 * 获取当前语言。
 *
 * 本分支固定为简体中文，保留该函数以兼容既有调用点。
 */
export function getCurrentLocale(): string {
  return LOCALE
}

export default i18n
