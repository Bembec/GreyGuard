import {
  Bell,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Menu,
  Search,
  X,
} from "lucide-react"
import {
  useEffect,
  useMemo,
  useState,
} from "react"
import {
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom"

import { Logo } from "../components/brand/Logo"
import { GlobalSearchDialog } from "../components/GlobalSearchDialog"
import { NavFlyout } from "../components/navigation/NavFlyout"
import { SidebarNavGroup } from "../components/navigation/SidebarNavGroup"
import { UserMenu } from "../components/navigation/UserMenu"
import { WorkspaceTabs } from "../components/navigation/WorkspaceTabs"
import { navigationGroups } from "../config/navigationGroups"
import { commandCenter, pageForPath, workspaceForPath, workspaces } from "../config/workspaces"
import { useAuth } from "../context/AuthContext"
import { recordPageView } from "../lib/pageViewAnalytics"
import { CapacityBanner } from "../components/CapacityBanner"
import { OfflineBanner } from "../components/page/OfflineBanner"
import "../styles/shell.css"

const pinnedItem = commandCenter
const groupedWorkspaces = navigationGroups.map((group) => ({
  group,
  workspaces: workspaces.filter((workspace) => workspace.domain === group.id),
}))

function getPageInformation(pathname: string) {
  const workspace = workspaceForPath(pathname)
  const domain = navigationGroups.find((group) => group.id === workspace?.domain)
  const trail = [domain?.label, workspace?.label].filter((part): part is string => Boolean(part))
  if (pathname.startsWith("/agents/")) {
    return { label: "Agent Investigation", path: "/agents", trail: [...trail, "Agents"] }
  }
  if (pathname.startsWith("/requests/")) {
    return { label: "Request Investigation", path: "/requests", trail: [...trail, "Tool Requests"] }
  }
  const page = pageForPath(pathname) ?? commandCenter
  return { label: page.label, path: page.path, trail }
}

export function AppShell() {
  const location = useLocation()
  useEffect(() => recordPageView(location.pathname), [location.pathname])
  const navigate = useNavigate()
  const { logout } = useAuth()

  const [collapsed, setCollapsed] =
    useState(false)
  const [mobileOpen, setMobileOpen] =
    useState(false)
  const [searchOpen, setSearchOpen] =
    useState(false)

  const currentPage = useMemo(
    () => getPageInformation(location.pathname),
    [location.pathname],
  )

  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  // Dark only for now (owner decision, 2026-10-15): the shell and many page stylesheets still
  // hard-code dark colours, so the light theme stays hidden until they use the design tokens.
  useEffect(() => {
    document.documentElement.dataset.theme = "dark"
  }, [])

  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        setSearchOpen(true)
      }
    }
    document.addEventListener("keydown", keydown)
    return () => document.removeEventListener("keydown", keydown)
  }, [])

  return (
    <div
      className={[
        "app-shell",
        collapsed
          ? "app-shell--collapsed"
          : "",
      ].join(" ")}
    >
      <button
        type="button"
        className={[
          "shell-backdrop",
          mobileOpen
            ? "shell-backdrop--visible"
            : "",
        ].join(" ")}
        onClick={() => setMobileOpen(false)}
        aria-label="Close navigation"
      />

      <aside
        className={[
          "sidebar",
          mobileOpen
            ? "sidebar--mobile-open"
            : "",
        ].join(" ")}
      >
        <div className="sidebar__brand">
          <Logo variant={collapsed ? "symbol" : "horizontal"} />

          <button
            type="button"
            className="sidebar__mobile-close"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
          >
            <X size={20} />
          </button>
        </div>

        <div className="sidebar__environment">
          <span className="sidebar__pulse" />

          <div>
            <strong>Protected environment</strong>
            <span>Local control plane online</span>
          </div>
        </div>

        <nav
          className="sidebar__nav gg-scrollbar"
          aria-label="Primary navigation"
        >
          {pinnedItem && (
            <NavLink
              to={pinnedItem.path}
              className={({ isActive }) =>
                ["sidebar__link", isActive ? "sidebar__link--active" : ""].join(" ")
              }
            >
              <span className="sidebar__link-icon">
                <pinnedItem.icon size={19} />
              </span>
              {!collapsed && (
                <>
                  <span className="sidebar__link-copy">
                    <strong>{pinnedItem.label}</strong>
                    <small>{pinnedItem.description}</small>
                  </span>
                  <ChevronRight className="sidebar__link-arrow" size={16} />
                </>
              )}
            </NavLink>
          )}

          {collapsed
            ? groupedWorkspaces.map(({ group, workspaces }) => (
                <NavFlyout key={group.id} group={group} workspaces={workspaces} />
              ))
            : groupedWorkspaces.map(({ group, workspaces }) => (
                <SidebarNavGroup key={group.id} group={group} workspaces={workspaces} />
              ))}
        </nav>

        <div className="sidebar__footer">
          <button
            type="button"
            className="sidebar__logout"
            onClick={logout}
          >
            <LogOut size={18} />

            <span className="sidebar__link-copy">
              <strong>End session</strong>
              <small>Remove administrator access</small>
            </span>
          </button>

          <button
            type="button"
            className="sidebar__collapse"
            onClick={() =>
              setCollapsed((current) => !current)
            }
            aria-label={
              collapsed
                ? "Expand sidebar"
                : "Collapse sidebar"
            }
          >
            {collapsed ? (
              <ChevronRight size={18} />
            ) : (
              <ChevronLeft size={18} />
            )}
          </button>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="topbar__left">
            <button
              type="button"
              className="topbar__mobile-menu"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={21} />
            </button>

            <div>
              <p className="topbar__trail">
                GreyGuard
                {currentPage.trail.map((part) => (
                  <span key={part}>
                    <ChevronRight size={13} aria-hidden="true" />
                    {part}
                  </span>
                ))}
              </p>

              <p className="topbar__title">{currentPage.label}</p>
            </div>
          </div>

          <div className="topbar__actions">
            <button
              type="button"
              className="topbar__search"
              onClick={() => setSearchOpen(true)}
            >
              <Search size={17} />
              <span>Search control plane</span>
              <kbd>⌘ K</kbd>
            </button>

            <button
              type="button"
              className="topbar__icon-button"
              aria-label="Notifications"
              onClick={() => navigate("/notifications")}
            >
              <Bell size={18} />
              <span className="topbar__notification" />
            </button>

            <UserMenu />
          </div>
        </header>

        <main
          className={[
            "workspace__content",
            `workspace__content--${currentPage.path
              .replace("/", "")}`,
          ].join(" ")}
        >
          <div className="workspace__background">
            <div className="workspace__grid" />
            <div className="workspace__orb workspace__orb--one" />
            <div className="workspace__orb workspace__orb--two" />

            {location.pathname === "/dashboard" ? (
              <Logo variant="symbol" className="workspace__watermark" />
            ) : null}
          </div>

          <WorkspaceTabs />
          <OfflineBanner />
          <CapacityBanner />
          <Outlet />
        </main>
      </section>
      <GlobalSearchDialog open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  )
}
