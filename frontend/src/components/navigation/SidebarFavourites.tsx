import { Star } from "lucide-react"
import { Link } from "react-router-dom"

import { visiblePages } from "../../config/workspaces"
import { useAuth } from "../../context/AuthContext"
import { usePageShortcuts } from "../../lib/pageShortcuts"

/**
 * The administrator's favourite pages, above the domains. Favourites are kept on this device and
 * filtered by permission here, so a page that is no longer allowed simply stops showing.
 */
export function SidebarFavourites() {
  const { administrator } = useAuth()
  const { favourites } = usePageShortcuts()
  const pages = visiblePages(favourites, administrator)
  if (!pages.length) return null

  // The workspace entry below already marks the open page, so favourites never claim it too.
  return (
    <div className="sidebar-group sidebar-favourites" role="group" aria-label="Favourites">
      <p className="sidebar-group__header sidebar-favourites__label">
        <Star size={16} aria-hidden="true" />
        <span>Favourites</span>
      </p>
      <div className="sidebar-group__items">
        {pages.map(({ item }) => (
          <Link key={item.path} to={item.path} className="sidebar__link sidebar__link--compact" title={item.description}>
            <span className="sidebar__link-icon">
              <item.icon size={16} />
            </span>
            <span className="sidebar__link-copy">
              <strong>{item.label}</strong>
            </span>
          </Link>
        ))}
      </div>
    </div>
  )
}
