import { Link, useLocation } from "react-router-dom"

import { pagePathFor, visibleTabs, workspaceForPath } from "../../config/workspaces"
import { useAuth } from "../../context/AuthContext"

/**
 * Page-level tabs for the open workspace. Each tab is a link to the page's own URL, so a tab can
 * be bookmarked, opened in a new window or reached directly. Only the tabs the administrator may
 * open are shown, and nothing renders for a workspace with a single visible page.
 */
export function WorkspaceTabs() {
  const { administrator } = useAuth()
  const location = useLocation()
  const workspace = workspaceForPath(location.pathname)
  if (!workspace) return null
  const tabs = visibleTabs(workspace, administrator)
  if (tabs.length < 2) return null

  const current = pagePathFor(location.pathname)
  return (
    <nav className="workspace-tabs" aria-label={`${workspace.label} sections`}>
      <div className="workspace-tabs__context">
        <workspace.icon size={16} aria-hidden="true" />
        <span>{workspace.label}</span>
      </div>
      <div className="workspace-tabs__list gg-scrollbar">
        {tabs.map((item) => {
          const active = item.path === current
          return (
            <Link
              key={item.path}
              to={item.path}
              className={["workspace-tabs__tab", active ? "workspace-tabs__tab--active" : ""].join(" ")}
              aria-current={active ? "page" : undefined}
              title={item.description}
            >
              <item.icon size={15} aria-hidden="true" />
              {item.label}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
