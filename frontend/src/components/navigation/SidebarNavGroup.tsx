import { ChevronDown, ChevronRight } from "lucide-react"
import { useState } from "react"
import { NavLink } from "react-router-dom"

import type { NavigationGroup } from "../../config/navigationGroups"
import { navigationPermission, type NavigationItem } from "../../config/navigation"
import { useAuth } from "../../context/AuthContext"
import { matchesPermission } from "../../hooks/usePermission"

interface SidebarNavGroupProps {
  group: NavigationGroup
  items: NavigationItem[]
}

/** One expanded-sidebar group: a toggleable header plus its permission-visible items. */
export function SidebarNavGroup({ group, items }: SidebarNavGroupProps) {
  const { administrator } = useAuth()
  const [expanded, setExpanded] = useState(true)
  const visible = items.filter((item) =>
    matchesPermission(administrator, navigationPermission(item)),
  )
  if (!visible.length) return null

  const GroupIcon = group.icon
  return (
    <div className="sidebar-group">
      <button
        type="button"
        className="sidebar-group__header"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        aria-controls={`sidebar-group-${group.id}`}
      >
        <GroupIcon size={16} />
        <span>{group.label}</span>
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>
      {expanded && (
        <div id={`sidebar-group-${group.id}`} className="sidebar-group__items">
          {visible.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => ["sidebar__link", isActive ? "sidebar__link--active" : ""].join(" ")}
            >
              <span className="sidebar__link-icon">
                <item.icon size={18} />
              </span>
              <span className="sidebar__link-copy">
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
