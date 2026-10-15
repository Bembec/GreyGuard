import { navigationItems } from "../config/navigation"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api"
const navigationPaths = new Set(navigationItems.map((item) => item.path))

/** The path to count for a page view, or null when nothing should be sent: only exact navigation
 * paths (never URLs with identifiers in them), and never when the browser asks not to be tracked. */
export function pageViewPath(pathname: string, doNotTrack: string | null | undefined): string | null {
  if (doNotTrack === "1" || doNotTrack === "yes") return null
  return navigationPaths.has(pathname) ? pathname : null
}

/** Counts one page view for the signed-in org. Fire and forget: analytics never blocks or breaks a page. */
export function recordPageView(pathname: string): void {
  const path = pageViewPath(pathname, typeof navigator === "undefined" ? null : navigator.doNotTrack)
  if (!path) return
  void fetch(`${API_BASE_URL}/analytics/page-view`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" },
    body: JSON.stringify({ path }),
    keepalive: true,
  }).catch(() => undefined)
}
