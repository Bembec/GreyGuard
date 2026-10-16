import { useSyncExternalStore } from "react"

import { navigationItems } from "../config/navigation"
import { pagePathFor } from "../config/workspaces"

/**
 * Recent pages and favourites: per-device conveniences kept in localStorage. Only navigation page
 * paths are stored (never URLs carrying an agent, request or other identifier), and whoever reads
 * them still filters by the administrator's permissions before showing anything.
 */
const RECENT_KEY = "greyguard_recent_pages"
const FAVOURITES_KEY = "greyguard_favourite_pages"
const CHANGE_EVENT = "greyguard:page-shortcuts"
export const MAX_RECENT = 6
export const MAX_FAVOURITES = 8

const pagePaths = new Set(navigationItems.map((item) => item.path))

type Store = Pick<Storage, "getItem" | "setItem">

function browserStorage(): Store | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage
  } catch {
    return null
  }
}

export function readPaths(key: string, storage: Store | null = browserStorage()): string[] {
  try {
    const value = JSON.parse(storage?.getItem(key) ?? "[]")
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && pagePaths.has(item)) : []
  } catch {
    return []
  }
}

function writePaths(key: string, paths: string[], storage: Store | null = browserStorage()) {
  try {
    storage?.setItem(key, JSON.stringify(paths))
  } catch {
    // A convenience only: blocked storage simply means nothing is remembered.
  }
  if (typeof window !== "undefined") window.dispatchEvent(new Event(CHANGE_EVENT))
}

/** Remember a visit. Detail URLs count as their list page, and the Command Center is not recorded. */
export function recordRecentPage(pathname: string, storage: Store | null = browserStorage()) {
  const path = pagePathFor(pathname)
  if (!pagePaths.has(path) || path === "/dashboard") return
  const current = readPaths(RECENT_KEY, storage)
  if (current[0] === path) return
  writePaths(RECENT_KEY, [path, ...current.filter((item) => item !== path)].slice(0, MAX_RECENT), storage)
}

export function toggleFavourite(path: string, storage: Store | null = browserStorage()): boolean {
  if (!pagePaths.has(path)) return false
  const current = readPaths(FAVOURITES_KEY, storage)
  const next = current.includes(path) ? current.filter((item) => item !== path) : [...current, path].slice(-MAX_FAVOURITES)
  writePaths(FAVOURITES_KEY, next, storage)
  return next.includes(path)
}

let snapshot = { recent: [] as string[], favourites: [] as string[], key: "" }

function read() {
  const recent = readPaths(RECENT_KEY)
  const favourites = readPaths(FAVOURITES_KEY)
  const key = `${recent.join()}|${favourites.join()}`
  if (key !== snapshot.key) snapshot = { recent, favourites, key }
  return snapshot
}

function subscribe(onChange: () => void) {
  window.addEventListener(CHANGE_EVENT, onChange)
  window.addEventListener("storage", onChange)
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange)
    window.removeEventListener("storage", onChange)
  }
}

export function usePageShortcuts(): { recent: string[]; favourites: string[] } {
  return useSyncExternalStore(subscribe, read, read)
}
