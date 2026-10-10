import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import {
  administratorLogin,
  completeSSOLogin,
  refreshAdministrator,
  getCurrentAdministrator,
  logoutAdministrator,
  switchActiveOrganization,
  verifyAdministrator,
  type AdministratorLoginResponse,
  type OrganizationMembership,
} from "../api/client"
import type { Agent } from "../types/api"

const SESSION_KEY = "greyguard_admin_pin"
const REFRESH_KEY = "greyguard_admin_refresh"

export interface Administrator {
  admin_id: string
  email: string
  display_name: string
  role:
    | "PLATFORM_ADMIN"
    | "SECURITY_ANALYST"
    | "AUDITOR"
  permissions: string[]
  mfa_enabled?: boolean
  password_expires_at?: string | null
  organizations?: OrganizationMembership[]
  active_org_id?: string | null
  active_org_name?: string | null
  governance_role?: "OWNER" | "BILLING_ADMIN" | "MEMBER" | null
  /** Global account flag for install-wide controls (accounts, SSO, observability, rate limits) -
   * independent of the per-org role above, which any org owner can hold. */
  install_operator?: boolean
}

interface AuthContextValue {
  sessionToken: string | null
  administrator: Administrator | null
  agents: Agent[]
  isAuthenticated: boolean
  isResumingSession: boolean
  login: (
    email: string,
    password: string,
    mfaCode?: string,
  ) => Promise<void>
  completeSso: (state: string, code: string) => Promise<void>
  completeSetup: (result: AdministratorLoginResponse) => Promise<void>
  switchActiveOrg: (orgId: string) => Promise<void>
  logout: () => Promise<void>
}

// Exported for test wrappers that need to provide a crafted context value directly
// (see usePermission.test.tsx) without mounting the full AuthProvider.
export const AuthContext =
  createContext<AuthContextValue | null>(null)

export function AuthProvider({
  children,
}: {
  children: ReactNode
}) {
  const [sessionToken, setSessionToken] =
    useState<string | null>(() =>
      sessionStorage.getItem(SESSION_KEY),
    )
  const [administrator, setAdministrator] =
    useState<Administrator | null>(null)
  const [agents, setAgents] = useState<Agent[]>([])
  const [isResumingSession, setIsResumingSession] = useState(() =>
    Boolean(sessionStorage.getItem(SESSION_KEY)),
  )

  const clearSession = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY)
    sessionStorage.removeItem(REFRESH_KEY)
    setSessionToken(null)
    setAdministrator(null)
    setAgents([])
    setIsResumingSession(false)
  }, [])

  useEffect(() => {
    if (!sessionToken || administrator) {
      return
    }

    let active = true

    Promise.all([
      getCurrentAdministrator(sessionToken),
      verifyAdministrator(sessionToken),
    ])
      .then(([currentAdministrator, agentList]) => {
        if (active) {
          setAdministrator(currentAdministrator)
          setAgents(agentList)
          setIsResumingSession(false)
        }
      })
      .catch(async () => {
        const refreshToken=sessionStorage.getItem(REFRESH_KEY)
        if(!active||!refreshToken){if(active)clearSession();return}
        try{const refreshed=await refreshAdministrator(refreshToken);sessionStorage.setItem(SESSION_KEY,refreshed.access_token);sessionStorage.setItem(REFRESH_KEY,refreshed.refresh_token);setSessionToken(refreshed.access_token);setAdministrator(refreshed.administrator);if(active)setIsResumingSession(false)}catch{if(active)clearSession()}
      })

    return () => {
      active = false
    }
  }, [administrator, clearSession, sessionToken])

  const applySession = useCallback(
    async (result: AdministratorLoginResponse) => {
      const agentList = await verifyAdministrator(
        result.access_token,
      )

      sessionStorage.setItem(
        SESSION_KEY,
        result.access_token,
      )
      sessionStorage.setItem(REFRESH_KEY,result.refresh_token)
      setSessionToken(result.access_token)
      setAdministrator(result.administrator)
      setAgents(agentList)
    },
    [],
  )

  const login = useCallback(
    async (email: string, password: string, mfaCode?: string) => {
      if (!email.trim() || !password) {
        throw new Error(
          "Email and password are required.",
        )
      }

      const result = await administratorLogin(
        email.trim(),
        password,
        mfaCode,
      )
      await applySession(result)
    },
    [applySession],
  )

  const completeSso = useCallback(
    async (state: string, code: string) => {
      const result = await completeSSOLogin(state, code)
      await applySession(result)
    },
    [applySession],
  )

  const completeSetup = useCallback(
    async (result: AdministratorLoginResponse) => {
      await applySession(result)
    },
    [applySession],
  )

  const switchActiveOrg = useCallback(
    async (orgId: string) => {
      if (!sessionToken) {
        throw new Error("No active session.")
      }
      const updated = await switchActiveOrganization(sessionToken, orgId)
      setAdministrator(updated)
    },
    [sessionToken],
  )

  const logout = useCallback(async () => {
    if (sessionToken) {
      await logoutAdministrator(sessionToken).catch(
        () => undefined,
      )
    }
    clearSession()
  }, [clearSession, sessionToken])

  const value = useMemo(
    () => ({
      sessionToken,
      administrator,
      agents,
      isAuthenticated: Boolean(
        sessionToken && administrator,
      ),
      isResumingSession,
      login,
      completeSso,
      completeSetup,
      switchActiveOrg,
      logout,
    }),
    [
      sessionToken,
      administrator,
      agents,
      isResumingSession,
      login,
      completeSso,
      completeSetup,
      switchActiveOrg,
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
