import { Logo } from "./Logo"
import "../../styles/splash.css"

/**
 * Shown only while AuthContext is resolving a session token that already exists in
 * storage (see AuthContext's isResumingSession) - replaces the prior behavior of
 * briefly rendering LoginPage during that window on every hard reload with a live
 * session.
 */
export function SplashScreen() {
  return (
    <div className="gg-splash" role="status" aria-live="polite">
      <Logo variant="primary" className="gg-splash__logo" />
      <span className="gg-splash__status">Verifying your session…</span>
    </div>
  )
}
