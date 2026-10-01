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
import { SectionPage } from "../pages/SectionPage"
import ToolRequestsPage from "../pages/ToolRequestsPage"
import ApprovalsPage from "../pages/ApprovalsPage"
import PoliciesPage from "../pages/PoliciesPage"
import RiskCenterPage from "../pages/RiskCenterPage"

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
              description="Inspect GreyGuard's restricted filesystem and controlled tool boundary."
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