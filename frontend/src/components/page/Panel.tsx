import type { ReactNode } from "react"

interface PanelProps {
  title: string
  eyebrow?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
  id?: string
}

/** A titled section of a page. Its heading is an <h2>, under the page's single <h1>. */
export function Panel({ title, eyebrow, actions, children, className, id }: PanelProps) {
  const headingId = id ? `${id}-title` : undefined
  return (
    <section className={["gg-panel", className].filter(Boolean).join(" ")} aria-labelledby={headingId} id={id}>
      <header className="gg-panel__header">
        <div>
          {eyebrow && <p className="gg-panel__eyebrow">{eyebrow}</p>}
          <h2 id={headingId}>{title}</h2>
        </div>
        {actions && <div className="gg-panel__actions">{actions}</div>}
      </header>
      <div className="gg-panel__body">{children}</div>
    </section>
  )
}
