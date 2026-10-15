import type { ReactNode } from "react"
import { Link } from "react-router-dom"

export type StatTone = "neutral" | "info" | "success" | "warning" | "danger"

interface StatCardProps {
  label: string
  value: ReactNode
  hint?: ReactNode
  tone?: StatTone
  icon?: ReactNode
  /** When set, the card drills through to the page that holds these records. */
  to?: string
}

export function StatCard({ label, value, hint, tone = "neutral", icon, to }: StatCardProps) {
  const body = (
    <>
      {icon && <span className="gg-stat__icon" aria-hidden="true">{icon}</span>}
      <span className="gg-stat__label">{label}</span>
      <strong className="gg-stat__value">{value}</strong>
      {hint && <small className="gg-stat__hint">{hint}</small>}
    </>
  )
  return to
    ? <Link className={`gg-stat gg-stat--${tone} gg-stat--link`} to={to}>{body}</Link>
    : <article className={`gg-stat gg-stat--${tone}`}>{body}</article>
}

export function StatGrid({ children, label }: { children: ReactNode; label: string }) {
  return <section className="gg-stat-grid" aria-label={label}>{children}</section>
}
