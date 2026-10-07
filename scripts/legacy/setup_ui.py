from pathlib import Path


root = Path(__file__).resolve().parents[1]

files = {
    "frontend/src/types/api.ts": """
export interface AgentIdentity {
  agent_name: string
  scopes: string[]
  credential_status: string
  created_at: string
  rotated_at: string | null
  revoked_at: string | null
}

export interface Agent {
  agent_name: string
  agent_status: "ACTIVE" | "SUSPENDED"
  risk_score: number
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
  blocked_attempts: number
  identity: AgentIdentity | null
}

export interface HealthResponse {
  status: string
  version: string
  registered_agents: number
  registered_identities: number
  controlled_tools: number
  sandbox_initialized: boolean
}
""",
    "frontend/src/api/client.ts": """
import type {
  Agent,
  HealthResponse,
} from "../types/api"

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "/api"

interface ApiErrorBody {
  detail?: string
}

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function parseError(
  response: Response,
): Promise<string> {
  try {
    const body = (await response.json()) as ApiErrorBody
    return body.detail ?? "GreyGuard request failed."
  } catch {
    return "GreyGuard request failed."
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(
    `${API_BASE_URL}${path}`,
    {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    },
  )

  if (!response.ok) {
    throw new ApiError(
      await parseError(response),
      response.status,
    )
  }

  return response.json() as Promise<T>
}

export function getHealth() {
  return apiRequest<HealthResponse>("/health")
}

export function verifyAdministrator(
  adminPin: string,
) {
  return apiRequest<Agent[]>("/agents", {
    headers: {
      "x-admin-pin": adminPin,
    },
  })
}
""",
    "frontend/src/context/AuthContext.tsx": """
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import { verifyAdministrator } from "../api/client"
import type { Agent } from "../types/api"

const SESSION_KEY = "greyguard_admin_pin"

interface AuthContextValue {
  adminPin: string | null
  agents: Agent[]
  isAuthenticated: boolean
  login: (pin: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(
  null,
)

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({
  children,
}: AuthProviderProps) {
  const [adminPin, setAdminPin] = useState<string | null>(
    () => sessionStorage.getItem(SESSION_KEY),
  )

  const [agents, setAgents] = useState<Agent[]>([])

  const login = useCallback(
    async (pin: string) => {
      const normalizedPin = pin.trim()

      if (!normalizedPin) {
        throw new Error(
          "Administrator PIN is required.",
        )
      }

      const verifiedAgents =
        await verifyAdministrator(normalizedPin)

      sessionStorage.setItem(
        SESSION_KEY,
        normalizedPin,
      )

      setAdminPin(normalizedPin)
      setAgents(verifiedAgents)
    },
    [],
  )

  const logout = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY)
    setAdminPin(null)
    setAgents([])
  }, [])

  const value = useMemo(
    () => ({
      adminPin,
      agents,
      isAuthenticated: Boolean(adminPin),
      login,
      logout,
    }),
    [
      adminPin,
      agents,
      login,
      logout,
    ],
  )

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error(
      "useAuth must be used inside AuthProvider.",
    )
  }

  return context
}
""",
    "frontend/src/pages/LoginPage.tsx": """
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
""",
    "frontend/src/styles/login.css": """
.login-page {
  position: relative;
  display: grid;
  min-height: 100vh;
  grid-template-columns:
    minmax(0, 1.15fr)
    minmax(420px, 0.85fr);
  overflow: hidden;
  isolation: isolate;
  background:
    radial-gradient(
      circle at 20% 25%,
      rgba(34, 211, 238, 0.1),
      transparent 32%
    ),
    radial-gradient(
      circle at 80% 80%,
      rgba(139, 92, 246, 0.08),
      transparent 28%
    ),
    var(--gg-obsidian);
}

.login-page__grid {
  position: absolute;
  z-index: -3;
  inset: 0;
  opacity: 0.24;
  background-image:
    linear-gradient(
      rgba(34, 211, 238, 0.1) 1px,
      transparent 1px
    ),
    linear-gradient(
      90deg,
      rgba(34, 211, 238, 0.1) 1px,
      transparent 1px
    );
  background-size: 62px 62px;
  mask-image:
    radial-gradient(
      circle at 35% 48%,
      black,
      transparent 72%
    );
  animation: login-grid-move 24s linear infinite;
}

.login-page__scanline {
  position: absolute;
  z-index: -1;
  top: -20%;
  left: 0;
  width: 58%;
  height: 18%;
  opacity: 0.18;
  background:
    linear-gradient(
      transparent,
      rgba(34, 211, 238, 0.16),
      transparent
    );
  filter: blur(12px);
  animation: login-scan 8s ease-in-out infinite;
}

.login-visual {
  position: relative;
  display: flex;
  min-height: 100vh;
  flex-direction: column;
  justify-content: center;
  padding:
    clamp(2rem, 6vw, 7rem)
    clamp(2rem, 7vw, 8rem);
}

.login-visual__symbol {
  position: absolute;
  top: 50%;
  left: 47%;
  z-index: -1;
  display: grid;
  width: min(46vw, 620px);
  aspect-ratio: 1;
  place-items: center;
  transform: translate(-50%, -50%);
  opacity: 0.12;
}

.login-visual__symbol img {
  width: 54%;
  height: 54%;
  object-fit: contain;
  filter:
    saturate(0.8)
    drop-shadow(
      0 0 42px rgba(34, 211, 238, 0.3)
    );
  animation: login-symbol-breathe 6s ease-in-out infinite;
}

.login-visual__ring {
  position: absolute;
  border: 1px solid rgba(34, 211, 238, 0.28);
  border-radius: 50%;
}

.login-visual__ring::after {
  position: absolute;
  top: -4px;
  left: 50%;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--gg-cyan);
  box-shadow: 0 0 18px var(--gg-cyan);
  content: "";
}

.login-visual__ring--one {
  inset: 7%;
  animation: login-ring 22s linear infinite;
}

.login-visual__ring--two {
  inset: 18%;
  border-color: rgba(139, 92, 246, 0.25);
  animation: login-ring 16s linear infinite reverse;
}

.login-visual__ring--three {
  inset: 30%;
  animation: login-ring 12s linear infinite;
}

.login-visual__copy {
  max-width: 720px;
}

.login-eyebrow {
  margin-bottom: 1rem;
  color: var(--gg-cyan-soft);
  font-size: 0.72rem;
  font-weight: 750;
  letter-spacing: 0.2em;
  text-transform: uppercase;
}

.login-visual h1 {
  margin-bottom: 1.35rem;
  font-size: clamp(3rem, 6vw, 6.8rem);
  line-height: 0.94;
  letter-spacing: -0.07em;
}

.login-visual h1 span {
  color: transparent;
  background:
    linear-gradient(
      90deg,
      var(--gg-cyan),
      var(--gg-blue),
      var(--gg-violet)
    );
  background-clip: text;
}

.login-visual__copy > p:last-child {
  max-width: 640px;
  color: var(--gg-text-secondary);
  font-size: clamp(1rem, 1.6vw, 1.15rem);
  line-height: 1.8;
}

.login-visual__signals {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
  margin-top: 3rem;
}

.login-visual__signals span {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.62rem 0.8rem;
  border: 1px solid var(--gg-border);
  border-radius: 999px;
  color: var(--gg-text-secondary);
  background: rgba(8, 17, 31, 0.64);
  font-size: 0.76rem;
  backdrop-filter: blur(12px);
}

.login-visual__signals svg {
  color: var(--gg-cyan);
}

.login-panel {
  display: flex;
  min-height: 100vh;
  flex-direction: column;
  border-left: 1px solid var(--gg-border);
  background:
    linear-gradient(
      180deg,
      rgba(15, 25, 42, 0.96),
      rgba(6, 12, 22, 0.97)
    );
  box-shadow: -30px 0 80px rgba(0, 0, 0, 0.24);
}

.login-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 82px;
  padding: 0 2rem;
  border-bottom: 1px solid var(--gg-border);
}

.login-wordmark {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  letter-spacing: 0.12em;
}

.login-wordmark svg {
  color: var(--gg-cyan);
}

.login-version {
  color: var(--gg-text-muted);
  font-family: var(--gg-font-mono);
  font-size: 0.64rem;
  letter-spacing: 0.1em;
}

.login-form-wrap {
  width: min(470px, calc(100% - 3rem));
  margin: auto;
}

.login-form-heading {
  display: flex;
  align-items: center;
  gap: 0.9rem;
}

.login-form-heading__icon {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border: 1px solid var(--gg-border-strong);
  border-radius: 14px;
  color: var(--gg-cyan);
  background: rgba(34, 211, 238, 0.07);
}

.login-form-heading p {
  margin-bottom: 0.3rem;
  color: var(--gg-cyan-soft);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.login-form-heading h2 {
  margin: 0;
  font-size: clamp(1.5rem, 3vw, 2rem);
  letter-spacing: -0.035em;
}

.login-description {
  margin: 1.4rem 0 2rem;
  color: var(--gg-text-secondary);
  line-height: 1.7;
}

.login-form {
  display: grid;
  gap: 0.8rem;
}

.login-form > label {
  color: var(--gg-text-secondary);
  font-size: 0.78rem;
  font-weight: 650;
}

.login-input {
  display: grid;
  min-height: 56px;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 0.75rem;
  padding: 0 0.85rem;
  border: 1px solid var(--gg-border);
  border-radius: var(--gg-radius-md);
  background: rgba(4, 10, 19, 0.6);
  transition:
    border-color var(--gg-transition),
    box-shadow var(--gg-transition);
}

.login-input:focus-within {
  border-color: var(--gg-cyan);
  box-shadow: 0 0 0 4px rgba(34, 211, 238, 0.08);
}

.login-input > svg {
  color: var(--gg-text-muted);
}

.login-input input {
  width: 100%;
  border: 0;
  outline: 0;
  color: var(--gg-text-primary);
  background: transparent;
}

.login-input input::placeholder {
  color: var(--gg-text-muted);
}

.login-input button {
  display: grid;
  padding: 0.35rem;
  border: 0;
  place-items: center;
  color: var(--gg-text-muted);
  background: transparent;
  cursor: pointer;
}

.login-error {
  margin: 0;
  padding: 0.75rem;
  border: 1px solid rgba(239, 68, 68, 0.22);
  border-radius: 10px;
  color: #fecaca;
  background: rgba(239, 68, 68, 0.08);
  font-size: 0.8rem;
}

.login-submit {
  min-height: 54px;
  margin-top: 0.45rem;
  border: 1px solid rgba(103, 232, 249, 0.3);
  border-radius: var(--gg-radius-md);
  color: #031116;
  background:
    linear-gradient(
      100deg,
      var(--gg-cyan),
      #60a5fa
    );
  box-shadow:
    0 12px 32px rgba(34, 211, 238, 0.16);
  font-weight: 780;
  cursor: pointer;
  transition:
    transform var(--gg-transition),
    box-shadow var(--gg-transition),
    opacity var(--gg-transition);
}

.login-submit:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow:
    0 16px 40px rgba(34, 211, 238, 0.24);
}

.login-submit:disabled {
  cursor: wait;
  opacity: 0.65;
}

.login-security-note {
  display: flex;
  gap: 0.75rem;
  margin-top: 1.2rem;
  padding: 0.9rem;
  border: 1px solid var(--gg-border);
  border-radius: var(--gg-radius-md);
  color: var(--gg-text-muted);
  background: rgba(148, 163, 184, 0.04);
}

.login-security-note svg {
  flex: 0 0 auto;
  color: var(--gg-green);
}

.login-security-note p {
  margin: 0;
  font-size: 0.73rem;
  line-height: 1.55;
}

.login-footer {
  display: flex;
  justify-content: space-between;
  padding: 1.25rem 2rem;
  border-top: 1px solid var(--gg-border);
  color: var(--gg-text-muted);
  font-size: 0.68rem;
}

.login-footer span {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.login-footer__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--gg-amber);
  box-shadow: 0 0 12px var(--gg-amber);
}

@keyframes login-grid-move {
  to {
    transform: translateY(62px);
  }
}

@keyframes login-scan {
  50% {
    transform: translateY(700%);
  }
}

@keyframes login-ring {
  to {
    transform: rotate(360deg);
  }
}

@keyframes login-symbol-breathe {
  50% {
    transform: scale(1.04);
    filter:
      saturate(1)
      drop-shadow(
        0 0 60px rgba(34, 211, 238, 0.42)
      );
  }
}

@media (max-width: 980px) {
  .login-page {
    grid-template-columns: 1fr;
  }

  .login-visual {
    display: none;
  }

  .login-panel {
    border-left: 0;
  }
}

@media (max-width: 520px) {
  .login-panel__header {
    padding: 0 1.2rem;
  }

  .login-version {
    display: none;
  }

  .login-form-wrap {
    width: min(100% - 2rem, 470px);
  }

  .login-footer {
    flex-direction: column;
    gap: 0.6rem;
    padding: 1rem 1.2rem;
  }
}
""",
    "frontend/src/App.tsx": """
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
""",
}


for relative_path, content in files.items():
    destination = root / relative_path

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination.write_text(
        content.strip() + "\n",
        encoding="utf-8",
    )

    print(
        "Created:",
        destination.relative_to(root),
    )


print()
print("GreyGuard V11 login created.")