import { ChevronDown, ChevronRight } from "lucide-react"
import { useState } from "react"
import { Link, useLocation } from "react-router-dom"

import type { NavigationGroup } from "../../config/navigationGroups"
import { visibleTabs, workspaceForPath, type Workspace } from "../../config/workspaces"
import { useAuth } from "../../context/AuthContext"

interface SidebarNavGroupProps {
  group: NavigationGroup
  workspaces: Workspace[]
}

const COLLAPSED_KEY = "greyguard_collapsed_nav_groups"

function readCollapsed(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(COLLAPSED_KEY) ?? "[]")
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : []
  } catch {
    return []
  }
}

function writeCollapsed(ids: string[]) {
  try {
    localStorage.setItem(COLLAPSED_KEY, JSON.stringify(ids))
  } catch {
    // A remembered open/closed state is a convenience only; ignore blocked storage.
  }
}

/**
 * One expandable product-domain section. It lists the domain's workspaces, never individual
 * pages: a workspace's pages are its tabs. A workspace is shown when the administrator may open
 * at least one of its tabs, and its link goes to the first of those.
 */
export function SidebarNavGroup({ group, workspaces }: SidebarNavGroupProps) {
  const { administrator } = useAuth()
  const location = useLocation()
  const current = workspaceForPath(location.pathname)
  const [expanded, setExpanded] = useState(() => !readCollapsed().includes(group.id))
  const visible = workspaces
    .map((workspace) => ({ workspace, tabs: visibleTabs(workspace, administrator) }))
    .filter(({ tabs }) => tabs.length > 0)
  if (!visible.length) return null

  const containsCurrent = visible.some(({ workspace }) => workspace.id === current?.id)
  // The section holding the open page always shows it, whatever was remembered.
  const open = expanded || containsCurrent
  const toggle = () => {
    const next = !open
    setExpanded(next)
    const others = readCollapsed().filter((id) => id !== group.id)
    writeCollapsed(next ? others : [...others, group.id])
  }

  const GroupIcon = group.icon
  return (
    <div className="sidebar-group">
      <button
        type="button"
        className="sidebar-group__header"
        onClick={toggle}
        aria-expanded={open}
        aria-controls={`sidebar-group-${group.id}`}
        title={group.description}
      >
        <GroupIcon size={16} />
        <span>{group.label}</span>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>
      {open && (
        <div id={`sidebar-group-${group.id}`} className="sidebar-group__items">
          {visible.map(({ workspace, tabs }) => {
            const active = workspace.id === current?.id
            return (
              <Link
                key={workspace.id}
                to={tabs[0].path}
                className={["sidebar__link", active ? "sidebar__link--active" : ""].join(" ")}
                aria-current={active ? "page" : undefined}
                title={workspace.description}
              >
                <span className="sidebar__link-icon">
                  <workspace.icon size={16} />
                </span>
                <span className="sidebar__link-copy">{workspace.label}</span>
                {tabs.length > 1 && <span className="sidebar__link-count" aria-label={`${tabs.length} sections`}>{tabs.length}</span>}
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
