import { useEffect, useState } from "react"
import { RefreshCw, WifiOff } from "lucide-react"
import { registerSW } from "virtual:pwa-register"
import "../styles/pwa-update-prompt.css"

/**
 * Manual service-worker registration (injectRegister: false in vite.config.ts) so this
 * component - not Workbox's auto-injected script - controls what the operator sees. A new
 * build never silently replaces the running app: onNeedRefresh shows a dismissible banner
 * and the operator decides when to reload. onOfflineReady only confirms the app shell can
 * load offline - it never implies live security data is available offline.
 */
export function PwaUpdatePrompt() {
  const [needsRefresh, setNeedsRefresh] = useState(false)
  const [offlineReady, setOfflineReady] = useState(false)
  const [updateServiceWorker, setUpdateServiceWorker] = useState<((reload?: boolean) => Promise<void>) | null>(null)

  useEffect(() => {
    const update = registerSW({
      onNeedRefresh: () => setNeedsRefresh(true),
      onOfflineReady: () => setOfflineReady(true),
    })
    setUpdateServiceWorker(() => update)
  }, [])

  if (!needsRefresh && !offlineReady) return null

  return (
    <div className="gg-pwa-prompt" role="status" aria-live="polite">
      {needsRefresh && (
        <div className="gg-pwa-prompt__banner">
          <RefreshCw size={16} />
          <span>A new GreyGuard build is available.</span>
          <button type="button" onClick={() => void updateServiceWorker?.(true)}>
            Reload now
          </button>
          <button type="button" className="gg-pwa-prompt__dismiss" onClick={() => setNeedsRefresh(false)}>
            Later
          </button>
        </div>
      )}
      {!needsRefresh && offlineReady && (
        <div className="gg-pwa-prompt__banner gg-pwa-prompt__banner--info">
          <WifiOff size={16} />
          <span>GreyGuard is ready to load offline. Live security data still requires a connection.</span>
          <button type="button" className="gg-pwa-prompt__dismiss" onClick={() => setOfflineReady(false)}>
            Dismiss
          </button>
        </div>
      )}
    </div>
  )
}
