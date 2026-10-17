// 权限类型定义
export type UserPermissionCategoryKey = 'manage'
export type UserPermissionKey = UserPermissionCategoryKey | 'admin'
export type UserPermissionFeatureKey = string
export type UserPermissionFeatureMap = Record<UserPermissionFeatureKey, boolean>

export interface UserPermissionFeatureOption {
  key: UserPermissionFeatureKey
  permission: UserPermissionCategoryKey
  titleKey: string
  descriptionKey: string
  icon: string
  path?: string
}

export interface UserPermissions {
  manage: boolean // 管理权限
  admin?: boolean // 管理员权限，仅用于前端入口标识，实际由 is_superuser 决定
  features?: UserPermissionFeatureMap // 功能级权限，缺省功能默认继承分类权限
}

export type UserPermissionContext = UserPermissions & { is_superuser?: boolean; [key: string]: unknown }
export type PermissionProtectedItem = { permission?: UserPermissionKey; feature?: UserPermissionFeatureKey }

export const PERMISSION_FEATURE = {
  MANAGE_HISTORY: 'manage.history',
  MANAGE_FILEMANAGER: 'manage.filemanager',
} as const

export const USER_PERMISSION_FEATURES: UserPermissionFeatureOption[] = [
  {
    key: PERMISSION_FEATURE.MANAGE_HISTORY,
    permission: 'manage',
    titleKey: 'dialog.userAddEdit.permissions.features.history',
    descriptionKey: 'dialog.userAddEdit.permissions.featureDescriptions.history',
    icon: 'mdi-folder-play-outline',
    path: '/history',
  },
  {
    key: PERMISSION_FEATURE.MANAGE_FILEMANAGER,
    permission: 'manage',
    titleKey: 'dialog.userAddEdit.permissions.features.fileManager',
    descriptionKey: 'dialog.userAddEdit.permissions.featureDescriptions.fileManager',
    icon: 'mdi-folder-multiple-outline',
    path: '/filemanager',
  },
]

/** 构造功能级权限默认值，新建用户默认不收窄已拥有的分类权限。 */
export function buildDefaultFeaturePermissions(enabled = true): UserPermissionFeatureMap {
  return Object.fromEntries(USER_PERMISSION_FEATURES.map(feature => [feature.key, enabled]))
}

/** 判断传入值是否为可安全读取的普通对象。 */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** 规整用户权限数据，兼容没有 features 字段的历史用户。 */
export function normalizeUserPermissions(permissions: Partial<UserPermissions> | null | undefined = {}): UserPermissions {
  const permissionData = permissions ?? {}
  const rawFeatures = isRecord(permissionData.features) ? permissionData.features : {}
  const features = Object.fromEntries(
    Object.entries(rawFeatures).filter(([, value]) => typeof value === 'boolean'),
  ) as UserPermissionFeatureMap

  return {
    manage: permissionData.manage ?? DEFAULT_PERMISSIONS.manage,
    admin: permissionData.admin ?? DEFAULT_PERMISSIONS.admin,
    features,
  }
}

/** 构造权限检查上下文，统一超级管理员标记、分类权限与功能权限字段。 */
export function buildUserPermissionContext(isSuperuser: boolean, permissions: Partial<UserPermissions> = {}): UserPermissionContext {
  return {
    is_superuser: isSuperuser,
    ...normalizeUserPermissions(permissions),
  }
}

// 默认权限配置
export const DEFAULT_PERMISSIONS: UserPermissions = {
  manage: false,
  admin: false,
  features: {},
}

// 管理员权限配置
export const ADMIN_PERMISSIONS: UserPermissions = {
  manage: true,
  admin: true,
  features: buildDefaultFeaturePermissions(),
}

/** 检查用户是否拥有指定权限分类。 */
export function hasPermission(userPermissions: any, permission: UserPermissionKey): boolean {
  // 如果用户是超级用户，拥有所有权限
  if (userPermissions?.is_superuser === true) {
    return true
  }

  // admin 入口只允许超级管理员，不从普通用户 permissions 字段放行
  if (permission === 'admin') {
    return false
  }

  // 检查具体权限
  const permissions = userPermissions || {}
  return permissions[permission] === true
}

/** 检查用户是否拥有指定功能权限，缺省功能项默认放行以兼容历史数据。 */
export function hasFeaturePermission(
  userPermissions: any,
  feature?: UserPermissionFeatureKey,
  permission?: UserPermissionKey,
): boolean {
  if (!feature) {
    return true
  }

  if (userPermissions?.is_superuser === true) {
    return true
  }

  if (permission && !hasPermission(userPermissions, permission)) {
    return false
  }

  const features = isRecord(userPermissions?.features) ? userPermissions.features : {}
  return features[feature] !== false
}

/** 批量检查是否拥有任一权限分类。 */
export function hasAnyPermission(userPermissions: any, permissionList: UserPermissionKey[]): boolean {
  return permissionList.some(permission => hasPermission(userPermissions, permission))
}

/** 批量检查是否拥有全部权限分类。 */
export function hasAllPermissions(userPermissions: any, permissionList: UserPermissionKey[]): boolean {
  return permissionList.every(permission => hasPermission(userPermissions, permission))
}

/** 统一检查带 permission / feature 字段的入口，避免菜单、按钮、快捷入口各自实现判断。 */
export function hasItemPermission(item: PermissionProtectedItem, userPermissions: any): boolean {
  if (item.permission && !hasPermission(userPermissions, item.permission)) {
    return false
  }

  return hasFeaturePermission(userPermissions, item.feature, item.permission)
}

/** 根据权限过滤带 permission / feature 字段的入口。 */
export function filterItemsByPermission<T extends PermissionProtectedItem>(items: T[], userPermissions: any): T[] {
  return items.filter(item => hasItemPermission(item, userPermissions))
}

/** 根据权限过滤菜单项。 */
export function filterMenusByPermission(menus: any[], userPermissions: any): any[] {
  return filterItemsByPermission(menus, userPermissions)
}
