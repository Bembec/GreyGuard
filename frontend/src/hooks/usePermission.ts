import { useAuth, type Administrator } from "../context/AuthContext"

export type PermissionCheck =
  | { role: Administrator["role"] }
  | { anyRole: Administrator["role"][] }
  | { permission: string }
  | { anyPermission: string[] }
  | { installOperator: true }

/**
 * Plain (non-hook) matcher, so a list of items can be permission-filtered in a .map()/.filter()
 * without calling the usePermission hook once per item - hooks cannot be called inside loops
 * or callbacks. A missing check always passes (matches today's nav-filtering convention: an
 * item with no requiredRole is visible to everyone). `administrator` being null always fails a
 * real check - there is no identity to evaluate against.
 */
export function matchesPermission(administrator: Administrator | null, check?: PermissionCheck): boolean {
  if (!check) return true
  if (!administrator) return false
  if ("role" in check) return administrator.role === check.role
  if ("anyRole" in check) return check.anyRole.includes(administrator.role)
  if ("permission" in check) return administrator.permissions.includes(check.permission)
  if ("installOperator" in check) return administrator.install_operator === true
  return check.anyPermission.some((permission) => administrator.permissions.includes(permission))
}

export function usePermission(check?: PermissionCheck): boolean {
  const { administrator } = useAuth()
  return matchesPermission(administrator, check)
}
