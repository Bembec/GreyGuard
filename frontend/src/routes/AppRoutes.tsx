import {
  Navigate,
  Route,
  Routes,
} from "react-router-dom"

import { useAuth } from "../context/AuthContext"
import { AppShell } from "../layouts/AppShell"
import AgentsPage from "../pages/AgentsPage"
import { DashboardPage } from "../pages/DashboardPage"
import { LoginPage } from "../pages/LoginPage"
import LiveOperationsPage from "../pages/LiveOperationsPage"
import ToolRequestsPage from "../pages/ToolRequestsPage"
import ApprovalsPage from "../pages/ApprovalsPage"
import PoliciesPage from "../pages/PoliciesPage"
import RiskCenterPage from "../pages/RiskCenterPage"
import AuditTrailPage from "../pages/AuditTrailPage"
import IncidentCenterPage from "../pages/IncidentCenterPage"
import AuthenticationPage from "../pages/AuthenticationPage"
import SandboxPage from "../pages/SandboxPage"

import SettingsPage from "../pages/SettingsPage"
import TeamAccessPage from "../pages/TeamAccessPage"
import SecretsPage from "../pages/SecretsPage"
import NotificationsPage from "../pages/NotificationsPage"
import ServiceAccountsPage from "../pages/ServiceAccountsPage"

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
          path="/live"
          element={<LiveOperationsPage />}
        />

        <Route
          path="/agents"
          element={<AgentsPage />}
        />


        <Route
          path="/requests"
          element={<ToolRequestsPage />}
        />

        <Route
          path="/approvals"
          element={<ApprovalsPage />}
        />

        <Route
          path="/policies"
          element={<PoliciesPage />}
        />
        <Route
          path="/risk"
          element={<RiskCenterPage />}
        />

        <Route
          path="/incidents"
          element={<IncidentCenterPage />}
        />

        <Route path="/notifications" element={<NotificationsPage />} />

        <Route
          path="/audit"
          element={<AuditTrailPage />}
        />

        <Route
          path="/authentication"
          element={<AuthenticationPage />}
        />

        <Route
          path="/sandbox"
          element={<SandboxPage />}
        />

        <Route
          path="/team"
          element={<TeamAccessPage />}
        />

        <Route path="/secrets" element={<SecretsPage />} />

        <Route path="/service-accounts" element={<ServiceAccountsPage />} />

        <Route
          path="/settings"
          element={<SettingsPage />}
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
