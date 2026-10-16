import { useIsFetching, useQueryClient, type Query } from "@tanstack/react-query"
import { RefreshCw } from "lucide-react"
import { useEffect, useState, useSyncExternalStore } from "react"

import { relativeTime } from "../page/timeFormat"

/** The shell's own signals (bell, status line) say nothing about how fresh the page's data is. */
export function isPageQuery(query: Pick<Query, "queryKey" | "isActive" | "state">): boolean {
  return query.queryKey[0] !== "shell" && query.isActive() && query.state.dataUpdatedAt > 0
}

/**
 * How old the data on screen is: the OLDEST successful load among the page's active queries, so
 * the line never makes a page look fresher than its stalest panel. Undefined when the page
 * loads nothing through the query cache (it then shows nothing rather than a guess).
 */
export function oldestUpdate(queries: Pick<Query, "queryKey" | "isActive" | "state">[]): number | undefined {
  const times = queries.filter(isPageQuery).map((query) => query.state.dataUpdatedAt)
  return times.length ? Math.min(...times) : undefined
}

/** Evidence freshness for whichever page is open, with one refresh for everything on it. */
export function ShellFreshness() {
  const queryClient = useQueryClient()
  const cache = queryClient.getQueryCache()
  // Re-read whenever any query changes; the snapshot is a number, so React skips equal values.
  const updatedAt = useSyncExternalStore(
    (onChange) => cache.subscribe(onChange),
    () => oldestUpdate(cache.getAll()),
  )
  const fetching = useIsFetching({ predicate: (query) => query.queryKey[0] !== "shell" }) > 0
  // Keep "2 minutes ago" true while nothing refetches.
  const [, setTick] = useState(0)
  useEffect(() => {
    const timer = window.setInterval(() => setTick((tick) => tick + 1), 15_000)
    return () => window.clearInterval(timer)
  }, [])

  if (updatedAt === undefined) return null
  const refresh = () => void queryClient.refetchQueries({ type: "active", predicate: (query) => query.queryKey[0] !== "shell" })
  return (
    <div className="shell-freshness" role="status" aria-live="off">
      <span title={new Date(updatedAt).toLocaleString()}>Updated {relativeTime(new Date(updatedAt).toISOString()).replace("Just now", "just now")}</span>
      <button type="button" className="topbar__icon-button" onClick={refresh} disabled={fetching} aria-label="Refresh this page's data" title="Refresh this page's data">
        <RefreshCw size={15} className={fetching ? "gg-spin" : undefined} aria-hidden="true" />
      </button>
    </div>
  )
}
