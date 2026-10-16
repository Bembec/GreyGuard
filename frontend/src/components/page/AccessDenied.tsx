import { Lock } from "lucide-react"
import { Link } from "react-router-dom"

import { navigationPermission, type NavigationItem } from "../../config/navigation"
import { PageHeader } from "./PageHeader"

/** Why a role cannot open a page, in terms of the role it needs, never of what the page holds. */
export function accessRequirement(item: NavigationItem): { title: string; detail: string } {
  const check = navigationPermission(item)
  if (check && "installOperator" in check) {
    return {
      title: "Install operator access required",
      detail: "This page controls the whole GreyGuard installation, not one organization, so only an install operator can open it.",
    }
  }
  return {
    title: "Platform Administrator access required",
    detail: "This page changes how GreyGuard enforces controls, so only a Platform Administrator can open it.",
  }
}

/**
 * The one state shown when a role opens a page it may not use, whether from a bookmark, a shared
 * link or a typed URL. The server refuses the page's data either way; this explains why.
 */
export function AccessDenied({ item }: { item: NavigationItem }) {
  const requirement = accessRequirement(item)
  return (
    <main className="gg-page-pad">
      <PageHeader title={item.label} description={item.description} icon={<item.icon size={22} />} />
      <section className="gg-access-denied" aria-labelledby="gg-access-denied-title">
        <span className="gg-access-denied__icon" aria-hidden="true"><Lock size={24} /></span>
        <h2 id="gg-access-denied-title">{requirement.title}</h2>
        <p>{requirement.detail}</p>
        <p>If you need it, ask an administrator in your organization to change your role. Nothing from this page was loaded.</p>
        <Link className="gg-button" to="/dashboard">Go to the Command Center</Link>
      </section>
    </main>
  )
}
