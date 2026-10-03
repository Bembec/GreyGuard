import { describe, expect, it, vi } from "vitest"

import {
  AuthenticationError,
  GreyGuardClient,
  ScopeValidationError,
  redact,
} from "../../../sdk/javascript/src/index.js"

const response = (status: number, payload: object) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  })

describe("GreyGuard JavaScript SDK", () => {
  it("redacts credentials from serialization and structured logs", () => {
    const client = new GreyGuardClient({
      baseUrl: "http://greyguard.test",
      agentName: "agent-one",
      credential: "gg_super_secret",
    })

    expect(JSON.stringify(client)).not.toContain("gg_super_secret")
    expect(redact({ api_token: "token", safe: "visible" })).toEqual({
      api_token: "[REDACTED]",
      safe: "visible",
    })
  })

  it("blocks undeclared scopes before transmission", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>()
    const client = new GreyGuardClient({
      baseUrl: "http://greyguard.test",
      agentName: "agent-one",
      credential: "credential",
      scopes: ["read_file"],
      fetch,
    })

    await expect(client.submit({ action: "delete_file" })).rejects.toBeInstanceOf(
      ScopeValidationError,
    )
    expect(fetch).not.toHaveBeenCalled()
  })

  it("reuses one idempotency key across transient retries", async () => {
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(response(503, { detail: "retry" }))
      .mockResolvedValueOnce(
        response(201, {
          request_id: "request-1",
          action: "read_file",
          execution_status: "COMPLETED",
        }),
      )
    const client = new GreyGuardClient({
      baseUrl: "http://greyguard.test",
      agentName: "agent-one",
      credential: "credential",
      fetch,
      sleep: async () => undefined,
    })

    const result = await client.submit({ action: "read_file" })
    const firstHeaders = fetch.mock.calls[0]?.[1]?.headers as Record<string, string>
    const secondHeaders = fetch.mock.calls[1]?.[1]?.headers as Record<string, string>

    expect(result.request_id).toBe("request-1")
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(firstHeaders["Idempotency-Key"]).toBe(secondHeaders["Idempotency-Key"])
  })

  it("does not retry state-sensitive policy evaluation", async () => {
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValue(response(503, { detail: "unavailable" }))
    const client = new GreyGuardClient({
      baseUrl: "http://greyguard.test",
      agentName: "agent-one",
      credential: "credential",
      maxRetries: 4,
      fetch,
    })

    await expect(client.evaluate("read_file")).rejects.toThrow("unavailable")
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it("maps authentication failures to a typed error", async () => {
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValue(response(401, { detail: "Invalid agent credential." }))
    const client = new GreyGuardClient({
      baseUrl: "http://greyguard.test",
      agentName: "agent-one",
      credential: "credential",
      fetch,
    })

    await expect(client.getRequest("request-1")).rejects.toBeInstanceOf(
      AuthenticationError,
    )
  })
})

