import type { ReactNode } from "react"

interface PageHeaderProps {
  eyebrow: string
  title: ReactNode
  description: ReactNode
  icon?: ReactNode
  /** Contextual actions for the whole page, such as Refresh or Create. */
  actions?: ReactNode
  /** Optional status or meta line under the description. */
  meta?: ReactNode
}

/** The one page title (the page's only <h1>), what the page is for, and its page-wide actions. */
export function PageHeader({ eyebrow, title, description, icon, actions, meta }: PageHeaderProps) {
  return (
    <header className="gg-page-header">
      {icon && <span className="gg-page-header__icon" aria-hidden="true">{icon}</span>}
      <div className="gg-page-header__copy">
        <p className="gg-page-header__eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="gg-page-header__description">{description}</p>
        {meta && <div className="gg-page-header__meta">{meta}</div>}
      </div>
      {actions && <div className="gg-page-header__actions">{actions}</div>}
    </header>
  )
}
