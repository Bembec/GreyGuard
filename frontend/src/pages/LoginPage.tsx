import {
  Eye,
  EyeOff,
  Fingerprint,
  KeyRound,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react"
import {
  useState,
  type FormEvent,
} from "react"

import { ApiError } from "../api/client"
import { useAuth } from "../context/AuthContext"
import "../styles/login.css"

export function LoginPage() {
  const { login } = useAuth()

  const [pin, setPin] = useState("")
  const [showPin, setShowPin] = useState(false)
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] =
    useState(false)

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()
    setError("")
    setIsSubmitting(true)

    try {
      await login(pin)
    } catch (loginError) {
      if (loginError instanceof ApiError) {
        if (loginError.status === 503) {
          setError(
            "The backend administrator PIN is not configured.",
          )
        } else {
          setError(loginError.message)
        }
      } else if (loginError instanceof Error) {
        setError(loginError.message)
      } else {
        setError(
          "GreyGuard could not verify the administrator.",
        )
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-page__grid" />
      <div className="login-page__scanline" />

      <section className="login-visual">
        <div className="login-visual__symbol">
          <span className="login-visual__ring login-visual__ring--one" />
          <span className="login-visual__ring login-visual__ring--two" />
          <span className="login-visual__ring login-visual__ring--three" />

          <img
            src="/brand/greyguard-symbol.png"
            alt="GreyGuard security symbol"
          />
        </div>

        <div className="login-visual__copy">
          <p className="login-eyebrow">
            Agent Security Command
          </p>

          <h1>
            Every action passes
            <span> through the guard.</span>
          </h1>

          <p>
            Authenticate to inspect agents, enforce
            policy boundaries, review approvals and
            preserve execution evidence.
          </p>
        </div>

        <div className="login-visual__signals">
          <span>
            <ShieldCheck size={16} />
            Policy online
          </span>

          <span>
            <Fingerprint size={16} />
            Identity enforced
          </span>

          <span>
            <LockKeyhole size={16} />
            Sandbox sealed
          </span>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-panel__header">
          <div className="login-wordmark">
            <ShieldCheck size={24} />
            <strong>GREYGUARD</strong>
          </div>

          <span className="login-version">
            CONTROL PLANE V11
          </span>
        </div>

        <div className="login-form-wrap">
          <div className="login-form-heading">
            <span className="login-form-heading__icon">
              <KeyRound size={22} />
            </span>

            <div>
              <p>Protected access</p>
              <h2>Administrator sign in</h2>
            </div>
          </div>

          <p className="login-description">
            Enter the administrator PIN configured
            for the running GreyGuard backend.
          </p>

          <form
            className="login-form"
            onSubmit={handleSubmit}
          >
            <label htmlFor="admin-pin">
              Administrator PIN
            </label>

            <div className="login-input">
              <LockKeyhole size={18} />

              <input
                id="admin-pin"
                type={showPin ? "text" : "password"}
                value={pin}
                onChange={(event) =>
                  setPin(event.target.value)
                }
                autoComplete="current-password"
                placeholder="Enter secure PIN"
                disabled={isSubmitting}
              />

              <button
                type="button"
                onClick={() =>
                  setShowPin((current) => !current)
                }
                aria-label={
                  showPin
                    ? "Hide administrator PIN"
                    : "Show administrator PIN"
                }
              >
                {showPin ? (
                  <EyeOff size={18} />
                ) : (
                  <Eye size={18} />
                )}
              </button>
            </div>

            {error ? (
              <p
                className="login-error"
                role="alert"
              >
                {error}
              </p>
            ) : null}

            <button
              className="login-submit"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting
                ? "Verifying control access…"
                : "Enter command center"}
            </button>
          </form>

          <div className="login-security-note">
            <ShieldCheck size={18} />

            <p>
              The PIN remains in this browser tab
              only and is removed when you sign out.
            </p>
          </div>
        </div>

        <footer className="login-footer">
          <span>
            <span className="login-footer__dot" />
            Awaiting backend verification
          </span>

          <span>Local defensive environment</span>
        </footer>
      </section>
    </main>
  )
}
