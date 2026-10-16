/**
 * Time ranges for the evidence lists (P7.5 batch 4d). The server does the filtering: these helpers
 * only turn a choice into `since`/`until` and back, and keep that choice in the URL.
 *
 * Relative presets stay relative in the URL (`range=24h`), so a bookmark means "the last 24 hours"
 * whenever it is opened. A custom range is absolute (`since=…&until=…`). Anything invalid falls
 * back to the page's default and is never an error: a bad link still opens the page.
 */

export const RANGE_PRESETS = [
  { id: "1h", label: "Last hour", phrase: "the last hour", ms: 60 * 60 * 1000 },
  { id: "24h", label: "Last 24 hours", phrase: "the last 24 hours", ms: 24 * 60 * 60 * 1000 },
  { id: "7d", label: "Last 7 days", phrase: "the last 7 days", ms: 7 * 24 * 60 * 60 * 1000 },
  { id: "30d", label: "Last 30 days", phrase: "the last 30 days", ms: 30 * 24 * 60 * 60 * 1000 },
] as const

export type RangePreset = (typeof RANGE_PRESETS)[number]["id"]

export type TimeRangeValue =
  | { kind: "preset"; preset: RangePreset }
  | { kind: "custom"; since: string; until: string | null }

/** The URL keys a range uses; a page's saved views include them with its own filter keys. */
export const RANGE_KEYS = ["range", "since", "until"] as const

/** The server's ceiling; it may allow less (configured retention) and says so with a 422. */
export const MAX_LOOKBACK_DAYS = 400

const DAY_MS = 24 * 60 * 60 * 1000

function presetOf(id: string | null): (typeof RANGE_PRESETS)[number] | undefined {
  return RANGE_PRESETS.find((preset) => preset.id === id)
}

function validInstant(value: string | null): Date | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

/** Whether a custom range is one the server would accept, so the URL never holds a broken one. */
export function customRangeProblem(since: string | null, until: string | null, now = Date.now()): string | null {
  const start = validInstant(since)
  if (!start) return "Choose a start date and time."
  if (start.getTime() < now - MAX_LOOKBACK_DAYS * DAY_MS) return `The start can be at most ${MAX_LOOKBACK_DAYS} days ago.`
  if (start.getTime() > now) return "The start cannot be in the future."
  if (until !== null) {
    const end = validInstant(until)
    if (!end) return "Choose a valid end date and time."
    if (end.getTime() <= start.getTime()) return "The end must be after the start."
  }
  return null
}

export function readRange(params: URLSearchParams, fallback: RangePreset, now = Date.now()): TimeRangeValue {
  const preset = presetOf(params.get("range"))
  if (preset) return { kind: "preset", preset: preset.id }
  const since = params.get("since")
  const until = params.get("until")
  if (since && !customRangeProblem(since, until, now)) {
    return { kind: "custom", since: new Date(since).toISOString(), until: until ? new Date(until).toISOString() : null }
  }
  return { kind: "preset", preset: fallback }
}

/** A copy of params holding this range. The page default is left out, so plain URLs stay plain. */
export function writeRange(params: URLSearchParams, value: TimeRangeValue, fallback: RangePreset): URLSearchParams {
  const next = new URLSearchParams(params)
  next.delete("range")
  next.delete("since")
  next.delete("until")
  if (value.kind === "preset") {
    if (value.preset !== fallback) next.set("range", value.preset)
  } else {
    next.set("since", value.since)
    if (value.until) next.set("until", value.until)
  }
  return next
}

/** The bounds to send. Presets are resolved at request time, so a refresh moves the window. */
export function rangeBounds(value: TimeRangeValue, now = Date.now()): { since: string; until?: string } {
  if (value.kind === "custom") return value.until ? { since: value.since, until: value.until } : { since: value.since }
  const preset = presetOf(value.preset) ?? RANGE_PRESETS[1]
  return { since: new Date(now - preset.ms).toISOString() }
}

/** `since=…[&until=…]`, ready to append to an evidence list's query string. */
export function rangeQuery(value: TimeRangeValue, now = Date.now()): string {
  const bounds = rangeBounds(value, now)
  const query = new URLSearchParams({ since: bounds.since })
  if (bounds.until) query.set("until", bounds.until)
  return query.toString()
}

/** A stable cache key: presets by name, so the 15-second refresh does not fork the cache. */
export function rangeKey(value: TimeRangeValue): string {
  return value.kind === "preset" ? value.preset : `${value.since}..${value.until ?? "now"}`
}

function formatInstant(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
}

/** For sentences: "in the last 24 hours", "between 1 Oct, 09:00 and 2 Oct, 09:00". */
export function describeRange(value: TimeRangeValue): string {
  if (value.kind === "preset") return `in ${presetOf(value.preset)?.phrase ?? "the selected range"}`
  return value.until
    ? `between ${formatInstant(value.since)} and ${formatInstant(value.until)}`
    : `since ${formatInstant(value.since)}`
}

/** The next wider preset, for "Widen to …" on an empty result; null when there is none. */
export function widerPreset(value: TimeRangeValue): (typeof RANGE_PRESETS)[number] | null {
  if (value.kind === "custom") return RANGE_PRESETS[RANGE_PRESETS.length - 1]
  const index = RANGE_PRESETS.findIndex((preset) => preset.id === value.preset)
  return RANGE_PRESETS[index + 1] ?? null
}

/** `datetime-local` speaks the viewer's local time without a zone; these convert both ways. */
export function toLocalInput(iso: string): string {
  const date = new Date(iso)
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 16)
}

export function fromLocalInput(local: string): string | null {
  if (!local) return null
  const date = new Date(local)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}
