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
