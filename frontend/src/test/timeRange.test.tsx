// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter, useLocation } from "react-router-dom"
import { afterEach, describe, expect, it } from "vitest"

import { RangeNotice, TimeRangeControl } from "../components/page/TimeRangeControl"
import { useClearUrlParams, useTimeRangeParam, useUrlParam } from "../hooks/useUrlState"
import {
  MAX_LOOKBACK_DAYS,
  customRangeProblem,
  fromLocalInput,
  rangeBounds,
  rangeKey,
  rangeQuery,
  readRange,
  toLocalInput,
  widerPreset,
  writeRange,
  type TimeRangeValue,
} from "../lib/timeRange"

afterEach(cleanup)

const NOW = Date.parse("2026-10-16T12:00:00Z")
const DAY = 86_400_000
const params = (query: string) => new URLSearchParams(query)

describe("reading a range from the URL", () => {
  it("reads a preset and falls back to the page default", () => {
    expect(readRange(params("range=7d"), "24h", NOW)).toEqual({ kind: "preset", preset: "7d" })
    expect(readRange(params(""), "24h", NOW)).toEqual({ kind: "preset", preset: "24h" })
  })

  it("treats anything invalid as the default rather than an error", () => {
    for (const query of [
      "range=99y",
      "since=garbage",
      `since=${new Date(NOW - (MAX_LOOKBACK_DAYS + 1) * DAY).toISOString()}`,
      `since=${new Date(NOW + DAY).toISOString()}`,
      "since=2026-10-15T00:00:00Z&until=2026-10-14T00:00:00Z",
      "since=2026-10-15T00:00:00Z&until=nope",
    ]) {
      expect(readRange(params(query), "7d", NOW), query).toEqual({ kind: "preset", preset: "7d" })
    }
  })

  it("reads a custom range as UTC instants", () => {
    expect(readRange(params("since=2026-10-15T10:00:00%2B02:00&until=2026-10-16T00:00:00Z"), "24h", NOW)).toEqual({
      kind: "custom", since: "2026-10-15T08:00:00.000Z", until: "2026-10-16T00:00:00.000Z",
    })
  })
})

describe("writing a range to the URL", () => {
  it("leaves the default out so plain links stay plain, and keeps other params", () => {
    expect(writeRange(params("q=x&range=7d"), { kind: "preset", preset: "24h" }, "24h").toString()).toBe("q=x")
    expect(writeRange(params("q=x"), { kind: "preset", preset: "30d" }, "24h").toString()).toBe("q=x&range=30d")
  })

  it("replaces a preset with a custom range and the other way round", () => {
    const custom: TimeRangeValue = { kind: "custom", since: "2026-10-01T00:00:00.000Z", until: null }
    const written = writeRange(params("range=7d"), custom, "24h")
    expect(written.get("range")).toBeNull()
    expect(written.get("since")).toBe(custom.since)
    expect(writeRange(written, { kind: "preset", preset: "7d" }, "24h").toString()).toBe("range=7d")
  })

  it("round-trips", () => {
    const value: TimeRangeValue = { kind: "custom", since: "2026-10-01T00:00:00.000Z", until: "2026-10-02T00:00:00.000Z" }
    expect(readRange(writeRange(params(""), value, "24h"), "24h", NOW)).toEqual(value)
  })
})

describe("bounds sent to the server", () => {
  it("resolves presets at request time", () => {
    expect(rangeBounds({ kind: "preset", preset: "24h" }, NOW)).toEqual({ since: "2026-10-15T12:00:00.000Z" })
    expect(rangeQuery({ kind: "preset", preset: "1h" }, NOW)).toBe("since=2026-10-16T11%3A00%3A00.000Z")
  })

  it("sends a custom range as given", () => {
    expect(rangeQuery({ kind: "custom", since: "2026-10-01T00:00:00.000Z", until: "2026-10-02T00:00:00.000Z" }))
      .toBe("since=2026-10-01T00%3A00%3A00.000Z&until=2026-10-02T00%3A00%3A00.000Z")
  })

  it("keys the cache by preset name, so a refresh does not fork it", () => {
    expect(rangeKey({ kind: "preset", preset: "7d" })).toBe("7d")
  })

  it("offers the next wider preset and stops at the widest", () => {
    expect(widerPreset({ kind: "preset", preset: "24h" })?.id).toBe("7d")
    expect(widerPreset({ kind: "preset", preset: "30d" })).toBeNull()
  })
})

