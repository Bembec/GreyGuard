from pathlib import Path


root = Path(__file__).resolve().parents[1]

files = {
    "frontend/src/config/navigation.ts": """
export interface NavigationItem {
  label: string
  path: string
  description: string
}

export const navigationItems: NavigationItem[] = [
  {
    label: "Command Center",
    path: "/dashboard",
    description: "Security overview and live posture",
  },
  {
    label: "Agents",
    path: "/agents",
    description: "Identity, scopes and agent states",
  },
  {
    label: "Tool Requests",
    path: "/requests",
    description: "Controlled execution requests",
  },
  {
    label: "Approvals",
    path: "/approvals",
    description: "Human authorization queue",
  },
  {
    label: "Policies",
    path: "/policies",
    description: "Action permissions and boundaries",
  },
  {
    label: "Risk Center",
    path: "/risk",
    description: "Risk scores and suspensions",
  },
  {
    label: "Audit Trail",
    path: "/audit",
    description: "Security decision evidence",
  },
  {
    label: "Authentication",
    path: "/authentication",
    description: "Credential and scope events",
  },
  {
    label: "Sandbox",
    path: "/sandbox",
    description: "Contained tool environment",
  },
  {
    label: "Settings",
    path: "/settings",
    description: "Interface and control settings",
  },
]
""",
    "frontend/src/layouts/AppShell.tsx": """
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
""",
    "frontend/src/pages/DashboardPage.tsx": """
import {
  Activity,
  Bot,
  CheckCircle2,
  Clock3,
  LockKeyhole,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react"

import { useAuth } from "../context/AuthContext"
import "../styles/pages.css"

export function DashboardPage() {
  const { agents } = useAuth()

  const activeAgents = agents.filter(
    (agent) => agent.agent_status === "ACTIVE",
  ).length

  const suspendedAgents = agents.filter(
    (agent) =>
      agent.agent_status === "SUSPENDED",
  ).length

  const highRiskAgents = agents.filter(
    (agent) =>
      agent.risk_level === "HIGH"
      || agent.risk_level === "CRITICAL",
  ).length

  return (
    <section className="page">
      <header className="page-heading">
        <div>
          <p className="page-heading__eyebrow">
            Live security posture
          </p>

          <h2>
            Good afternoon,
            <span> Administrator.</span>
          </h2>

          <p>
            GreyGuard is monitoring identity,
            permission, risk and controlled execution
            across your registered agents.
          </p>
        </div>

        <div className="page-heading__status">
          <span />
          Control plane protected
        </div>
      </header>

      <div className="metric-grid">
        <article className="metric-card metric-card--cyan">
          <div className="metric-card__icon">
            <Bot size={22} />
          </div>

          <div>
            <span>Registered agents</span>
            <strong>{agents.length}</strong>
            <small>
              {activeAgents} currently active
            </small>
          </div>
        </article>

        <article className="metric-card metric-card--green">
          <div className="metric-card__icon">
            <ShieldCheck size={22} />
          </div>

          <div>
            <span>Active agents</span>
            <strong>{activeAgents}</strong>
            <small>Operating within policy</small>
          </div>
        </article>

        <article className="metric-card metric-card--amber">
          <div className="metric-card__icon">
            <ShieldAlert size={22} />
          </div>

          <div>
            <span>High-risk agents</span>
            <strong>{highRiskAgents}</strong>
            <small>Requires closer review</small>
          </div>
        </article>

        <article className="metric-card metric-card--red">
          <div className="metric-card__icon">
            <LockKeyhole size={22} />
          </div>

          <div>
            <span>Suspended agents</span>
            <strong>{suspendedAgents}</strong>
            <small>Execution access refused</small>
          </div>
        </article>
      </div>

      <div className="dashboard-grid">
        <article className="dashboard-card dashboard-card--posture">
          <div className="dashboard-card__heading">
            <div>
              <p>Containment posture</p>
              <h3>Security boundaries</h3>
            </div>

            <span className="status-chip status-chip--success">
              Enforced
            </span>
          </div>

          <div className="posture-orbit">
            <div className="posture-orbit__ring posture-orbit__ring--outer" />
            <div className="posture-orbit__ring posture-orbit__ring--inner" />

            <div className="posture-orbit__core">
              <ShieldCheck size={34} />
              <strong>Protected</strong>
              <span>Gateway sealed</span>
            </div>

            <span className="posture-node posture-node--one">
              Identity
            </span>
            <span className="posture-node posture-node--two">
              Scope
            </span>
            <span className="posture-node posture-node--three">
              Policy
            </span>
            <span className="posture-node posture-node--four">
              Sandbox
            </span>
          </div>
        </article>

        <article className="dashboard-card">
          <div className="dashboard-card__heading">
            <div>
              <p>Control pipeline</p>
              <h3>Request enforcement</h3>
            </div>

            <Activity size={20} />
          </div>

          <div className="pipeline">
            {[
              ["Identity", "Credential verified"],
              ["Scope", "Action boundary checked"],
              ["Policy", "Decision calculated"],
              ["Approval", "Human gate enforced"],
              ["Execution", "Sandbox evidence stored"],
            ].map(([name, description], index) => (
              <div
                className="pipeline__step"
                key={name}
              >
                <span>
                  {index + 1}
                </span>

                <div>
                  <strong>{name}</strong>
                  <small>{description}</small>
                </div>

                <CheckCircle2 size={17} />
              </div>
            ))}
          </div>
        </article>

        <article className="dashboard-card dashboard-card--wide">
          <div className="dashboard-card__heading">
            <div>
              <p>Registered estate</p>
              <h3>Agent risk overview</h3>
            </div>

            <span className="dashboard-card__updated">
              <Clock3 size={15} />
              Current session
            </span>
          </div>

          <div className="agent-table">
            <div className="agent-table__header">
              <span>Agent</span>
              <span>Status</span>
              <span>Risk</span>
              <span>Score</span>
            </div>

            {agents.slice(0, 6).map((agent) => (
              <div
                className="agent-table__row"
                key={agent.agent_name}
              >
                <span className="agent-name">
                  <span>
                    <Bot size={16} />
                  </span>
                  {agent.agent_name}
                </span>

                <span
                  className={[
                    "status-chip",
                    agent.agent_status === "ACTIVE"
                      ? "status-chip--success"
                      : "status-chip--danger",
                  ].join(" ")}
                >
                  {agent.agent_status}
                </span>

                <span>
                  {agent.risk_level}
                </span>

                <span className="risk-score">
                  <span
                    style={{
                      width: `${Math.min(
                        agent.risk_score,
                        100,
                      )}%`,
                    }}
                  />
                  {agent.risk_score}
                </span>
              </div>
            ))}
          </div>
        </article>
      </div>
    </section>
  )
}
""",
    "frontend/src/pages/SectionPage.tsx": """
import {
  ArrowRight,
  ShieldCheck,
} from "lucide-react"

interface SectionPageProps {
  eyebrow: string
  title: string
  description: string
  features: string[]
}

export function SectionPage({
  eyebrow,
  title,
  description,
  features,
}: SectionPageProps) {
  return (
    <section className="page">
      <header className="page-heading">
        <div>
          <p className="page-heading__eyebrow">
            {eyebrow}
          </p>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
      </header>

      <div className="section-grid">
        {features.map((feature, index) => (
          <article
            className="section-card"
            key={feature}
          >
            <span className="section-card__number">
              {String(index + 1).padStart(2, "0")}
            </span>

            <ShieldCheck size={22} />

            <h3>{feature}</h3>

            <p>
              This control is part of GreyGuard’s
              protected multi-agent security plane.
            </p>

            <button type="button">
              Inspect control
              <ArrowRight size={16} />
            </button>
          </article>
        ))}
      </div>
    </section>
  )
}
""",
    "frontend/src/routes/AppRoutes.tsx": """
import {
  Navigate,
  Route,
  Routes,
} from "react-router-dom"

import { useAuth } from "../context/AuthContext"
import { AppShell } from "../layouts/AppShell"
import { DashboardPage } from "../pages/DashboardPage"
import { LoginPage } from "../pages/LoginPage"
import { SectionPage } from "../pages/SectionPage"

export function AppRoutes() {
  const { isAuthenticated } = useAuth()

  if (!isAuthenticated) {
    return <LoginPage />
  }

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route
          index
          element={
            <Navigate
              to="/dashboard"
              replace
            />
          }
        />

        <Route
          path="/dashboard"
          element={<DashboardPage />}
        />

        <Route
          path="/agents"
          element={
            <SectionPage
              eyebrow="Identity control"
              title="Agents and identities"
              description="Inspect independent agent states, credentials and assigned action scopes."
              features={[
                "Registered agent estate",
                "Credential lifecycle",
                "Scope boundaries",
                "Suspension controls",
              ]}
            />
          }
        />

        <Route
          path="/requests"
          element={
            <SectionPage
              eyebrow="Execution control"
              title="Tool requests"
              description="Follow every request from policy evaluation through controlled execution evidence."
              features={[
                "Request queue",
                "Decision state",
                "Execution timeline",
                "Replay protection",
              ]}
            />
          }
        />

        <Route
          path="/approvals"
          element={
            <SectionPage
              eyebrow="Human authority"
              title="Approval center"
              description="Review sensitive actions before GreyGuard permits execution."
              features={[
                "Pending approvals",
                "Decision context",
                "Reviewer evidence",
                "Denied operations",
              ]}
            />
          }
        />

        <Route
          path="/policies"
          element={
            <SectionPage
              eyebrow="Policy enforcement"
              title="Permission policies"
              description="Understand how actions become ALLOW, ASK, BLOCK or REFUSED."
              features={[
                "Action matrix",
                "Risk weights",
                "Scope mapping",
                "Threshold controls",
              ]}
            />
          }
        />

        <Route
          path="/risk"
          element={
            <SectionPage
              eyebrow="Risk intelligence"
              title="Risk center"
              description="Track accumulated risk, blocked attempts and automatic agent suspension."
              features={[
                "Risk ranking",
                "Threshold monitoring",
                "Suspension events",
                "Administrative reset",
              ]}
            />
          }
        />

        <Route
          path="/audit"
          element={
            <SectionPage
              eyebrow="Decision evidence"
              title="Audit trail"
              description="Investigate policy outcomes and persistent security evidence."
              features={[
                "Policy events",
                "Approval records",
                "Execution evidence",
                "Correlation history",
              ]}
            />
          }
        />

        <Route
          path="/authentication"
          element={
            <SectionPage
              eyebrow="Identity assurance"
              title="Authentication"
              description="Review credential verification, scope decisions, rotation and revocation."
              features={[
                "Authentication events",
                "Scope denials",
                "Credential rotation",
                "Credential revocation",
              ]}
            />
          }
        />

        <Route
          path="/sandbox"
          element={
            <SectionPage
              eyebrow="Contained execution"
              title="Sandbox"
              description="Inspect GreyGuard’s restricted filesystem and controlled tool boundary."
              features={[
                "Allowed tools",
                "Path containment",
                "Dry-run mode",
                "Sandbox resources",
              ]}
            />
          }
        />

        <Route
          path="/settings"
          element={
            <SectionPage
              eyebrow="Control configuration"
              title="Settings"
              description="Manage interface preferences and inspect control-plane configuration."
              features={[
                "Appearance",
                "Reduced motion",
                "API environment",
                "Security information",
              ]}
            />
          }
        />

        <Route
          path="*"
          element={
            <Navigate
              to="/dashboard"
              replace
            />
          }
        />
      </Route>
    </Routes>
  )
}
""",
    "frontend/src/App.tsx": """
import { AuthProvider } from "./context/AuthContext"
import { AppRoutes } from "./routes/AppRoutes"

function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}

export default App
""",
    "frontend/src/styles/shell.css": """
.app-shell {
  --active-sidebar-width: var(--gg-sidebar-width);
  display: grid;
  min-height: 100vh;
  grid-template-columns:
    var(--active-sidebar-width)
    minmax(0, 1fr);
  transition:
    grid-template-columns var(--gg-transition);
}

.app-shell--collapsed {
  --active-sidebar-width:
    var(--gg-sidebar-collapsed);
}

.sidebar {
  position: fixed;
  z-index: 50;
  inset: 0 auto 0 0;
  display: flex;
  width: var(--active-sidebar-width);
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid var(--gg-border);
  background:
    linear-gradient(
      180deg,
      rgba(10, 19, 33, 0.98),
      rgba(4, 9, 17, 0.99)
    );
  transition:
    width var(--gg-transition),
    transform var(--gg-transition);
}

.sidebar__brand {
  display: flex;
  min-height: var(--gg-topbar-height);
  align-items: center;
  gap: 0.8rem;
  padding: 0 1.15rem;
  border-bottom: 1px solid var(--gg-border);
}

.sidebar__brand-icon {
  display: grid;
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  place-items: center;
  border: 1px solid var(--gg-border-strong);
  border-radius: 13px;
  color: var(--gg-cyan);
  background: rgba(34, 211, 238, 0.07);
  box-shadow: var(--gg-glow-cyan);
}

.sidebar__brand-copy,
.sidebar__link-copy {
  min-width: 0;
  transition:
    opacity var(--gg-transition),
    transform var(--gg-transition);
}

.sidebar__brand-copy {
  display: grid;
  gap: 0.22rem;
}

.sidebar__brand-copy strong {
  letter-spacing: 0.11em;
}

.sidebar__brand-copy span {
  color: var(--gg-text-muted);
  font-size: 0.59rem;
  letter-spacing: 0.16em;
}

.sidebar__environment {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 1rem;
  padding: 0.8rem;
  border: 1px solid rgba(34, 197, 94, 0.15);
  border-radius: var(--gg-radius-md);
  background: rgba(34, 197, 94, 0.05);
}

.sidebar__pulse {
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  border-radius: 50%;
  background: var(--gg-green);
  box-shadow: 0 0 14px var(--gg-green);
  animation: shell-pulse 2s infinite;
}

.sidebar__environment div {
  display: grid;
  gap: 0.2rem;
  white-space: nowrap;
}

.sidebar__environment strong {
  font-size: 0.72rem;
}

.sidebar__environment span:last-child {
  color: var(--gg-text-muted);
  font-size: 0.62rem;
}

.sidebar__nav {
  flex: 1;
  overflow-y: auto;
  padding: 0 0.75rem 1rem;
}

.sidebar__section-label {
  margin: 0.8rem 0.65rem;
  color: var(--gg-text-muted);
  font-size: 0.58rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  white-space: nowrap;
}

.sidebar__link {
  position: relative;
  display: flex;
  min-height: 55px;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.25rem;
  padding: 0.65rem;
  border: 1px solid transparent;
  border-radius: 12px;
  color: var(--gg-text-secondary);
  transition:
    color var(--gg-transition-fast),
    border-color var(--gg-transition),
    background var(--gg-transition);
}

.sidebar__link:hover {
  color: var(--gg-text-primary);
  background: rgba(148, 163, 184, 0.05);
}

.sidebar__link--active {
  border-color: rgba(34, 211, 238, 0.18);
  color: var(--gg-text-primary);
  background:
    linear-gradient(
      90deg,
      rgba(34, 211, 238, 0.11),
      rgba(59, 130, 246, 0.04)
    );
}

.sidebar__link--active::before {
  position: absolute;
  left: -1px;
  width: 3px;
  height: 28px;
  border-radius: 0 4px 4px 0;
  background: var(--gg-cyan);
  box-shadow: 0 0 16px var(--gg-cyan);
  content: "";
}

.sidebar__link-icon {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  border-radius: 10px;
  background: rgba(148, 163, 184, 0.06);
}

.sidebar__link--active .sidebar__link-icon {
  color: var(--gg-cyan);
  background: rgba(34, 211, 238, 0.1);
}

.sidebar__link-copy {
  display: grid;
  flex: 1;
  gap: 0.2rem;
}

.sidebar__link-copy strong {
  overflow: hidden;
  font-size: 0.78rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar__link-copy small {
  overflow: hidden;
  color: var(--gg-text-muted);
  font-size: 0.61rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar__link-arrow {
  color: var(--gg-text-muted);
}

.sidebar__footer {
  position: relative;
  padding: 0.75rem;
  border-top: 1px solid var(--gg-border);
}

.sidebar__logout {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 0.85rem;
  padding: 0.7rem;
  border: 0;
  border-radius: 11px;
  color: var(--gg-text-secondary);
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.sidebar__logout:hover {
  color: #fecaca;
  background: rgba(239, 68, 68, 0.07);
}

.sidebar__collapse {
  position: absolute;
  right: -14px;
  bottom: 30px;
  display: grid;
  width: 28px;
  height: 28px;
  border: 1px solid var(--gg-border);
  border-radius: 50%;
  place-items: center;
  color: var(--gg-text-secondary);
  background: var(--gg-panel-solid);
  cursor: pointer;
}

.sidebar__mobile-close,
.topbar__mobile-menu {
  display: none;
}

.app-shell--collapsed
.sidebar__brand-copy,
.app-shell--collapsed
.sidebar__link-copy,
.app-shell--collapsed
.sidebar__link-arrow,
.app-shell--collapsed
.sidebar__section-label,
.app-shell--collapsed
.sidebar__environment div {
  opacity: 0;
  pointer-events: none;
  transform: translateX(-8px);
}

.workspace {
  min-width: 0;
  grid-column: 2;
}

.topbar {
  position: sticky;
  z-index: 35;
  top: 0;
  display: flex;
  min-height: var(--gg-topbar-height);
  align-items: center;
  justify-content: space-between;
  padding: 0 1.6rem;
  border-bottom: 1px solid var(--gg-border);
  background: rgba(5, 11, 20, 0.82);
  backdrop-filter: blur(20px);
}

.topbar__left {
  display: flex;
  align-items: center;
  gap: 0.8rem;
}

.topbar__left p {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin: 0 0 0.2rem;
  color: var(--gg-text-muted);
  font-size: 0.64rem;
}

.topbar__left h1 {
  margin: 0;
  font-size: 1rem;
}

.topbar__actions {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.topbar__search {
  display: flex;
  min-width: 240px;
  align-items: center;
  gap: 0.6rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--gg-border);
  border-radius: 11px;
  color: var(--gg-text-muted);
  background: rgba(148, 163, 184, 0.04);
  cursor: pointer;
}

.topbar__search span {
  flex: 1;
  text-align: left;
  font-size: 0.72rem;
}

.topbar__search kbd {
  padding: 0.2rem 0.38rem;
  border: 1px solid var(--gg-border);
  border-radius: 5px;
  font-size: 0.6rem;
}

.topbar__icon-button {
  position: relative;
  display: grid;
  width: 39px;
  height: 39px;
  border: 1px solid var(--gg-border);
  border-radius: 11px;
  place-items: center;
  color: var(--gg-text-secondary);
  background: rgba(148, 163, 184, 0.04);
  cursor: pointer;
}

.topbar__notification {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--gg-amber);
  box-shadow: 0 0 10px var(--gg-amber);
}

.topbar__operator {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin-left: 0.35rem;
  padding-left: 0.9rem;
  border-left: 1px solid var(--gg-border);
}

.topbar__operator > span {
  display: grid;
  width: 38px;
  height: 38px;
  border-radius: 11px;
  place-items: center;
  color: var(--gg-cyan);
  background: rgba(34, 211, 238, 0.08);
}

.topbar__operator div {
  display: grid;
  gap: 0.18rem;
}

.topbar__operator strong {
  font-size: 0.73rem;
}

.topbar__operator small {
  color: var(--gg-text-muted);
  font-size: 0.6rem;
}

.workspace__content {
  position: relative;
  min-height:
    calc(100vh - var(--gg-topbar-height));
  overflow: hidden;
  isolation: isolate;
}

.workspace__background {
  position: absolute;
  z-index: -2;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

.workspace__grid {
  position: absolute;
  inset: 0;
  opacity: 0.13;
  background-image:
    linear-gradient(
      rgba(34, 211, 238, 0.12) 1px,
      transparent 1px
    ),
    linear-gradient(
      90deg,
      rgba(34, 211, 238, 0.12) 1px,
      transparent 1px
    );
  background-size: 54px 54px;
  mask-image:
    linear-gradient(
      to bottom,
      black,
      transparent 90%
    );
}

.workspace__orb {
  position: absolute;
  width: 32rem;
  height: 32rem;
  border-radius: 50%;
  opacity: 0.08;
  filter: blur(90px);
}

.workspace__orb--one {
  top: -18rem;
  right: -8rem;
  background: var(--gg-cyan);
}

.workspace__orb--two {
  bottom: -20rem;
  left: 20%;
  background: var(--gg-violet);
}

.workspace__watermark {
  position: absolute;
  top: 9%;
  right: -5%;
  width: min(48vw, 640px);
  opacity: 0.035;
  filter: grayscale(1);
  mask-image:
    linear-gradient(
      to left,
      black,
      transparent 92%
    );
  animation: shell-watermark 8s ease-in-out infinite;
}

.shell-backdrop {
  display: none;
}

@keyframes shell-pulse {
  50% {
    opacity: 0.4;
    transform: scale(0.8);
  }
}

@keyframes shell-watermark {
  50% {
    transform: scale(1.025);
    opacity: 0.05;
  }
}

@media (max-width: 1100px) {
  .topbar__search {
    min-width: 40px;
    width: 40px;
  }

  .topbar__search span,
  .topbar__search kbd {
    display: none;
  }
}

@media (max-width: 820px) {
  .app-shell {
    display: block;
  }

  .sidebar {
    width: min(310px, 88vw);
    transform: translateX(-105%);
  }

  .sidebar--mobile-open {
    transform: translateX(0);
  }

  .sidebar__mobile-close,
  .topbar__mobile-menu {
    display: grid;
  }

  .sidebar__mobile-close {
    margin-left: auto;
    padding: 0.4rem;
    border: 0;
    color: var(--gg-text-secondary);
    background: transparent;
  }

  .topbar__mobile-menu {
    width: 40px;
    height: 40px;
    border: 1px solid var(--gg-border);
    border-radius: 10px;
    place-items: center;
    color: var(--gg-text-secondary);
    background: transparent;
  }

  .sidebar__collapse {
    display: none;
  }

  .workspace {
    grid-column: auto;
  }

  .shell-backdrop {
    position: fixed;
    z-index: 45;
    inset: 0;
    border: 0;
    background: rgba(0, 0, 0, 0.64);
    backdrop-filter: blur(4px);
  }

  .shell-backdrop--visible {
    display: block;
  }
}

@media (max-width: 620px) {
  .topbar {
    padding: 0 0.8rem;
  }

  .topbar__operator div,
  .topbar__search {
    display: none;
  }

  .topbar__operator {
    padding-left: 0.5rem;
  }
}
""",
    "frontend/src/styles/pages.css": """
.page {
  width: min(1500px, 100%);
  margin: 0 auto;
  padding: clamp(1.25rem, 3vw, 2.5rem);
}

.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 2rem;
  margin-bottom: 2rem;
}

.page-heading > div:first-child {
  max-width: 820px;
}

.page-heading__eyebrow {
  margin-bottom: 0.65rem;
  color: var(--gg-cyan-soft);
  font-size: 0.67rem;
  font-weight: 750;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.page-heading h2 {
  margin-bottom: 0.8rem;
  font-size: clamp(2rem, 4.5vw, 4.2rem);
  line-height: 1;
  letter-spacing: -0.055em;
}

.page-heading h2 span {
  color: transparent;
  background:
    linear-gradient(
      90deg,
      var(--gg-cyan),
      var(--gg-violet)
    );
  background-clip: text;
}

.page-heading > div > p:last-child {
  max-width: 760px;
  margin: 0;
  color: var(--gg-text-secondary);
  line-height: 1.7;
}

.page-heading__status {
  display: inline-flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.7rem 0.9rem;
  border: 1px solid rgba(34, 197, 94, 0.18);
  border-radius: 999px;
  color: #bbf7d0;
  background: rgba(34, 197, 94, 0.06);
  font-size: 0.72rem;
  white-space: nowrap;
}

.page-heading__status span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--gg-green);
  box-shadow: 0 0 12px var(--gg-green);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.85rem;
}

.metric-card {
  display: flex;
  min-height: 150px;
  align-items: flex-start;
  gap: 1rem;
  padding: 1.15rem;
  border: 1px solid var(--gg-border);
  border-radius: var(--gg-radius-lg);
  background:
    linear-gradient(
      145deg,
      rgba(18, 30, 49, 0.84),
      rgba(8, 15, 27, 0.74)
    );
  box-shadow: var(--gg-shadow-sm);
  backdrop-filter: blur(16px);
}

.metric-card__icon {
  display: grid;
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  border-radius: 13px;
  place-items: center;
}

.metric-card--cyan .metric-card__icon {
  color: var(--gg-cyan);
  background: rgba(34, 211, 238, 0.1);
}

.metric-card--green .metric-card__icon {
  color: var(--gg-green);
  background: rgba(34, 197, 94, 0.1);
}

.metric-card--amber .metric-card__icon {
  color: var(--gg-amber);
  background: rgba(245, 158, 11, 0.1);
}

.metric-card--red .metric-card__icon {
  color: var(--gg-red);
  background: rgba(239, 68, 68, 0.1);
}

.metric-card > div:last-child {
  display: grid;
}

.metric-card span {
  color: var(--gg-text-secondary);
  font-size: 0.72rem;
}

.metric-card strong {
  margin: 0.35rem 0;
  font-size: 2.25rem;
  letter-spacing: -0.05em;
}

.metric-card small {
  color: var(--gg-text-muted);
  font-size: 0.65rem;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1.05fr 0.95fr;
  gap: 0.9rem;
  margin-top: 0.9rem;
}

.dashboard-card {
  min-height: 390px;
  padding: 1.3rem;
  border: 1px solid var(--gg-border);
  border-radius: var(--gg-radius-lg);
  background: var(--gg-panel);
  box-shadow: var(--gg-shadow-sm);
  backdrop-filter: blur(18px);
}

.dashboard-card--wide {
  min-height: auto;
  grid-column: 1 / -1;
}

.dashboard-card__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dashboard-card__heading p {
  margin-bottom: 0.3rem;
  color: var(--gg-text-muted);
  font-size: 0.65rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.dashboard-card__heading h3 {
  margin: 0;
  font-size: 1.05rem;
}

.dashboard-card__heading > svg {
  color: var(--gg-cyan);
}

.status-chip {
  display: inline-flex;
  width: fit-content;
  padding: 0.38rem 0.55rem;
  border-radius: 999px;
  font-size: 0.6rem;
  font-weight: 750;
}

.status-chip--success {
  color: #bbf7d0;
  background: rgba(34, 197, 94, 0.1);
}

.status-chip--danger {
  color: #fecaca;
  background: rgba(239, 68, 68, 0.1);
}

.posture-orbit {
  position: relative;
  display: grid;
  height: 310px;
  place-items: center;
}

.posture-orbit__ring {
  position: absolute;
  border: 1px solid rgba(34, 211, 238, 0.16);
  border-radius: 50%;
}

.posture-orbit__ring--outer {
  width: 270px;
  height: 270px;
  animation: posture-spin 24s linear infinite;
}

.posture-orbit__ring--inner {
  width: 180px;
  height: 180px;
  border-style: dashed;
  animation: posture-spin 18s linear infinite reverse;
}

.posture-orbit__core {
  display: grid;
  width: 118px;
  height: 118px;
  place-items: center;
  align-content: center;
  gap: 0.2rem;
  border: 1px solid var(--gg-border-strong);
  border-radius: 50%;
  color: var(--gg-cyan);
  background: rgba(34, 211, 238, 0.06);
  box-shadow: var(--gg-glow-cyan);
}

.posture-orbit__core strong {
  color: var(--gg-text-primary);
  font-size: 0.75rem;
}

.posture-orbit__core span {
  color: var(--gg-text-muted);
  font-size: 0.58rem;
}

.posture-node {
  position: absolute;
  padding: 0.38rem 0.52rem;
  border: 1px solid var(--gg-border);
  border-radius: 999px;
  color: var(--gg-text-secondary);
  background: var(--gg-panel-solid);
  font-size: 0.6rem;
}

.posture-node--one {
  top: 35px;
}

.posture-node--two {
  right: 8%;
}

.posture-node--three {
  bottom: 32px;
}

.posture-node--four {
  left: 8%;
}

.pipeline {
  display: grid;
  gap: 0.6rem;
  margin-top: 1.4rem;
}

.pipeline__step {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 1px solid var(--gg-border);
  border-radius: 11px;
  background: rgba(148, 163, 184, 0.035);
}

.pipeline__step > span {
  display: grid;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  place-items: center;
  color: var(--gg-cyan);
  background: rgba(34, 211, 238, 0.08);
  font-family: var(--gg-font-mono);
  font-size: 0.66rem;
}

.pipeline__step div {
  display: grid;
  gap: 0.18rem;
}

.pipeline__step strong {
  font-size: 0.72rem;
}

.pipeline__step small {
  color: var(--gg-text-muted);
  font-size: 0.62rem;
}

.pipeline__step > svg {
  color: var(--gg-green);
}

.dashboard-card__updated {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  color: var(--gg-text-muted);
  font-size: 0.63rem;
}

.agent-table {
  margin-top: 1rem;
  overflow-x: auto;
}

.agent-table__header,
.agent-table__row {
  display: grid;
  min-width: 650px;
  grid-template-columns:
    minmax(200px, 1.4fr)
    0.7fr
    0.7fr
    1fr;
  align-items: center;
  gap: 1rem;
  padding: 0.8rem;
}

.agent-table__header {
  color: var(--gg-text-muted);
  font-size: 0.62rem;
  text-transform: uppercase;
}

.agent-table__row {
  border-top: 1px solid var(--gg-border);
  color: var(--gg-text-secondary);
  font-size: 0.72rem;
}

.agent-name {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  color: var(--gg-text-primary);
  font-weight: 650;
}

.agent-name > span {
  display: grid;
  width: 32px;
  height: 32px;
  border-radius: 9px;
  place-items: center;
  color: var(--gg-cyan);
  background: rgba(34, 211, 238, 0.07);
}

.risk-score {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.risk-score::before {
  width: 80px;
  height: 4px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  content: "";
}

.risk-score > span {
  position: absolute;
  left: 0;
  max-width: 80px;
  height: 4px;
  border-radius: 999px;
  background:
    linear-gradient(
      90deg,
      var(--gg-green),
      var(--gg-amber),
      var(--gg-red)
    );
}

.section-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.85rem;
}

.section-card {
  position: relative;
  min-height: 280px;
  overflow: hidden;
  padding: 1.25rem;
  border: 1px solid var(--gg-border);
  border-radius: var(--gg-radius-lg);
  background:
    linear-gradient(
      145deg,
      rgba(18, 30, 49, 0.82),
      rgba(7, 14, 25, 0.76)
    );
  box-shadow: var(--gg-shadow-sm);
}

.section-card__number {
  position: absolute;
  top: 1rem;
  right: 1rem;
  color: rgba(148, 163, 184, 0.18);
  font-family: var(--gg-font-mono);
  font-size: 2rem;
  font-weight: 800;
}

.section-card > svg {
  margin-bottom: 2.6rem;
  color: var(--gg-cyan);
}

.section-card h3 {
  margin-bottom: 0.7rem;
  font-size: 1rem;
}

.section-card p {
  color: var(--gg-text-muted);
  font-size: 0.72rem;
  line-height: 1.65;
}

.section-card button {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  margin-top: 1rem;
  padding: 0;
  border: 0;
  color: var(--gg-cyan-soft);
  background: transparent;
  font-size: 0.68rem;
  cursor: pointer;
}

@keyframes posture-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1180px) {
  .metric-grid,
  .section-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 900px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-card--wide {
    grid-column: auto;
  }
}

@media (max-width: 620px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .metric-grid,
  .section-grid {
    grid-template-columns: 1fr;
  }

  .metric-card {
    min-height: 120px;
  }
}
""",
}


for relative_path, content in files.items():
    destination = root / relative_path
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    destination.write_text(
        content.strip() + "\n",
        encoding="utf-8",
    )
    print(
        "Created:",
        destination.relative_to(root),
    )


print()
print("GreyGuard command shell created.")