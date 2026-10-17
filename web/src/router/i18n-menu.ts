import { useGlobalSettingsStore } from '@/stores'
import type { NavMenu, NavMenuTabItem } from '@/@layouts/types'
import type { Composer } from 'vue-i18n'
import { PERMISSION_FEATURE } from '@/utils/permission'

/** 构建当前语言与全局模式对应的主导航菜单。 */
export function getNavMenus(t: Composer['t']): NavMenu[] {
  const globalSettingsStore = useGlobalSettingsStore()

  // 检查是否为高级模式
  const isAdvancedMode = globalSettingsStore.get('ADVANCED_MODE') !== false

  return [
    {
      title: t('navItems.dashboard'),
      icon: 'mdi-home-outline',
      iconColor: 'primary',
      to: '/dashboard',
      header: t('menu.start'),
      admin: false,
      footer: true,
      permission: 'admin',
    },
    {
      title: t('navItems.mediaOrganize'),
      icon: 'mdi-folder-play-outline',
      iconColor: 'warning',
      to: '/history',
      header: t('menu.organize'),
      admin: true,
      permission: 'manage',
      feature: PERMISSION_FEATURE.MANAGE_HISTORY,
    },
    {
      title: t('navItems.fileManager'),
      icon: 'mdi-folder-multiple-outline',
      iconColor: 'success',
      to: '/filemanager',
      header: t('menu.organize'),
      admin: true,
      permission: 'manage',
      feature: PERMISSION_FEATURE.MANAGE_FILEMANAGER,
    },
    ...(isAdvancedMode
      ? [
          {
            title: t('navItems.settings'),
            icon: 'mdi-cog-outline',
            iconColor: 'secondary',
            to: '/setting',
            header: t('menu.system'),
            admin: true,
            permission: 'admin',
            tabs: getSettingTabs(t),
          } as NavMenu,
        ]
      : []),
  ]
}

/** 返回系统设置页的配置标签。 */
export function getSettingTabs(t: Composer['t']): NavMenuTabItem[] {
  return [
    {
      title: t('settingTabs.system.title'),
      icon: 'mdi-server-network',
      tab: 'system',
      description: t('settingTabs.system.description'),
    },
    {
      title: t('settingTabs.directory.title'),
      icon: 'mdi-folder',
      tab: 'directory',
      description: t('settingTabs.directory.description'),
    },
    {
      title: t('settingTabs.notification.title'),
      icon: 'mdi-bell',
      tab: 'notification',
      description: t('settingTabs.notification.description'),
    },
  ]
}
