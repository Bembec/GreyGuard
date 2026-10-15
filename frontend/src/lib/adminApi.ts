const API = import.meta.env.VITE_API_BASE_URL ?? "/api"

/**
 * One authenticated call to the GreyGuard API on behalf of the signed-in administrator. Resolves
 * with the parsed body, or throws an Error carrying the server's own explanation.
 */
export async function adminCall<T>(path: string, token: string | null, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    method: init.method ?? "GET",
    headers: { "Content-Type": "application/json", "X-Admin-Pin": token ?? "" },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error((body as { detail?: unknown }).detail ? String((body as { detail: unknown }).detail) : "GreyGuard request failed.")
  return body as T
}
