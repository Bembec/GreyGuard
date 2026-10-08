import { Eye, EyeOff, Fingerprint, KeyRound, LockKeyhole, ShieldCheck } from "lucide-react"
import { useEffect, useState, type FormEvent } from "react"
import { ApiError, beginSSOLogin, listSSOProviders, type SSOProvider } from "../api/client"
import { Logo } from "../components/brand/Logo"
import { useAuth } from "../context/AuthContext"
import "../styles/login.css"

export function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [mfaCode,setMfaCode]=useState("")
  const [mfaRequired,setMfaRequired]=useState(false)
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [ssoProviders, setSsoProviders] = useState<SSOProvider[]>([])
  const [ssoStarting, setSsoStarting] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    listSSOProviders()
      .then((result) => { if (active) setSsoProviders(result.providers) })
      .catch(() => undefined)
    return () => { active = false }
  }, [])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setIsSubmitting(true)
    try { await login(email, password, mfaCode||undefined) }
    catch (value) {
      if(value instanceof ApiError&&value.status===428){setMfaRequired(true);setError("Enter the six-digit code from your authenticator app.");return}
      setError(value instanceof ApiError || value instanceof Error
        ? value.message : "GreyGuard could not verify the administrator.")
    } finally { setIsSubmitting(false) }
  }

  async function handleSsoClick(provider: SSOProvider) {
    setError(""); setSsoStarting(provider.provider_id)
    try {
      const { authorization_url } = await beginSSOLogin(provider.provider_id)
      window.location.href = authorization_url
    } catch (value) {
      setSsoStarting(null)
      setError(value instanceof ApiError || value instanceof Error
        ? value.message : "GreyGuard could not start enterprise sign-in.")
    }
  }

  return <main className="login-page">
    <div className="login-page__grid" /><div className="login-page__scanline" />
    <section className="login-visual">
      <div className="login-visual__symbol">
        <span className="login-visual__ring login-visual__ring--one" />
        <span className="login-visual__ring login-visual__ring--two" />
        <span className="login-visual__ring login-visual__ring--three" />
        <Logo variant="symbol" />
      </div>
      <div className="login-visual__copy">
        <Logo variant="primary" className="login-visual__primary-logo" />
        <p className="login-eyebrow">Agent Security Command</p>
        <h1>Every action passes<span> through the guard.</span></h1>
        <p>Authenticate with your individual operator identity to enforce policy, investigate risk and preserve accountable evidence.</p>
      </div>
      <div className="login-visual__signals"><span><ShieldCheck size={16}/>Policy online</span><span><Fingerprint size={16}/>Identity enforced</span><span><LockKeyhole size={16}/>RBAC active</span></div>
    </section>
    <section className="login-panel">
      <div className="login-panel__header"><Logo variant="horizontal" /><span className="login-version">CONTROL PLANE V11</span></div>
      <div className="login-form-wrap">
        <div className="login-form-heading"><span className="login-form-heading__icon"><KeyRound size={22}/></span><div><p>Protected access</p><h2>Operator sign in</h2></div></div>
        <p className="login-description">Use the administrator identity assigned to you. Every privileged action is tied to an accountable role.</p>
        <form className="login-form" onSubmit={handleSubmit}>
          <label htmlFor="admin-email">Email address</label>
          <div className="login-input"><Fingerprint size={18}/><input id="admin-email" type="email" value={email} onChange={(e)=>setEmail(e.target.value)} autoComplete="username" placeholder="admin@greyguard.local" disabled={isSubmitting}/></div>
          <label htmlFor="admin-password">Password</label>
          <div className="login-input"><LockKeyhole size={18}/><input id="admin-password" type={showPassword?"text":"password"} value={password} onChange={(e)=>setPassword(e.target.value)} autoComplete="current-password" placeholder="Enter secure password" disabled={isSubmitting}/><button type="button" onClick={()=>setShowPassword(v=>!v)} aria-label={showPassword?"Hide password":"Show password"}>{showPassword?<EyeOff size={18}/>:<Eye size={18}/>}</button></div>
          {mfaRequired&&<><label htmlFor="admin-mfa">Authenticator code</label><div className="login-input"><Fingerprint size={18}/><input id="admin-mfa" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={mfaCode} onChange={e=>setMfaCode(e.target.value.replace(/\D/g,""))} autoComplete="one-time-code" placeholder="000000"/></div></>}
          {error && <p className="login-error" role="alert">{error}</p>}
          <button className="login-submit" type="submit" disabled={isSubmitting}>{isSubmitting?"Verifying identity…":"Enter command center"}</button>
        </form>
        {ssoProviders.length > 0 && (
          <div className="login-sso">
            <span className="login-sso__divider">Or sign in with your organization</span>
            {ssoProviders.map((provider) => (
              <button
                key={provider.provider_id}
                type="button"
                className="login-sso__button"
                onClick={() => handleSsoClick(provider)}
                disabled={ssoStarting !== null}
              >
                <ShieldCheck size={18} />
                {ssoStarting === provider.provider_id ? "Redirecting…" : `Continue with ${provider.name}`}
              </button>
            ))}
          </div>
        )}
        <div className="login-security-note"><ShieldCheck size={18}/><p>The session token remains in this browser tab and is revoked when you sign out.</p></div>
      </div>
      <footer className="login-footer"><span><span className="login-footer__dot"/>RBAC identity verification</span><span>Local defensive environment</span></footer>
    </section>
  </main>
}
