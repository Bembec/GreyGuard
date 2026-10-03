const sensitiveMarkers = [
  "authorization",
  "credential",
  "password",
  "secret",
  "token",
  "x-agent-key",
  "api_key",
]

/** Return a recursively redacted copy suitable for application logs. */
export function redact(value) {
  if (Array.isArray(value)) {
    return value.map(redact)
  }

  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        sensitiveMarkers.some((marker) => key.toLowerCase().includes(marker))
          ? "[REDACTED]"
          : redact(item),
      ]),
    )
  }

  return value
}
