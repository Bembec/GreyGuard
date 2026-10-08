import { Navigate } from "react-router-dom"
import type { ReactNode } from "react"

import { usePermission, type PermissionCheck } from "../../hooks/usePermission"

interface RequirePermissionProps {
  check: PermissionCheck
  children: ReactNode
  /** Renders in place of children when denied (the "in-page access denied panel" pattern). */
  fallback?: ReactNode
  /** Redirects when denied (the "silent redirect" pattern). Takes priority over fallback. */
  redirectTo?: string
}

/**
 * One component covering the three ad hoc permission-guard patterns found across the
 * codebase (silent redirect, in-page denied panel, inline hide) - passing neither fallback
 * nor redirectTo reproduces the third pattern (render nothing) exactly.
 */
export function RequirePermission({ check, children, fallback, redirectTo }: RequirePermissionProps) {
  const allowed = usePermission(check)
  if (allowed) return <>{children}</>
  if (redirectTo) return <Navigate to={redirectTo} replace />
  if (fallback) return <>{fallback}</>
  return null
}
