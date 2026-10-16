import { AlertTriangle, Bot, CheckSquare, Clock3, FileSearch, Search, ShieldAlert, X } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"

import { EmptyState, ErrorState, LoadingState } from "./AsyncState"
import { navigationGroups } from "../config/navigationGroups"
import { matchPages, pagePathFor, visiblePages, type PageMatch } from "../config/workspaces"
import { useAuth } from "../context/AuthContext"
import { useDismissableLayer } from "../hooks/useDismissableLayer"
import { usePageShortcuts } from "../lib/pageShortcuts"
import "../styles/global-search.css"

type SearchResult = { kind: "AGENT" | "REQUEST" | "APPROVAL" | "ALERT" | "AUDIT"; id: string; title: string; summary: string; path: string }
type SearchResponse = { query: string; results: SearchResult[]; count: number }
const API = import.meta.env.VITE_API_BASE_URL ?? "/api"
const RECENT_KEY = "greyguard_recent_searches"

export function readRecentSearches(storage: Pick<Storage, "getItem"> = localStorage): string[] {
  try {
    const value = JSON.parse(storage.getItem(RECENT_KEY) ?? "[]")
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string").slice(0, 5) : []
  } catch { return [] }
}

export function saveRecentSearch(query: string, storage: Pick<Storage, "getItem" | "setItem"> = localStorage) {
  const normalized = query.trim()
  if (normalized.length < 2) return
  storage.setItem(RECENT_KEY, JSON.stringify([normalized, ...readRecentSearches(storage).filter((item) => item.toLowerCase() !== normalized.toLowerCase())].slice(0, 5)))
}

function pageTrail({ item, workspace }: PageMatch) {
  return [navigationGroups.find((group) => group.id === workspace?.domain)?.label, workspace?.label].filter(Boolean).join(" › ") || item.description
}

const icons = { AGENT: Bot, REQUEST: FileSearch, APPROVAL: CheckSquare, ALERT: ShieldAlert, AUDIT: Clock3 }

export function GlobalSearchDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { administrator } = useAuth()
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const recent = useMemo(() => readRecentSearches(), [open, results])
  const shortcuts = usePageShortcuts()

  useDismissableLayer<HTMLDivElement>({ open, onClose, initialFocusRef: inputRef })

  useEffect(() => {
    if (!open || query.trim().length < 2) { setResults([]); setError(""); return }
    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      setLoading(true); setError("")
      try {
        const token = sessionStorage.getItem("greyguard_admin_pin")
        const response = await fetch(`${API}/search?q=${encodeURIComponent(query.trim())}`, { headers: { "X-Admin-Pin": token ?? "" }, signal: controller.signal })
        const body = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(body.detail ?? "Search is temporarily unavailable.")
        setResults((body as SearchResponse).results)
      } catch (reason) {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Search failed.")
      } finally { if (!controller.signal.aborted) setLoading(false) }
    }, 250)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [open, query])

  if (!open) return null
  const choose = (result: SearchResult) => { saveRecentSearch(query); onClose(); navigate(result.path) }
  const pages = matchPages(query, administrator)
  const goTo = (path: string) => { onClose(); navigate(path) }
  const pageList = (label: string, matches: PageMatch[], tag: string) => <div className="global-search__results global-search__pages" role="listbox" aria-label={label}>{matches.map((match) => <button type="button" role="option" aria-selected="false" key={match.item.path} onClick={() => goTo(match.item.path)}><span><match.item.icon size={18}/></span><div><strong>{match.item.label}</strong><small>{pageTrail(match)}</small></div><em>{tag}</em></button>)}</div>
  const browsing = query.trim().length < 2
  const favouritePages = browsing ? visiblePages(shortcuts.favourites, administrator) : []
  // A favourite is listed once, under Favourites, and the open page is not offered as a jump.
  const recentPages = browsing ? visiblePages(shortcuts.recent.filter((path) => !shortcuts.favourites.includes(path) && path !== pagePathFor(pathname)), administrator) : []
  return <div className="global-search" role="presentation">
    <button className="global-search__backdrop" type="button" onClick={onClose} aria-label="Close global search"/>
    <section role="dialog" aria-modal="true" aria-labelledby="global-search-title">
      <header><Search size={20}/><label htmlFor="global-search-input" id="global-search-title">Search control plane</label><button type="button" onClick={onClose} aria-label="Close search"><X size={19}/></button></header>
      <input ref={inputRef} id="global-search-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search pages, agents, requests, approvals, alerts or evidence…" autoComplete="off"/>
      <div className="global-search__body">
        {pages.length > 0 && pageList("Pages", pages, "PAGE")}
        {favouritePages.length > 0 && <div className="global-search__section"><strong>Favourites</strong>{pageList("Favourite pages", favouritePages, "FAVOURITE")}</div>}
        {recentPages.length > 0 && <div className="global-search__section"><strong>Recent pages</strong>{pageList("Recent pages", recentPages, "RECENT")}</div>}
        {browsing && <div className="global-search__recent"><strong>Recent searches</strong>{recent.length ? recent.map((item) => <button type="button" key={item} onClick={() => setQuery(item)}><Clock3 size={15}/>{item}</button>) : <p>No recent searches on this device.</p>}</div>}
        {loading && <LoadingState label="Searching GreyGuard" rows={4}/>}
        {!loading && error && <ErrorState message={error}/>}
        {!loading && !error && query.trim().length >= 2 && results.length === 0 && <EmptyState icon={<Search size={28}/>} title="No matching evidence" description="Try an agent name, request ID, action, alert, or outcome."/>}
        {!loading && !error && results.length > 0 && <div className="global-search__results" role="listbox" aria-label="Search results">{results.map((result) => { const Icon = icons[result.kind] ?? AlertTriangle; return <button type="button" role="option" aria-selected="false" key={`${result.kind}-${result.id}`} onClick={() => choose(result)}><span><Icon size={18}/></span><div><strong>{result.title}</strong><small>{result.summary}</small></div><em>{result.kind}</em></button> })}</div>}
      </div>
      <footer><span><kbd>↑</kbd><kbd>↓</kbd> review</span><span><kbd>esc</kbd> close</span><strong>Permission-filtered results</strong></footer>
    </section>
  </div>
}
