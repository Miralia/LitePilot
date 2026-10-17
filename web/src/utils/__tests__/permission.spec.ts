import {
  ADMIN_PERMISSIONS,
  buildDefaultFeaturePermissions,
  buildUserPermissionContext,
  DEFAULT_PERMISSIONS,
  filterItemsByPermission,
  filterMenusByPermission,
  hasAllPermissions,
  hasAnyPermission,
  hasFeaturePermission,
  hasItemPermission,
  hasPermission,
  normalizeUserPermissions,
  PERMISSION_FEATURE,
  USER_PERMISSION_FEATURES,
  type UserPermissionFeatureMap,
} from '@/utils/permission'
import { describe, expect, it } from 'vitest'

describe('permission utilities', () => {
  it('normalizes legacy permissions and filters invalid feature values', () => {
    const normalized = normalizeUserPermissions({
      manage: true,
      features: {
        enabled: true,
        invalid: 'yes',
      } as unknown as UserPermissionFeatureMap,
    })

    expect(normalized).toEqual({
      ...DEFAULT_PERMISSIONS,
      manage: true,
      features: { enabled: true },
    })
    expect(normalizeUserPermissions(null)).toEqual(DEFAULT_PERMISSIONS)
  })

  it('builds default and plugin feature contracts', () => {
    const disabledFeatures = buildDefaultFeaturePermissions(false)

    expect(Object.keys(disabledFeatures)).toHaveLength(USER_PERMISSION_FEATURES.length)
    expect(Object.values(disabledFeatures).every(enabled => enabled === false)).toBe(true)
    expect(ADMIN_PERMISSIONS.features?.[PERMISSION_FEATURE.MANAGE_HISTORY]).toBe(true)
  })

  it('grants every category and admin entry only to superusers', () => {
    const superuser = buildUserPermissionContext(true, {})

    expect(hasPermission(superuser, 'admin')).toBe(true)
    expect(hasPermission(superuser, 'manage')).toBe(true)
    expect(hasFeaturePermission(superuser, PERMISSION_FEATURE.MANAGE_HISTORY, 'manage')).toBe(true)
    expect(hasPermission({ admin: true, manage: true }, 'admin')).toBe(false)
  })

  it('checks category permissions as explicit booleans', () => {
    const permissions = { manage: true, unknown: 1 }

    expect(hasPermission(permissions, 'manage')).toBe(true)
    expect(hasPermission(null, 'manage')).toBe(false)
    expect(hasAnyPermission(null, ['manage'])).toBe(false)
    expect(hasAllPermissions(permissions, ['manage'])).toBe(true)
  })

  it('inherits missing feature flags but honors explicit denial and parent categories', () => {
    const legacyUser = { manage: true }
    const restrictedUser = {
      manage: true,
      features: { [PERMISSION_FEATURE.MANAGE_HISTORY]: false },
    }

    expect(hasFeaturePermission(legacyUser)).toBe(true)
    expect(hasFeaturePermission(legacyUser, PERMISSION_FEATURE.MANAGE_HISTORY, 'manage')).toBe(true)
    expect(hasFeaturePermission(restrictedUser, PERMISSION_FEATURE.MANAGE_HISTORY, 'manage')).toBe(false)
    expect(
      hasFeaturePermission(
        { manage: false, features: { [PERMISSION_FEATURE.MANAGE_HISTORY]: true } },
        PERMISSION_FEATURE.MANAGE_HISTORY,
        'manage',
      ),
    ).toBe(false)
  })

  it('checks and filters permission-protected items consistently', () => {
    const permissions = {
      manage: true,
      features: { [PERMISSION_FEATURE.MANAGE_FILEMANAGER]: false },
    }
    const items = [
      { id: 'open' },
      { id: 'history', permission: 'manage' as const, feature: PERMISSION_FEATURE.MANAGE_HISTORY },
      { id: 'filemanager', permission: 'manage' as const, feature: PERMISSION_FEATURE.MANAGE_FILEMANAGER },
    ]

    expect(hasItemPermission(items[1], permissions)).toBe(true)
    expect(hasItemPermission(items[2], permissions)).toBe(false)
    expect(filterItemsByPermission(items, permissions).map(item => item.id)).toEqual(['open', 'history'])
    expect(filterMenusByPermission(items, permissions).map(item => item.id)).toEqual(['open', 'history'])
  })
})
