/** Guidance for each readiness-checklist item. The backend decides whether a step is done; this
 * only says why it matters, who does it and where in the product it is done. */
export type OnboardingStep = { why: string; who: string; href?: string; action: string }

export const onboardingSteps: Record<string, OnboardingStep> = {
  owner_active: { why: "Someone in your organization is accountable for GreyGuard.", who: "Your GreyGuard operator invites; your owner accepts", action: "Accept the owner invitation" },
  separation_of_duties: { why: "Consequential actions can then need a second person's approval.", who: "Owner", href: "/team", action: "Invite a second administrator" },
  auditor_assigned: { why: "Read-only oversight that cannot change what it reviews.", who: "Owner", href: "/team", action: "Invite an auditor" },
  mfa_everyone: { why: "A stolen password alone cannot approve or change anything.", who: "Every member", href: "/account-security", action: "Turn on MFA" },
  plan_assigned: { why: "Your plan sets which integrations and how many agents you can add.", who: "Your GreyGuard operator", action: "Ask your GreyGuard contact" },
  policy_baseline: { why: "Agents are enforced against a reviewed, published policy.", who: "Administrator, with a second approver", href: "/policies", action: "Review and publish the policy" },
  first_agent: { why: "Nothing is governed until an agent sends its actions through GreyGuard.", who: "Administrator or platform engineer", href: "/agents", action: "Register your first agent" },
  integration: { why: "Evidence and alerts reach the tools your team already watches.", who: "Administrator", href: "/security-exports", action: "Connect your SIEM or notifications" },
  export_tested: { why: "You can take your evidence out at any time - prove it once.", who: "Owner", href: "/settings", action: "Export your organization's data" },
}

export function stepFor(key: string): OnboardingStep {
  return onboardingSteps[key] ?? { why: "", who: "", action: "Complete this step" }
}

export function progressLabel(done: number, total: number): string {
  if (total === 0) return "No steps"
  return done === total ? "Ready for production" : `${done} of ${total} steps complete`
}
