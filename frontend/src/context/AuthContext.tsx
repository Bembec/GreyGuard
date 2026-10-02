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
  getCurrentAdministrator,
  logoutAdministrator,
  verifyAdministrator,
} from "../api/client"
import type { Agent } from "../types/api"

const SESSION_KEY = "greyguard_admin_pin"

export interface Administrator {
  admin_id: string
  email: string
  display_name: string
  role:
    | "PLATFORM_ADMIN"
    | "SECURITY_ANALYST"
    | "AUDITOR"
  permissions: string[]
}

interface AuthContextValue {
  sessionToken: string | null
  administrator: Administrator | null
  agents: Agent[]
  isAuthenticated: boolean
  login: (
    email: string,
    password: string,
  ) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext =
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

  const clearSession = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY)
    setSessionToken(null)
    setAdministrator(null)
    setAgents([])
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
        }
      })
      .catch(() => {
        if (active) {
          clearSession()
        }
      })

    return () => {
      active = false
    }
  }, [administrator, clearSession, sessionToken])

  const login = useCallback(
    async (email: string, password: string) => {
      if (!email.trim() || !password) {
        throw new Error(
          "Email and password are required.",
        )
      }

      const result = await administratorLogin(
        email.trim(),
        password,
      )
      const agentList = await verifyAdministrator(
        result.access_token,
      )

      sessionStorage.setItem(
        SESSION_KEY,
        result.access_token,
      )
      setSessionToken(result.access_token)
      setAdministrator(result.administrator)
      setAgents(agentList)
    },
    [],
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
      login,
      logout,
    }),
    [
      sessionToken,
      administrator,
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
