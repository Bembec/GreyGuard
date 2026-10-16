import { useState } from "react"

/**
 * Long card and stream lists (approvals, evidence, incidents, notifications) show a page of
 * items and grow on request, rather than rendering hundreds of cards at once. Tables use
 * DataTable's own paging instead.
 *
 * `resetKey` joins the list's filters into one string (a search, a status), so a new filter
 * starts again from the first page. It is a string on purpose: an object rebuilt on every render
 * would look like a new filter each time.
 */
export function useShowMore<T>(items: T[], resetKey: string, step = 25) {
  const [state, setState] = useState({ key: resetKey, count: step })
  // Reset during render when the filters change: no effect, no flash of the old count.
  const count = state.key === resetKey ? state.count : step
  if (state.key !== resetKey) setState({ key: resetKey, count: step })
  return {
    visible: items.slice(0, count),
    control: <ShowMore shown={Math.min(count, items.length)} total={items.length} onMore={() => setState({ key: resetKey, count: count + step })} />,
  }
}

export function ShowMore({ shown, total, onMore }: { shown: number; total: number; onMore: () => void }) {
  if (total <= shown) return null
  return (
    <div className="gg-show-more">
      <span>Showing {shown} of {total}</span>
      <button type="button" className="gg-button" onClick={onMore}>Show more</button>
    </div>
  )
}
