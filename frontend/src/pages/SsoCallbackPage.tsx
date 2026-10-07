import { ShieldAlert, ShieldCheck } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useSearchParams } from "react-router-dom"

import { ApiError } from "../api/client"
import { useAuth } from "../context/AuthContext"
import "../styles/login.css"

export function SsoCallbackPage() {
  const [searchParams] = useSearchParams()
  const { completeSso } = useAuth()
  const [error, setError] = useState("")
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true

    const providerError = searchParams.get("error")
    const state = searchParams.get("state")
    const code = searchParams.get("code")

    if (providerError) {
      setError("The identity provider declined this sign-in attempt.")
      return
    }
    if (!state || !code) {
      setError("This sign-in link is incomplete or has already been used.")
      return
    }

    completeSso(state, code).catch((value) => {
      setError(
        value instanceof ApiError || value instanceof Error
          ? value.message
          : "GreyGuard could not complete enterprise sign-in.",
      )
    })
  }, [searchParams, completeSso])

  return (
    <main className="login-page">
      <div className="login-page__grid" />
      <section className="login-panel" style={{ margin: "auto" }}>
        <div className="login-form-wrap">
          <div className="login-form-heading">
            <span className="login-form-heading__icon">
              {error ? <ShieldAlert size={22} /> : <ShieldCheck size={22} />}
            </span>
            <div>
              <p>Enterprise sign-in</p>
              <h1>{error ? "Sign-in failed" : "Finishing sign-in…"}</h1>
            </div>
          </div>
          {error ? (
            <>
              <p className="login-error" role="alert">{error}</p>
              <a className="login-submit" href="/" style={{ display: "block", textAlign: "center", textDecoration: "none" }}>
                Return to sign-in
              </a>
            </>
          ) : (
            <p className="login-description">Verifying your identity with the configured provider.</p>
          )}
        </div>
      </section>
    </main>
  )
}
