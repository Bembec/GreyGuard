import { Eye, EyeOff, LockKeyhole, ShieldCheck, UserRound } from "lucide-react"
import { useState, type FormEvent } from "react"
import { Navigate } from "react-router-dom"

import { ApiError, submitFirstAdministratorSetup } from "../api/client"
import { Logo } from "../components/brand/Logo"
import { useAuth } from "../context/AuthContext"
import { useSetupStatus } from "../hooks/useSetupStatus"
import "../styles/install-wizard.css"

type Step = "welcome" | "create"

export function InstallWizardPage() {
  const { completeSetup } = useAuth()
  const setupStatus = useSetupStatus()
  const [step, setStep] = useState<Step>("welcome")
  const [displayName, setDisplayName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (setupStatus.data && !setupStatus.data.needs_setup) {
    return <Navigate to="/" replace />
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    if (password.length < 12) {
      setError("Password must be at least 12 characters.")
      return
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.")
      return
    }
    setIsSubmitting(true)
    try {
      const result = await submitFirstAdministratorSetup(email, displayName, password)
      // Completing setup immediately authenticates: the route tree swaps away from this
      // page the moment isAuthenticated flips true, so there is no further step here.
      await completeSetup(result)
    } catch (value) {
      setError(
        value instanceof ApiError || value instanceof Error
          ? value.message
          : "GreyGuard could not create the first administrator account.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="install-wizard">
      <section className="install-wizard__panel">
        <Logo variant="primary" className="install-wizard__logo" />

        {step === "welcome" && (
          <div className="install-wizard__step">
            <h1>Welcome to GreyGuard</h1>
            <p>No administrator account exists yet. Create the first Platform Administrator to continue.</p>
            <button type="button" className="install-wizard__submit" onClick={() => setStep("create")}>
              Continue
            </button>
          </div>
        )}

        {step === "create" && (
          <form className="install-wizard__step" onSubmit={handleCreate}>
            <h1>Create the first administrator</h1>
            <p>This account receives the Platform Administrator role, with full access to GreyGuard.</p>
            <label htmlFor="setup-name">Display name</label>
            <div className="install-wizard__input">
              <UserRound size={18} />
              <input
                id="setup-name"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                autoComplete="name"
                placeholder="Jordan Reyes"
                disabled={isSubmitting}
                required
              />
            </div>
            <label htmlFor="setup-email">Email address</label>
            <div className="install-wizard__input">
              <ShieldCheck size={18} />
              <input
                id="setup-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="username"
                placeholder="owner@example.com"
                disabled={isSubmitting}
                required
              />
            </div>
            <label htmlFor="setup-password">Password</label>
            <div className="install-wizard__input">
              <LockKeyhole size={18} />
              <input
                id="setup-password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="new-password"
                placeholder="At least 12 characters"
                disabled={isSubmitting}
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            <label htmlFor="setup-confirm-password">Confirm password</label>
            <div className="install-wizard__input">
              <LockKeyhole size={18} />
              <input
                id="setup-confirm-password"
                type={showPassword ? "text" : "password"}
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                autoComplete="new-password"
                disabled={isSubmitting}
                required
              />
            </div>
            {error && <p className="install-wizard__error" role="alert">{error}</p>}
            <button className="install-wizard__submit" type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Creating account…" : "Create administrator"}
            </button>
          </form>
        )}
      </section>
    </main>
  )
}
