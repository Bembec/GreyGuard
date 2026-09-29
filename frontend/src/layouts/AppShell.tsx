import {
  Activity,
  Bell,
  Bot,
  Boxes,
  CheckSquare,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Command,
  FileSearch,
  Fingerprint,
  LogOut,
  Menu,
  Moon,
  Radar,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sun,
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
} from "react-router-dom"

import { navigationItems } from "../config/navigation"
import { useAuth } from "../context/AuthContext"
import "../styles/shell.css"

const iconMap = {
  "/dashboard": Command,
  "/agents": Bot,
  "/requests": Boxes,
  "/approvals": CheckSquare,
  "/policies": SlidersHorizontal,
  "/risk": Radar,
  "/audit": FileSearch,
  "/authentication": Fingerprint,
  "/sandbox": ClipboardList,
  "/settings": Settings,
}

function getPageInformation(pathname: string) {
  return (
    navigationItems.find(
      (item) => item.path === pathname,
    ) ?? navigationItems[0]
  )
}

export function AppShell() {
  const location = useLocation()
  const { logout } = useAuth()

  const [collapsed, setCollapsed] =
    useState(false)
  const [mobileOpen, setMobileOpen] =
    useState(false)
  const [theme, setTheme] = useState<
    "dark" | "light"
  >("dark")

  const currentPage = useMemo(
    () => getPageInformation(location.pathname),
    [location.pathname],
  )

  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

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
          <span className="sidebar__brand-icon">
            <ShieldCheck size={25} />
          </span>

          <div className="sidebar__brand-copy">
            <strong>GREYGUARD</strong>
            <span>CONTROL PLANE</span>
          </div>

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
          <p className="sidebar__section-label">
            Security operations
          </p>

          {navigationItems.map((item) => {
            const Icon =
              iconMap[
                item.path as keyof typeof iconMap
              ] ?? Activity

            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  [
                    "sidebar__link",
                    isActive
                      ? "sidebar__link--active"
                      : "",
                  ].join(" ")
                }
              >
                <span className="sidebar__link-icon">
                  <Icon size={19} />
                </span>

                <span className="sidebar__link-copy">
                  <strong>{item.label}</strong>
                  <small>{item.description}</small>
                </span>

                <ChevronRight
                  className="sidebar__link-arrow"
                  size={16}
                />
              </NavLink>
            )
          })}
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
              <p>
                GreyGuard
                <ChevronRight size={13} />
                {currentPage.label}
              </p>

              <h1>{currentPage.label}</h1>
            </div>
          </div>

          <div className="topbar__actions">
            <button
              type="button"
              className="topbar__search"
            >
              <Search size={17} />
              <span>Search control plane</span>
              <kbd>⌘ K</kbd>
            </button>

            <button
              type="button"
              className="topbar__icon-button"
              onClick={() =>
                setTheme((current) =>
                  current === "dark"
                    ? "light"
                    : "dark",
                )
              }
              aria-label="Change appearance"
            >
              {theme === "dark" ? (
                <Sun size={18} />
              ) : (
                <Moon size={18} />
              )}
            </button>

            <button
              type="button"
              className="topbar__icon-button"
              aria-label="Notifications"
            >
              <Bell size={18} />
              <span className="topbar__notification" />
            </button>

            <div className="topbar__operator">
              <span>
                <ShieldCheck size={17} />
              </span>

              <div>
                <strong>Administrator</strong>
                <small>Verified session</small>
              </div>
            </div>
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
              <img
                className="workspace__watermark"
                src="/brand/greyguard-symbol.png"
                alt=""
                aria-hidden="true"
              />
            ) : null}
          </div>

          <Outlet />
        </main>
      </section>
    </div>
  )
}
