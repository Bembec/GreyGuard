import {
  Navigate,
  Route,
  Routes,
} from "react-router-dom"

import { useAuth } from "../context/AuthContext"
import { AppShell } from "../layouts/AppShell"
import AgentsPage from "../pages/AgentsPage"
import AgentDetailPage from "../pages/AgentDetailPage"
import { DashboardPage } from "../pages/DashboardPage"
import { LoginPage } from "../pages/LoginPage"
import LiveOperationsPage from "../pages/LiveOperationsPage"
import ToolRequestsPage from "../pages/ToolRequestsPage"
import RequestDetailPage from "../pages/RequestDetailPage"
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
import ComplianceReportsPage from "../pages/ComplianceReportsPage"
import AbuseProtectionPage from "../pages/AbuseProtectionPage"
import AgentAdaptersPage from "../pages/AgentAdaptersPage"
import ObservabilityPage from "../pages/ObservabilityPage"
import AccountSecurityPage from "../pages/AccountSecurityPage"
import EnterpriseIdentityPage from "../pages/EnterpriseIdentityPage"
import SecurityExportsPage from "../pages/SecurityExportsPage"
import AuditIntegrityPage from "../pages/AuditIntegrityPage"
import CommunicationIntegrationsPage from "../pages/CommunicationIntegrationsPage"
import IncidentIntegrationsPage from "../pages/IncidentIntegrationsPage"
import ExecutionIsolationPage from "../pages/ExecutionIsolationPage"

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
        <Route path="/agents/:agentName" element={<AgentDetailPage />} />


        <Route
          path="/requests"
          element={<ToolRequestsPage />}
        />
        <Route path="/requests/:requestId" element={<RequestDetailPage />} />

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

        <Route path="/compliance" element={<ComplianceReportsPage />} />

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

        <Route path="/abuse-protection" element={<AbuseProtectionPage />} />

        <Route path="/adapters" element={<AgentAdaptersPage />} />

        <Route path="/observability" element={<ObservabilityPage />} />

        <Route path="/security-exports" element={<SecurityExportsPage />} />

        <Route path="/audit-integrity" element={<AuditIntegrityPage />} />

        <Route path="/communication-integrations" element={<CommunicationIntegrationsPage />} />

        <Route path="/incident-integrations" element={<IncidentIntegrationsPage />} />

        <Route path="/execution-isolation" element={<ExecutionIsolationPage />} />

        <Route path="/account-security" element={<AccountSecurityPage />} />

        <Route path="/enterprise-identity" element={<EnterpriseIdentityPage />} />

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
