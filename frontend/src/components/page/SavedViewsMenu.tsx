import { Bookmark, Check, ChevronDown, Pencil, Trash2 } from "lucide-react"
import { useEffect, useId, useRef, useState } from "react"
import { useSearchParams } from "react-router-dom"

import { useAuth } from "../../context/AuthContext"
import { useDismissableLayer } from "../../hooks/useDismissableLayer"
import {
  MAX_VIEW_NAME,
  addView,
  parseViews,
  removeView,
  renameView,
  viewQuery,
  viewsStorageKey,
  type SavedView,
} from "../../lib/savedViews"

interface SavedViewsMenuProps {
  /** A stable page id, e.g. "tool-requests". */
  page: string
  /** Every URL key this page's filters own; nothing else is saved or applied. */
  keys: readonly string[]
}

function newId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `v_${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}`
}

/** One person's views for one page, in this browser. Blocked storage means views last the visit. */
function useSavedViews(page: string, keys: readonly string[]) {
  const { administrator } = useAuth()
  const key = administrator?.admin_id ? viewsStorageKey(administrator.admin_id, page) : null
  const [views, setViews] = useState<SavedView[]>(() => {
    try {
      return key ? parseViews(localStorage.getItem(key), page, keys) : []
    } catch {
      return []
    }
  })
  const store = (next: SavedView[]) => {
    setViews(next)
    try {
      if (key) localStorage.setItem(key, JSON.stringify(next))
    } catch {
      // A convenience only.
    }
  }
  return [views, store] as const
}

export function SavedViewsMenu({ page, keys }: SavedViewsMenuProps) {
  const id = useId()
  const [params, setParams] = useSearchParams()
  const [views, store] = useSavedViews(page, keys)
  const [open, setOpen] = useState(false)
  const [name, setName] = useState("")
  const [renaming, setRenaming] = useState<string | null>(null)
  const [renameText, setRenameText] = useState("")
  const [problem, setProblem] = useState<string | null>(null)
  const nameRef = useRef<HTMLInputElement>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const panelRef = useDismissableLayer<HTMLDivElement>({ open, onClose: () => setOpen(false), initialFocusRef: nameRef })

  const current = viewQuery(params, keys)
  const active = views.find((view) => view.query === current)

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", close)
    return () => document.removeEventListener("mousedown", close)
  }, [open])

  function apply(view: SavedView) {
    setParams((existing) => {
      const next = new URLSearchParams(existing)
      for (const owned of keys) next.delete(owned)
      // parseViews already dropped any key this page does not own.
      for (const [owned, value] of new URLSearchParams(view.query)) if (keys.includes(owned)) next.set(owned, value)
      return next
    })
    setOpen(false)
  }

  function save() {
    const result = addView(views, name, current, page, newId(), new Date().toISOString())
    if (!result.ok) {
      setProblem(result.problem)
      return
    }
    store(result.views)
    setName("")
    setProblem(null)
  }

  function rename(viewId: string) {
    const result = renameView(views, viewId, renameText)
    if (!result.ok) {
      setProblem(result.problem)
      return
    }
    store(result.views)
    setRenaming(null)
    setProblem(null)
  }

  return (
    <div className="gg-views" ref={wrapperRef}>
      <button
        type="button"
        className="gg-views__trigger"
        aria-expanded={open}
        aria-controls={`${id}-panel`}
        onClick={() => setOpen((value) => !value)}
      >
        <Bookmark size={14} aria-hidden="true" />
        {active ? active.name : "Views"}
        <ChevronDown size={14} aria-hidden="true" />
      </button>
      {open && (
        <div className="gg-views__panel" id={`${id}-panel`} ref={panelRef} role="dialog" aria-label="Saved views">
          {views.length === 0 ? (
            <p className="gg-views__empty">No saved views yet. Set the filters you want, then save them here.</p>
          ) : (
            <ul className="gg-views__list">
              {views.map((view) => (
                <li key={view.id}>
                  {renaming === view.id ? (
                    <form className="gg-views__rename" onSubmit={(event) => { event.preventDefault(); rename(view.id) }}>
                      <input
                        aria-label={`New name for ${view.name}`}
                        value={renameText}
                        maxLength={MAX_VIEW_NAME}
                        onChange={(event) => setRenameText(event.target.value)}
                        autoFocus
                      />
                      <button type="submit" className="gg-views__icon" aria-label="Save name"><Check size={14} aria-hidden="true" /></button>
                    </form>
                  ) : (
                    <>
                      <button type="button" className="gg-views__apply" aria-current={view.id === active?.id ? "true" : undefined} onClick={() => apply(view)}>
                        {view.name}
                      </button>
                      <button type="button" className="gg-views__icon" aria-label={`Rename ${view.name}`} onClick={() => { setRenaming(view.id); setRenameText(view.name); setProblem(null) }}>
                        <Pencil size={13} aria-hidden="true" />
                      </button>
                      <button type="button" className="gg-views__icon" aria-label={`Delete ${view.name}`} onClick={() => store(removeView(views, view.id))}>
                        <Trash2 size={13} aria-hidden="true" />
                      </button>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
          <form className="gg-views__save" onSubmit={(event) => { event.preventDefault(); save() }}>
            <label htmlFor={`${id}-name`}>Save the current filters as</label>
            <div>
              <input
                id={`${id}-name`}
                ref={nameRef}
                value={name}
                maxLength={MAX_VIEW_NAME}
                placeholder="e.g. Blocked, last 7 days"
                onChange={(event) => setName(event.target.value)}
              />
              <button type="submit" className="gg-button">Save</button>
            </div>
          </form>
          {problem && <p className="gg-views__problem" role="alert">{problem}</p>}
          <p className="gg-views__note">Saved in this browser, for your account only. A view keeps filters, not data.</p>
        </div>
      )}
    </div>
  )
}
