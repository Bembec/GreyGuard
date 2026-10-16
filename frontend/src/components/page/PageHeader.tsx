import type { ReactNode } from "react"
import { useLocation } from "react-router-dom"

import { workspaceForPath } from "../../config/workspaces"

interface PageHeaderProps {
  /** Defaults to the page's workspace, so regrouping navigation never leaves a stale label. */
  eyebrow?: string
  /** Appended to the derived eyebrow, such as "Investigation" on a detail page. */
  eyebrowSuffix?: string
  title: ReactNode
  description: ReactNode
  icon?: ReactNode
  /** Contextual actions for the whole page, such as Refresh or Create. */
  actions?: ReactNode
  /** Optional status or meta line under the description. */
  meta?: ReactNode
}

/** The one page title (the page's only <h1>), what the page is for, and its page-wide actions. */
export function PageHeader({ eyebrow, eyebrowSuffix, title, description, icon, actions, meta }: PageHeaderProps) {
  const { pathname } = useLocation()
  const label = eyebrow ?? [workspaceForPath(pathname)?.label, eyebrowSuffix].filter(Boolean).join(" · ")
  return (
    <header className="gg-page-header">
      {icon && <span className="gg-page-header__icon" aria-hidden="true">{icon}</span>}
      <div className="gg-page-header__copy">
        <p className="gg-page-header__eyebrow">{label}</p>
        <h1>{title}</h1>
        <p className="gg-page-header__description">{description}</p>
        {meta && <div className="gg-page-header__meta">{meta}</div>}
      </div>
      {actions && <div className="gg-page-header__actions">{actions}</div>}
    </header>
  )
}
