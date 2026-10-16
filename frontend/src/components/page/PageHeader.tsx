import type { ReactNode } from "react"

interface PageHeaderProps {
  /**
   * Context the breadcrumb does not already give, such as the organization on the Command
   * Center. The workspace is in the top bar's breadcrumb, so it is not repeated here.
   */
  eyebrow?: string
  /** A kind of page within its workspace, such as "Investigation" on a detail page. */
  eyebrowSuffix?: string
  title: ReactNode
  description: ReactNode
  /** Accepted for older call sites; the reference consoles show no title icon, so it is not drawn. */
  icon?: ReactNode
  /** Contextual actions for the whole page, such as Refresh or Create. */
  actions?: ReactNode
  /** Optional status or meta line under the description. */
  meta?: ReactNode
}

/** The one page title (the page's only <h1>), what the page is for, and its page-wide actions. */
export function PageHeader({ eyebrow, eyebrowSuffix, title, description, actions, meta }: PageHeaderProps) {
  const label = eyebrow ?? eyebrowSuffix
  return (
    <header className="gg-page-header">
      <div className="gg-page-header__copy">
        {label && <p className="gg-page-header__eyebrow">{label}</p>}
        <h1>{title}</h1>
        <p className="gg-page-header__description">{description}</p>
        {meta && <div className="gg-page-header__meta">{meta}</div>}
      </div>
      {actions && <div className="gg-page-header__actions">{actions}</div>}
    </header>
  )
}
