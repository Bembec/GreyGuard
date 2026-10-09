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


export interface OrganizationMembership {
  org_id: string
  org_name: string
  operational_role: "PLATFORM_ADMIN" | "SECURITY_ANALYST" | "AUDITOR"
  governance_role: "OWNER" | "BILLING_ADMIN" | "MEMBER"
  status: string
  created_at: string
}

export interface AdministratorIdentity {
  admin_id: string
  email: string
  display_name: string
  role: "PLATFORM_ADMIN" | "SECURITY_ANALYST" | "AUDITOR"
  permissions: string[]
  mfa_enabled?: boolean
  password_expires_at?: string | null
  organizations?: OrganizationMembership[]
  active_org_id?: string | null
  active_org_name?: string | null
  governance_role?: "OWNER" | "BILLING_ADMIN" | "MEMBER" | null
}

export interface AdministratorLoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_at: string
  administrator: AdministratorIdentity
}

export function administratorLogin(email: string, password: string, mfaCode?: string) {
  return apiRequest<AdministratorLoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password, mfa_code: mfaCode || null, device_name: navigator.userAgent.slice(0,100) }),
  })
}

export function refreshAdministrator(refreshToken: string) {
  return apiRequest<AdministratorLoginResponse>("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken, device_name: navigator.userAgent.slice(0,100) }),
  })
}

export function getCurrentAdministrator(token: string) {
  return apiRequest<AdministratorIdentity>("/auth/me", {
    headers: { "x-admin-pin": token },
  })
}

export function logoutAdministrator(token: string) {
  return apiRequest<{ logged_out: boolean }>("/auth/logout", {
    method: "POST",
    headers: { "x-admin-pin": token },
  })
}

export function switchActiveOrganization(token: string, orgId: string) {
  return apiRequest<AdministratorIdentity>("/auth/active-org", {
    method: "POST",
    headers: { "x-admin-pin": token },
    body: JSON.stringify({ org_id: orgId }),
  })
}

export interface SSOProvider {
  provider_id: string
  name: string
}

export function listSSOProviders() {
  return apiRequest<{ providers: SSOProvider[] }>("/auth/sso/providers")
}

export function beginSSOLogin(providerId: string) {
  return apiRequest<{ authorization_url: string }>(`/auth/sso/${encodeURIComponent(providerId)}/begin`, {
    method: "POST",
  })
}

export function completeSSOLogin(state: string, code: string) {
  return apiRequest<AdministratorLoginResponse>("/auth/sso/callback", {
    method: "POST",
    body: JSON.stringify({ state, code, device_name: navigator.userAgent.slice(0, 100) }),
  })
}

export function fetchSetupStatus() {
  return apiRequest<{ needs_setup: boolean }>("/auth/setup-status")
}

export function submitFirstAdministratorSetup(email: string, displayName: string, password: string) {
  return apiRequest<AdministratorLoginResponse>("/auth/setup", {
    method: "POST",
    body: JSON.stringify({
      email, display_name: displayName, password,
      device_name: navigator.userAgent.slice(0, 100),
    }),
  })
}
