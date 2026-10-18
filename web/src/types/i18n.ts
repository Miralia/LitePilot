/**
 * 语言相关信息。
 *
 * 本分支只维护简体中文，保留该结构以便既有引用点无需改动。
 */
export interface LocaleInfo {
  name: string
  title: string
  flag?: string
}

export const SUPPORTED_LOCALES: Record<string, LocaleInfo> = {
  'zh-CN': {
    name: 'zh-CN',
    title: '简体中文',
    flag: '🇨🇳',
  },
}

export type SupportedLocale = keyof typeof SUPPORTED_LOCALES
