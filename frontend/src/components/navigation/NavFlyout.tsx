import { useRef, useState } from "react"
import { NavLink } from "react-router-dom"

import type { NavigationGroup } from "../../config/navigationGroups"
import { navigationPermission, type NavigationItem } from "../../config/navigation"
import { useAuth } from "../../context/AuthContext"
import { useDismissableLayer } from "../../hooks/useDismissableLayer"
import { matchesPermission } from "../../hooks/usePermission"

interface NavFlyoutProps {
  group: NavigationGroup
  items: NavigationItem[]
}

/**
 * The collapsed-sidebar "mega-menu" surface: a group's icon button opens a keyboard-operable
 * popover listing that group's permission-visible items, giving collapsed mode real structure
 * instead of a bare, ungrouped icon rail.
 */
export function NavFlyout({ group, items }: NavFlyoutProps) {
  const { administrator } = useAuth()
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const panelRef = useDismissableLayer<HTMLDivElement>({ open, onClose: () => setOpen(false), trapFocus: true })

  const visible = items.filter((item) =>
    matchesPermission(administrator, navigationPermission(item)),
  )
  if (!visible.length) return null

  const GroupIcon = group.icon
  return (
    <div className="nav-flyout">
      <button
        ref={triggerRef}
        type="button"
        className="nav-flyout__trigger"
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={`nav-flyout-${group.id}`}
        onClick={() => setOpen((value) => !value)}
        title={group.label}
      >
        <GroupIcon size={19} />
      </button>
      {open && (
        <div
          id={`nav-flyout-${group.id}`}
          ref={panelRef}
          className="nav-flyout__panel"
          role="menu"
          aria-label={`${group.label} navigation`}
        >
          <p className="nav-flyout__label">{group.label}</p>
          {visible.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              role="menuitem"
              className={({ isActive }) => ["nav-flyout__item", isActive ? "nav-flyout__item--active" : ""].join(" ")}
              onClick={() => setOpen(false)}
            >
              <item.icon size={17} />
              <span>
                <strong>{item.label}</strong>
                <small>{item.description}</small>
              </span>
            </NavLink>
          ))}
        </div>
      )}
    </div>
  )
}
