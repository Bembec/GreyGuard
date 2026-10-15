import type { ReactNode } from "react"

export interface Column<T> {
  key: string
  header: string
  render: (row: T) => ReactNode
  /** When set, the column can be sorted by this value. */
  sortValue?: (row: T) => string | number | null | undefined
  align?: "start" | "end"
  /** Hidden on narrow screens. */
  secondary?: boolean
}

export function compareValues(a: string | number | null | undefined, b: string | number | null | undefined): number {
  if (a === b) return 0
  if (a === null || a === undefined) return 1
  if (b === null || b === undefined) return -1
  if (typeof a === "number" && typeof b === "number") return a - b
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" })
}

export function sortRows<T>(rows: T[], column: Column<T> | undefined, direction: "asc" | "desc"): T[] {
  if (!column?.sortValue) return rows
  const value = column.sortValue
  const sorted = [...rows].sort((a, b) => compareValues(value(a), value(b)))
  return direction === "asc" ? sorted : sorted.reverse()
}
