import {
  Bell,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Menu,
  Search,
  Star,
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
import { AccessDenied } from "../components/page/AccessDenied"
import { GlobalSearchDialog } from "../components/GlobalSearchDialog"
import { NavFlyout } from "../components/navigation/NavFlyout"
import { SidebarFavourites } from "../components/navigation/SidebarFavourites"
import { SidebarNavGroup } from "../components/navigation/SidebarNavGroup"
import { UserMenu } from "../components/navigation/UserMenu"
import { WorkspaceTabs } from "../components/navigation/WorkspaceTabs"
import { pageRefused } from "../config/navigation"
import { navigationGroups } from "../config/navigationGroups"
import { commandCenter, pageForPath, workspaceForPath, workspaces } from "../config/workspaces"
import { useAuth } from "../context/AuthContext"
import { matchesPermission } from "../hooks/usePermission"
import { recordRecentPage, toggleFavourite, usePageShortcuts } from "../lib/pageShortcuts"
import { recordPageView } from "../lib/pageViewAnalytics"
import { useShellSignals } from "../lib/shellSignals"
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

/** Stars the open page. Detail pages and the Command Center have no toggle: only list pages are kept. */
function FavouriteToggle({ path, label }: { path: string; label: string }) {
  const favourite = usePageShortcuts().favourites.includes(path)
  return (
    <button
      type="button"
      className={["topbar__favourite", favourite ? "topbar__favourite--on" : ""].join(" ")}
      onClick={() => toggleFavourite(path)}
      aria-pressed={favourite}
      aria-label={favourite ? `Remove ${label} from favourites` : `Add ${label} to favourites`}
      title={favourite ? "Remove from favourites" : "Add to favourites"}
    >
      <Star size={15} aria-hidden="true" />
    </button>
  )
}

export function AppShell() {
  const location = useLocation()
  useEffect(() => recordPageView(location.pathname), [location.pathname])
  useEffect(() => recordRecentPage(location.pathname), [location.pathname])
  const navigate = useNavigate()
  const { logout, administrator } = useAuth()
  const { unread, posture } = useShellSignals()

  const [collapsed, setCollapsed] =
    useState(false)
  const [mobileOpen, setMobileOpen] =
    useState(false)
  const [searchOpen, setSearchOpen] =
    useState(false)

  // One check for every route, so a bookmark or typed URL to a page this role may not use gets
  // the same explanation everywhere. Pages keep their own checks as a second layer.
  const routePage = pageForPath(location.pathname)
  const deniedPage = routePage && pageRefused(routePage, (check) => matchesPermission(administrator, check)) ? routePage : null

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


        <nav
          className="sidebar__nav gg-scrollbar"
          aria-label="Primary navigation"
        >
          {pinnedItem && (
            <NavLink
              to={pinnedItem.path}
              title={collapsed ? pinnedItem.label : pinnedItem.description}
              className={({ isActive }) =>
                ["sidebar__link", isActive ? "sidebar__link--active" : ""].join(" ")
              }
            >
              <span className="sidebar__link-icon">
                <pinnedItem.icon size={16} />
              </span>
              <span className="sidebar__link-copy">{pinnedItem.label}</span>
            </NavLink>
          )}

          {collapsed
            ? groupedWorkspaces.map(({ group, workspaces }) => (
                <NavFlyout key={group.id} group={group} workspaces={workspaces} />
              ))
            : <>
                <SidebarFavourites />
                {groupedWorkspaces.map(({ group, workspaces }) => (
                  <SidebarNavGroup key={group.id} group={group} workspaces={workspaces} />
                ))}
              </>}
        </nav>

        <div className="sidebar__footer">
          <div className={`sidebar__environment sidebar__environment--${posture.tone}`} role="status" title={posture.title}>
            <span className="sidebar__pulse" />

            <div>
              <strong>{posture.title}</strong>
              <span>{posture.detail}</span>
            </div>
          </div>

          <div className="sidebar__footer-row">
            <button
              type="button"
              className="sidebar__logout"
              onClick={logout}
              title="End session and remove administrator access"
            >
              <LogOut size={16} />
              <span>End session</span>
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
                <ChevronRight size={16} />
              ) : (
                <ChevronLeft size={16} />
              )}
            </button>
          </div>
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
                {currentPage.trail.map((part, index) => (
                  <span key={part}>
                    {index > 0 && <ChevronRight size={13} aria-hidden="true" />}
                    {part}
                  </span>
                ))}
                {currentPage.trail.length > 0 && <ChevronRight size={13} aria-hidden="true" />}
              </p>

              <div className="topbar__heading">
                <p className="topbar__title">{currentPage.label}</p>
                {location.pathname === currentPage.path && currentPage.path !== commandCenter.path && (
                  <FavouriteToggle path={currentPage.path} label={currentPage.label} />
                )}
              </div>
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
              aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
              onClick={() => navigate("/notifications")}
            >
              <Bell size={18} />
              {unread ? <span className="topbar__notification" /> : null}
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
          <WorkspaceTabs />
          <OfflineBanner />
          <CapacityBanner />
          {deniedPage ? <AccessDenied item={deniedPage} /> : <Outlet />}
        </main>
      </section>
      <GlobalSearchDialog open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  )
}
