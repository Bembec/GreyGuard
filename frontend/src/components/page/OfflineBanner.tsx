import { WifiOff } from "lucide-react"

import { useOnlineStatus } from "../../hooks/useOnlineStatus"

/**
 * Shown on every page while the browser is offline. GreyGuard never serves cached security data,
 * so this says plainly that what is on screen may be out of date and that actions will fail.
 */
export function OfflineBanner() {
  const online = useOnlineStatus()
  if (online) return null
  return (
    <div className="gg-offline" role="status">
      <WifiOff size={17} aria-hidden="true" />
      <div>
        <strong>You are offline</strong>
        <span>What is on screen may be out of date, and actions will not reach GreyGuard until the connection returns. Nothing is served from a cache.</span>
      </div>
    </div>
  )
}
