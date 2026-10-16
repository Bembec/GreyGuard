import { useLayoutEffect, useRef, useState, type CSSProperties } from "react"
import { createPortal } from "react-dom"
import { Link, useLocation } from "react-router-dom"

import type { NavigationGroup } from "../../config/navigationGroups"
import { pagePathFor, visibleTabs, type Workspace } from "../../config/workspaces"
import { useAuth } from "../../context/AuthContext"
import { useDismissableLayer } from "../../hooks/useDismissableLayer"

interface NavFlyoutProps {
  group: NavigationGroup
  workspaces: Workspace[]
}

/**
 * The collapsed-sidebar mega-menu: a domain's icon opens a keyboard-operable panel showing each
 * permitted workspace with its permitted pages beneath it, so the whole domain is one step away.
 */
export function NavFlyout({ group, workspaces }: NavFlyoutProps) {
  const { administrator } = useAuth()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  // The sidebar clips its overflow, so the panel is fixed to the viewport beside its trigger.
  const [position, setPosition] = useState<CSSProperties>({})
  const triggerRef = useRef<HTMLButtonElement>(null)
  const panelRef = useDismissableLayer<HTMLDivElement>({ open, onClose: () => setOpen(false), trapFocus: true })

  // Once painted, lift the panel so all of it sits on screen; one taller than the window scrolls.
  useLayoutEffect(() => {
    const panel = panelRef.current
    if (!open || !panel) return
    const margin = 8
    const top = Math.max(margin, Math.min(panel.getBoundingClientRect().top, window.innerHeight - panel.offsetHeight - margin))
    if (top !== panel.getBoundingClientRect().top) setPosition((current) => ({ ...current, top }))
  }, [open, panelRef])

  const visible = workspaces
    .map((workspace) => ({ workspace, tabs: visibleTabs(workspace, administrator) }))
    .filter(({ tabs }) => tabs.length > 0)
  if (!visible.length) return null

  const currentPage = pagePathFor(location.pathname)
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
        onClick={() => {
          const rect = triggerRef.current?.getBoundingClientRect()
          if (rect) setPosition({ top: Math.max(8, rect.top), left: rect.right + 12 })
          setOpen((value) => !value)
        }}
        title={group.label}
      >
        <GroupIcon size={17} />
      </button>
      {/* On <body>: the sidebar is its own stacking context, which would keep the open menu
          beneath fixed banners such as the offline prompt. */}
      {open && createPortal(
        <div
          id={`nav-flyout-${group.id}`}
          ref={panelRef}
          className="nav-flyout__panel"
          style={position}
          role="menu"
          aria-label={`${group.label} navigation`}
        >
          <p className="nav-flyout__label">{group.label}</p>
          {visible.map(({ workspace, tabs }) => (
            <div key={workspace.id} className="nav-flyout__workspace" role="group" aria-label={workspace.label}>
              <p className="nav-flyout__workspace-label">
                <workspace.icon size={15} />
                {workspace.label}
              </p>
              {tabs.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  role="menuitem"
                  className={["nav-flyout__item", item.path === currentPage ? "nav-flyout__item--active" : ""].join(" ")}
                  onClick={() => setOpen(false)}
                >
                  <item.icon size={17} />
                  <span>
                    <strong>{item.label}</strong>
                    <small>{item.description}</small>
                  </span>
                </Link>
              ))}
            </div>
          ))}
        </div>,
        document.body,
      )}
    </div>
  )
}
