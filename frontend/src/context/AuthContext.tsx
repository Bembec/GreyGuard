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
