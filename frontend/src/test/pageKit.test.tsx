// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { DataTable } from "../components/page/DataTable"
import { compareValues, sortRows, type Column } from "../components/page/tableSort"
import { greetingFor, relativeTime } from "../components/page/timeFormat"
import { toneFor } from "../components/page/tones"

type Row = { name: string; score: number | null }
const columns: Column<Row>[] = [
  { key: "name", header: "Name", sortValue: (row) => row.name, render: (row) => row.name },
  { key: "score", header: "Score", sortValue: (row) => row.score, render: (row) => String(row.score) },
]

describe("table sorting", () => {
  it("sorts numbers numerically and text naturally", () => {
    expect(compareValues(2, 10)).toBeLessThan(0)
    expect(compareValues("agent-2", "agent-10")).toBeLessThan(0)
  })

  it("always puts missing values last when ascending", () => {
    const rows = [{ name: "a", score: null }, { name: "b", score: 3 }, { name: "c", score: 1 }]
    expect(sortRows(rows, columns[1], "asc").map((row) => row.name)).toEqual(["c", "b", "a"])
  })

  it("leaves rows untouched for a column that cannot sort", () => {
    const rows = [{ name: "b", score: 1 }, { name: "a", score: 2 }]
    expect(sortRows(rows, { key: "x", header: "X", render: () => null }, "asc")).toBe(rows)
  })
})

describe("DataTable", () => {
  afterEach(cleanup)
  const rows = Array.from({ length: 12 }, (_, index) => ({ name: `agent-${index + 1}`, score: index }))

  it("pages its rows and sorts when a header is pressed", () => {
    render(<DataTable label="Agents" columns={columns} rows={rows} rowKey={(row) => row.name} empty={<p>none</p>} pageSize={5} />)
    const table = screen.getByRole("table", { name: "Agents" })
    expect(within(table).getAllByRole("row")).toHaveLength(6)
    expect(screen.getByText("1–5 of 12")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Next page" }))
    expect(screen.getByText("6–10 of 12")).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: /Score/ }))
    fireEvent.click(screen.getByRole("button", { name: /Score/ }))
    const header = screen.getByRole("columnheader", { name: /Score/ })
    expect(header.getAttribute("aria-sort")).toBe("descending")
    // Sorting returns to the first page.
    expect(within(table).getAllByRole("row")[1].textContent).toContain("agent-12")
  })

  it("shows the empty state when there are no rows", () => {
    render(<DataTable label="Agents" columns={columns} rows={[]} rowKey={(row) => row.name} empty={<p>No agents yet</p>} />)
    expect(screen.getByText("No agents yet")).toBeTruthy()
    expect(screen.queryByRole("table")).toBeNull()
  })
})

describe("formatting", () => {
  const now = Date.parse("2026-10-15T12:00:00Z")

  it("describes recent times relatively", () => {
    expect(relativeTime("2026-10-15T11:59:30Z", now)).toBe("Just now")
    expect(relativeTime("2026-10-15T11:55:00Z", now)).toBe("5 min ago")
    expect(relativeTime("2026-10-15T09:00:00Z", now)).toBe("3 h ago")
    expect(relativeTime("2026-10-13T12:00:00Z", now)).toBe("2 d ago")
    expect(relativeTime(null, now)).toBe("Never")
    expect(relativeTime("not a date", now)).toBe("not a date")
  })

  it("greets by the time of day", () => {
    expect(greetingFor(8)).toBe("Good morning")
    expect(greetingFor(14)).toBe("Good afternoon")
    expect(greetingFor(21)).toBe("Good evening")
    expect(greetingFor(2)).toBe("Good evening")
  })

  it("gives security outcomes a tone, and unknown words a neutral one", () => {
    expect(toneFor("BLOCK")).toBe("danger")
    expect(toneFor("pending")).toBe("warning")
    expect(toneFor("ALLOW")).toBe("success")
    expect(toneFor("SOMETHING_NEW")).toBe("neutral")
    expect(toneFor(null)).toBe("neutral")
  })
})