describe("custom range checks", () => {
  it("matches the server's rules", () => {
    expect(customRangeProblem(null, null, NOW)).toMatch(/start/)
    expect(customRangeProblem(new Date(NOW - (MAX_LOOKBACK_DAYS + 1) * DAY).toISOString(), null, NOW)).toMatch(/400 days/)
    expect(customRangeProblem(new Date(NOW + DAY).toISOString(), null, NOW)).toMatch(/future/)
    expect(customRangeProblem("2026-10-10T00:00:00Z", "2026-10-10T00:00:00Z", NOW)).toMatch(/after/)
    expect(customRangeProblem("2026-10-10T00:00:00Z", null, NOW)).toBeNull()
  })

  it("converts the viewer's local input to UTC and back", () => {
    const iso = "2026-10-10T08:30:00.000Z"
    expect(fromLocalInput(toLocalInput(iso))).toBe(iso)
    expect(fromLocalInput("")).toBeNull()
  })
})

function Location() {
  const location = useLocation()
  return <output data-testid="url">{location.search}</output>
}

function Harness() {
  const [status, setStatus] = useUrlParam("status", "ALL", ["ALL", "OPEN"])
  const [range, setRange] = useTimeRangeParam("24h")
  const clear = useClearUrlParams(["status"])
  return (
    <>
      <span data-testid="status">{status}</span>
      <button type="button" onClick={() => setStatus("OPEN")}>open</button>
      <button type="button" onClick={clear}>clear</button>
      <TimeRangeControl value={range} onChange={setRange} />
      <Location />
    </>
  )
}

const renderAt = (url: string) => render(<MemoryRouter initialEntries={[url]}><Harness /></MemoryRouter>)

describe("filters in the URL", () => {
  it("reads only allowed values and drops the rest to the default", () => {
    renderAt("/x?status=EVIL")
    expect(screen.getByTestId("status").textContent).toBe("ALL")
  })

  it("writes a filter, and clearing removes only the page's own keys", () => {
    renderAt("/x?range=7d")
    fireEvent.click(screen.getByText("open"))
    expect(screen.getByTestId("url").textContent).toBe("?range=7d&status=OPEN")
    fireEvent.click(screen.getByText("clear"))
    expect(screen.getByTestId("url").textContent).toBe("?range=7d")
  })

  it("puts a chosen preset in the URL and the default back out of it", () => {
    renderAt("/x")
    const select = screen.getByTestId("time-range") as HTMLSelectElement
    fireEvent.change(select, { target: { value: "30d" } })
    expect(screen.getByTestId("url").textContent).toBe("?range=30d")
    fireEvent.change(select, { target: { value: "24h" } })
    expect(screen.getByTestId("url").textContent).toBe("")
  })

  it("applies a valid custom range and refuses an inverted one", () => {
    renderAt("/x")
    fireEvent.change(screen.getByTestId("time-range"), { target: { value: "custom" } })
    const from = screen.getByLabelText("From") as HTMLInputElement
    const to = screen.getByLabelText("To") as HTMLInputElement
    const apply = screen.getByRole("button", { name: "Apply" }) as HTMLButtonElement
    const start = toLocalInput(new Date(Date.now() - 2 * DAY).toISOString())
    const before = toLocalInput(new Date(Date.now() - 3 * DAY).toISOString())
    act(() => { fireEvent.change(from, { target: { value: start } }); fireEvent.change(to, { target: { value: before } }) })
    expect(apply.disabled).toBe(true)
    expect(screen.getByText("The end must be after the start.")).toBeTruthy()
    act(() => { fireEvent.change(to, { target: { value: "" } }) })
    expect(apply.disabled).toBe(false)
    fireEvent.click(apply)
    expect(screen.getByTestId("url").textContent).toMatch(/^\?since=/)
  })
})

describe("the range notice", () => {
  it("says when the list is capped, and that open work is always shown", () => {
    render(<RangeNotice range={{ kind: "preset", preset: "24h" }} shown={200} truncated noun="requests" openNote="Pending requests are always shown." />)
    const text = screen.getByTestId("range-notice").textContent
    expect(text).toContain("Newest 200 requests in the last 24 hours.")
    expect(text).toContain("More exist")
    expect(text).toContain("Pending requests are always shown.")
  })

  it("does not claim a cap when there is none", () => {
    render(<RangeNotice range={{ kind: "preset", preset: "7d" }} shown={3} noun="incidents" />)
    expect(screen.getByTestId("range-notice").textContent).toBe("3 incidents in the last 7 days.")
  })
})
