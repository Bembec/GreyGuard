import { Logo } from "./Logo"
import "../../styles/splash.css"

/**
 * Shown only while AuthContext is resolving a session token that already exists in
 * storage (see AuthContext's isResumingSession) - replaces the prior behavior of
 * briefly rendering LoginPage during that window on every hard reload with a live
 * session.
 */
export function SplashScreen({ waiting = false }: { waiting?: boolean }) {
  return (
    <div className="gg-splash" role="status" aria-live="polite">
      <Logo variant="primary" className="gg-splash__logo" />
      <span className="gg-splash__status">
        {waiting ? "Waiting for the control plane to respond. Your session is kept and will resume automatically…" : "Verifying your session…"}
      </span>
    </div>
  )
}
