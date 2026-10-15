import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react"
import { useMemo, useState, type ReactNode } from "react"

import { sortRows, type Column } from "./tableSort"

export type { Column }

interface DataTableProps<T> {
  label: string
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string
  empty: ReactNode
  pageSize?: number
  initialSort?: { key: string; direction: "asc" | "desc" }
  /** Optional highlight for a row, e.g. a critical item. */
  rowTone?: (row: T) => "danger" | "warning" | undefined
}

/**
 * A sortable, paged table. Sorting and paging happen over the rows given, so a page passes the
 * rows its filters selected. Row actions belong in a cell as real links or buttons, which keeps
 * every row reachable by keyboard.
 */
export function DataTable<T>({ label, columns, rows, rowKey, empty, pageSize = 10, initialSort, rowTone }: DataTableProps<T>) {
  const [sort, setSort] = useState(initialSort)
  const [page, setPage] = useState(0)
  const sorted = useMemo(
    () => sortRows(rows, columns.find((column) => column.key === sort?.key), sort?.direction ?? "asc"),
    [rows, columns, sort],
  )
  const pages = Math.max(1, Math.ceil(sorted.length / pageSize))
  const current = Math.min(page, pages - 1)
  const visible = sorted.slice(current * pageSize, current * pageSize + pageSize)

  if (!rows.length) return <>{empty}</>

  const toggleSort = (key: string) => {
    setSort((existing) => existing?.key === key ? { key, direction: existing.direction === "asc" ? "desc" : "asc" } : { key, direction: "asc" })
    setPage(0)
  }

  return (
    <div className="gg-table">
      <div className="gg-table__scroll gg-scrollbar">
        <table aria-label={label}>
          <thead>
            <tr>
              {columns.map((column) => {
                const active = sort?.key === column.key
                return (
                  <th
                    key={column.key}
                    scope="col"
                    className={[column.align === "end" ? "is-end" : "", column.secondary ? "is-secondary" : ""].join(" ")}
                    aria-sort={active ? (sort!.direction === "asc" ? "ascending" : "descending") : undefined}
                  >
                    {column.sortValue ? (
                      <button type="button" onClick={() => toggleSort(column.key)}>
                        {column.header}
                        {active ? (sort!.direction === "asc" ? <ArrowUp size={13} aria-hidden="true" /> : <ArrowDown size={13} aria-hidden="true" />) : <ArrowUpDown size={13} aria-hidden="true" />}
                      </button>
                    ) : column.header}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={rowKey(row)} data-tone={rowTone?.(row)}>
                {columns.map((column) => (
                  <td key={column.key} className={[column.align === "end" ? "is-end" : "", column.secondary ? "is-secondary" : ""].join(" ")}>
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <nav className="gg-table__pager" aria-label={`${label} pages`}>
          <span>{current * pageSize + 1}–{Math.min(sorted.length, (current + 1) * pageSize)} of {sorted.length}</span>
          <button type="button" onClick={() => setPage(current - 1)} disabled={current === 0} aria-label="Previous page"><ChevronLeft size={16} /></button>
          <button type="button" onClick={() => setPage(current + 1)} disabled={current >= pages - 1} aria-label="Next page"><ChevronRight size={16} /></button>
        </nav>
      )}
    </div>
  )
}
