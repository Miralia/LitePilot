import i18n from '@/plugins/i18n'

export const storageAttributes = [
  {
    type: 'local',
    icon: 'mdi-folder-multiple-outline',
    remote: false,
  },
  {
    type: 'alipan',
    icon: 'mdi-cloud-outline',
    remote: true,
  },
  {
    type: 'u115',
    icon: 'mdi-cloud-outline',
    remote: true,
  },
  {
    type: 'rclone',
    icon: 'mdi-server-network-outline',
    remote: true,
  },
  {
    type: 'alist',
    icon: 'mdi-server-network-outline',
    remote: true,
  },
  {
    type: 'alistgo',
    icon: 'mdi-server-network-outline',
    remote: true,
  },
  {
    type: 'smb',
    icon: 'mdi-folder-network-outline',
    remote: true,
  },
]

export const storageIconDict = storageAttributes.reduce((dict, item) => {
  dict[item.type] = item.icon
  return dict
}, {} as Record<string, string>)

export const storageRemoteDict = storageAttributes.reduce((dict, item) => {
  dict[item.type] = item.remote
  return dict
}, {} as Record<string, boolean>)

export const downloaderOptions = [
  {
    value: 'qbittorrent',
    title: i18n.global.t('setting.system.qbittorrent'),
  },
]

export const downloaderDict = downloaderOptions.reduce((dict, item) => {
  dict[item.value] = item.title
  return dict
}, {} as Record<string, string>)

export const mediaServerOptions = [
  {
    value: 'emby',
    title: i18n.global.t('setting.system.emby'),
  },
]

export const mediaServerDict = mediaServerOptions.reduce((dict, item) => {
  dict[item.value] = item.title
  return dict
}, {} as Record<string, string>)

export const transferTypeOptions = [
  { title: i18n.global.t('transferType.copy'), value: 'copy' },
  { title: i18n.global.t('transferType.move'), value: 'move' },
  { title: i18n.global.t('transferType.link'), value: 'link' },
  { title: i18n.global.t('transferType.softlink'), value: 'softlink' },
]

// 分辨率选择框数据
// 媒体类型选项
// 媒体类型字典
// 通知开关选项
export const notificationSwitchOptions = [
  {
    title: i18n.global.t('notificationSwitch.resourceDownload'),
    value: '资源下载',
  },
  {
    title: i18n.global.t('notificationSwitch.organize'),
    value: '整理入库',
  },
  {
    title: i18n.global.t('notificationSwitch.mediaServer'),
    value: '媒体服务器',
  },
  {
    title: i18n.global.t('notificationSwitch.manual'),
    value: '手动处理',
  },
  {
    title: i18n.global.t('notificationSwitch.other'),
    value: '其它',
  },
]

// 通知开关字典
export const notificationSwitchDict = notificationSwitchOptions.reduce((dict, item) => {
  dict[item.value] = item.title
  return dict
}, {} as Record<string, string>)

// 操作步骤选项
// 操作步骤字典
