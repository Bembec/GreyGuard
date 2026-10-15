import { ChevronDown, ChevronRight, Lightbulb } from "lucide-react"
import { useState, type ReactNode } from "react"

const STORAGE_KEY = "greyguard_collapsed_guidance"

function readCollapsed(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]")
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : []
  } catch {
    return []
  }
}

/**
 * Inline guidance on what a page is for and how its workflow runs. Open by default; an operator
 * who has read it can fold it away, and that choice is remembered on this device only.
 */
export function Guidance({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  const [open, setOpen] = useState(() => !readCollapsed().includes(id))
  const toggle = () => {
    const next = !open
    setOpen(next)
    try {
      const others = readCollapsed().filter((item) => item !== id)
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next ? others : [...others, id]))
    } catch {
      // Remembering the choice is a convenience only.
    }
  }
  return (
    <aside className="gg-guidance" aria-label={title}>
      <button type="button" className="gg-guidance__toggle" onClick={toggle} aria-expanded={open} aria-controls={`guidance-${id}`}>
        <Lightbulb size={16} aria-hidden="true" />
        <span>{title}</span>
        {open ? <ChevronDown size={15} aria-hidden="true" /> : <ChevronRight size={15} aria-hidden="true" />}
      </button>
      {open && <div id={`guidance-${id}`} className="gg-guidance__body">{children}</div>}
    </aside>
  )
}
