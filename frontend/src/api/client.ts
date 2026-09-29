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
