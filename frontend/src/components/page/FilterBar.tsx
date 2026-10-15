import { Search } from "lucide-react"
import type { ReactNode } from "react"

export interface FilterOption {
  value: string
  label: string
  count?: number
}

interface FilterBarProps {
  /** Free-text filter over the records shown. */
  search?: { value: string; onChange: (value: string) => void; placeholder: string; label?: string }
  /** One exclusive set of quick filters, such as status. */
  options?: { value: string; onChange: (value: string) => void; items: FilterOption[]; label: string }
  /** Extra controls, such as selects. */
  children?: ReactNode
  /** e.g. "12 of 40 shown". */
  summary?: ReactNode
}

export function FilterBar({ search, options, children, summary }: FilterBarProps) {
  return (
    <div className="gg-filter-bar" role="search">
      {search && (
        <label className="gg-filter-bar__search">
          <Search size={16} aria-hidden="true" />
          <span className="gg-sr-only">{search.label ?? search.placeholder}</span>
          <input type="search" value={search.value} placeholder={search.placeholder} onChange={(event) => search.onChange(event.target.value)} />
        </label>
      )}
      {options && (
        <div className="gg-filter-bar__options" role="group" aria-label={options.label}>
          {options.items.map((item) => (
            <button
              type="button"
              key={item.value}
              className={options.value === item.value ? "is-active" : ""}
              aria-pressed={options.value === item.value}
              onClick={() => options.onChange(item.value)}
            >
              {item.label}
              {item.count !== undefined && <span>{item.count}</span>}
            </button>
          ))}
        </div>
      )}
      {children}
      {summary && <p className="gg-filter-bar__summary" aria-live="polite">{summary}</p>}
    </div>
  )
}
