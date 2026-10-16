/**
 * Saved views, version 1: personal (P7.5 batch 4d, approved 2026-10-16).
 *
 * A view is a name plus a page's filter query string, nothing else: it holds filters, never data,
 * so applying one in another organization shows that organization's records, filtered the same
 * way. Views live in this browser under the person's account id, like Command Center pins. That
 * means no new server surface and nothing that can cross tenants.
 *
 * The record shape (`page`, `query`, `scope`) is the one a later shared-views table will hold
 * (owner, org, visibility and role checks added server-side), so these can be migrated unchanged.
 */

export const MAX_VIEWS_PER_PAGE = 20
export const MAX_VIEW_NAME = 60

export interface SavedView {
  id: string
  name: string
  /** The page's own filter keys only, as a query string without "?". */
  query: string
  page: string
  scope: "personal"
  createdAt: string
}

export function viewsStorageKey(adminId: string, page: string): string {
  return `greyguard_saved_views:${adminId}:${page}`
}

/** Keeps only the page's own filter keys, in a stable order, so equal filters compare equal. */
export function viewQuery(params: URLSearchParams, keys: readonly string[]): string {
  const kept = new URLSearchParams()
  for (const key of [...keys].sort()) {
    const value = params.get(key)
    if (value !== null && value !== "") kept.set(key, value)
  }
  return kept.toString()
}

function isView(value: unknown, page: string): value is SavedView {
  if (!value || typeof value !== "object") return false
  const view = value as Record<string, unknown>
  return typeof view.id === "string" && view.id.length > 0 && view.id.length <= 64
    && typeof view.name === "string" && view.name.trim().length > 0 && view.name.length <= MAX_VIEW_NAME
    && typeof view.query === "string" && view.query.length <= 2000
    && view.page === page && view.scope === "personal"
    && typeof view.createdAt === "string"
}

/** Reads stored views, dropping anything malformed, foreign to this page, or over the limit. */
export function parseViews(raw: string | null, page: string, keys: readonly string[]): SavedView[] {
  let value: unknown
  try {
    value = JSON.parse(raw ?? "[]")
  } catch {
    return []
  }
  if (!Array.isArray(value)) return []
  const seen = new Set<string>()
  const views: SavedView[] = []
  for (const item of value) {
    if (!isView(item, page) || seen.has(item.id)) continue
    seen.add(item.id)
    // Re-filter the query: a stored view can never carry a key this page does not own.
    views.push({ ...item, name: item.name.trim(), query: viewQuery(new URLSearchParams(item.query), keys) })
    if (views.length === MAX_VIEWS_PER_PAGE) break
  }
  return views
}

export type SaveResult = { ok: true; views: SavedView[]; view: SavedView } | { ok: false; problem: string }

/** Adds a view, or replaces the one with the same name (names are unique per page, ignoring case). */
export function addView(views: SavedView[], name: string, query: string, page: string, id: string, now: string): SaveResult {
  const trimmed = name.trim()
  if (!trimmed) return { ok: false, problem: "Give the view a name." }
  if (trimmed.length > MAX_VIEW_NAME) return { ok: false, problem: `Names can be up to ${MAX_VIEW_NAME} characters.` }
  const existing = views.find((view) => view.name.toLowerCase() === trimmed.toLowerCase())
  if (!existing && views.length >= MAX_VIEWS_PER_PAGE) {
    return { ok: false, problem: `You can save up to ${MAX_VIEWS_PER_PAGE} views on a page. Delete one first.` }
  }
  const view: SavedView = { id: existing?.id ?? id, name: trimmed, query, page, scope: "personal", createdAt: existing?.createdAt ?? now }
  return { ok: true, view, views: existing ? views.map((item) => (item.id === existing.id ? view : item)) : [...views, view] }
}

export function renameView(views: SavedView[], id: string, name: string): SaveResult {
  const trimmed = name.trim()
  const target = views.find((view) => view.id === id)
  if (!target) return { ok: false, problem: "That view no longer exists." }
  if (!trimmed) return { ok: false, problem: "Give the view a name." }
  if (trimmed.length > MAX_VIEW_NAME) return { ok: false, problem: `Names can be up to ${MAX_VIEW_NAME} characters.` }
  if (views.some((view) => view.id !== id && view.name.toLowerCase() === trimmed.toLowerCase())) {
    return { ok: false, problem: "Another view already has that name." }
  }
  const view = { ...target, name: trimmed }
  return { ok: true, view, views: views.map((item) => (item.id === id ? view : item)) }
}

export function removeView(views: SavedView[], id: string): SavedView[] {
  return views.filter((view) => view.id !== id)
}
