import {
  AuthenticationError,
  AuthorizationError,
  RequestError,
  ScopeValidationError,
} from "./errors.js"
import { redact } from "./redact.js"

const retryableStatuses = new Set([429, 502, 503, 504])

const wait = (milliseconds) =>
  new Promise((resolve) => globalThis.setTimeout(resolve, milliseconds))

function createIdempotencyKey() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID()
  }

  return `gg-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

/** Secure client for GreyGuard policy evaluation and controlled tools. */
export class GreyGuardClient {
  #credential
  #fetch
  #scopes
  #sleep

  constructor({
    baseUrl,
    agentName,
    credential,
    scopes,
    timeoutMs = 10_000,
    maxRetries = 2,
    fetch: fetchImplementation = globalThis.fetch,
    sleep = wait,
  }) {
    if (!baseUrl?.trim()) throw new TypeError("baseUrl is required")
    if (!agentName?.trim()) throw new TypeError("agentName is required")
    if (!credential) throw new TypeError("credential is required")
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
      throw new TypeError("timeoutMs must be greater than zero")
    }
    if (!Number.isInteger(maxRetries) || maxRetries < 0) {
      throw new TypeError("maxRetries must be a non-negative integer")
    }
    if (typeof fetchImplementation !== "function") {
      throw new TypeError("A Fetch API implementation is required")
    }

    this.baseUrl = baseUrl.replace(/\/$/, "")
    this.agentName = agentName
    this.timeoutMs = timeoutMs
    this.maxRetries = maxRetries
    this.#credential = credential
    this.#scopes = scopes === undefined ? null : new Set(scopes)
    this.#fetch = fetchImplementation
    this.#sleep = sleep
  }

  toJSON() {
    return {
      baseUrl: this.baseUrl,
      agentName: this.agentName,
      credential: "[REDACTED]",
    }
  }

  /** Evaluate one action. This state-sensitive operation is never retried. */
  async evaluate(action) {
    this.#validateScope(action)
    return this.#request("POST", "/actions/evaluate", { action }, {
      retryable: false,
    })
  }

  /** Submit a controlled tool request with idempotent transient retries. */
  async submit(request, { idempotencyKey = createIdempotencyKey() } = {}) {
    this.#validateScope(request.action)
    if (idempotencyKey.length < 8 || idempotencyKey.length > 128) {
      throw new TypeError(
        "idempotencyKey must be between 8 and 128 characters",
      )
    }

    return this.#request(
      "POST",
      "/tool-requests",
      {
        action: request.action,
        target: request.target ?? "",
        payload: request.payload ?? {},
        dry_run: request.dryRun ?? false,
      },
      {
        retryable: true,
        headers: { "Idempotency-Key": idempotencyKey },
      },
    )
  }

  /** Retrieve one request owned by the authenticated agent. */
  async getRequest(requestId) {
    return this.#request(
      "GET",
      `/tool-requests/${encodeURIComponent(requestId)}`,
      undefined,
      { retryable: true },
    )
  }

  #validateScope(action) {
    if (this.#scopes !== null && !this.#scopes.has(action)) {
      throw new ScopeValidationError(
        `Action ${JSON.stringify(action)} is outside this client's declared scopes.`,
      )
    }
  }

  async #request(method, path, body, { retryable, headers = {} }) {
    const attempts = retryable ? this.maxRetries + 1 : 1

    for (let attempt = 0; attempt < attempts; attempt += 1) {
      const controller = new AbortController()
      const timeout = globalThis.setTimeout(
        () => controller.abort(),
        this.timeoutMs,
      )

      let response
      try {
        response = await this.#fetch(`${this.baseUrl}${path}`, {
          method,
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
            "X-Agent-Name": this.agentName,
            "X-Agent-Key": this.#credential,
            ...headers,
          },
          body: body === undefined ? undefined : JSON.stringify(body),
          signal: controller.signal,
        })
      } catch (error) {
        if (attempt + 1 < attempts) {
          await this.#sleep(200 * 2 ** attempt)
          continue
        }
        throw new RequestError("GreyGuard is unavailable.", { cause: error })
      } finally {
        globalThis.clearTimeout(timeout)
      }

      const payload = await this.#readPayload(response)
      if (response.ok) return payload

      if (retryableStatuses.has(response.status) && attempt + 1 < attempts) {
        await this.#sleep(200 * 2 ** attempt)
        continue
      }
      this.#raiseForStatus(response.status, payload)
    }

    throw new RequestError("GreyGuard request failed after retries.")
  }

  async #readPayload(response) {
    try {
      return await response.json()
    } catch {
      return { detail: "GreyGuard returned an invalid response." }
    }
  }

  #raiseForStatus(status, payload) {
    const safePayload = redact(payload)
    const message = String(safePayload.detail ?? "GreyGuard rejected the request.")
    if (status === 401) throw new AuthenticationError(message)
    if (status === 403) throw new AuthorizationError(message)
    throw new RequestError(message, {
      statusCode: status,
      details: safePayload,
    })
  }
}
