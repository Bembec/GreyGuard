import { AuthProvider, useAuth } from "./context/AuthContext"
import { LoginPage } from "./pages/LoginPage"
import "./styles/foundation.css"

function AuthenticatedFoundation() {
  const { logout } = useAuth()

  return (
    <main className="foundation">
      <div className="foundation__grid" />
      <div className="foundation__glow foundation__glow--cyan" />
      <div className="foundation__glow foundation__glow--violet" />

      <section className="foundation__content">
        <div className="foundation__brand">
          <div>
            <p className="foundation__eyebrow">
              Administrator verified
            </p>
            <h1>GreyGuard Command Center</h1>
          </div>
        </div>

        <div className="foundation__hero">
          <span className="foundation__status">
            <span className="foundation__status-dot" />
            Protected session active
          </span>

          <h2>
            Control access
            <span> granted.</span>
          </h2>

          <p>
            The responsive dashboard, navigation,
            agents and approval modules are the next
            interface layer.
          </p>

          <button
            type="button"
            className="login-submit"
            onClick={logout}
          >
            End protected session
          </button>
        </div>
      </section>
    </main>
  )
}

function GreyGuardApplication() {
  const { isAuthenticated } = useAuth()

  if (!isAuthenticated) {
    return <LoginPage />
  }

  return <AuthenticatedFoundation />
}

function App() {
  return (
    <AuthProvider>
      <GreyGuardApplication />
    </AuthProvider>
  )
}

export default App
