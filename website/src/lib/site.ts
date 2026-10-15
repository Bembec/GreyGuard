export type SiteMode = "preview" | "publish"

export const siteMode: SiteMode = process.env.GREYGUARD_SITE_MODE === "publish" ? "publish" : "preview"

/** The separate administrator application. The site only links to its sign-in page. */
export const consoleUrl = process.env.GREYGUARD_CONSOLE_URL ?? "/sign-in/"

/** The demo-request route (decision W5). Until it is chosen, the call to action explains that. */
export const demoContact = process.env.GREYGUARD_DEMO_CONTACT ?? null

export interface MenuLink { label: string; href: string; description: string; icon: string; badge?: string }
export interface MenuColumn { heading: string; links: MenuLink[] }
export interface NavItem { label: string; href: string; columns?: MenuColumn[]; feature?: { eyebrow: string; title: string; text: string; href: string; cta: string } }

/** The addendum's required navigation. Items with columns open a mega-menu; every item is also a plain link, so it works without scripts. */
export const primaryNavigation: NavItem[] = [
  {
    label: "Platform", href: "/platform/",
    columns: [{
      heading: "Product groups",
      links: [
        { label: "Gate", href: "/platform/#gate", description: "Identity, scopes, policy and human approval", icon: "gate" },
        { label: "Watch", href: "/platform/#watch", description: "Risk, live decisions and incidents", icon: "watch" },
        { label: "Respond", href: "/platform/#respond", description: "Recoverable containment and removal", icon: "respond" },
        { label: "Evidence", href: "/platform/#evidence", description: "Tamper-evident records and reports", icon: "evidence" },
      ],
    }],
    feature: { eyebrow: "How it works", title: "How a request is decided", text: "Follow one agent action from identity to evidence.", href: "/platform/#request-path", cta: "See the request path" },
  },
  {
    label: "Agent environments", href: "/environments/",
    columns: [{
      heading: "Connection methods",
      links: [
        { label: "SDKs", href: "/environments/#sdks", description: "Python and JavaScript clients", icon: "code" },
        { label: "REST API", href: "/environments/#api", description: "Versioned under /api/v1", icon: "server" },
        { label: "Framework adapters", href: "/environments/#adapters", description: "MCP, LangChain, LangGraph, CrewAI, AutoGen", icon: "plug" },
        { label: "Gateways", href: "/environments/#gateways", description: "Signed policy enforced near the agent", icon: "lock" },
        { label: "Monitor-only", href: "/environments/#coverage", description: "Observe without enforcing", icon: "watch", badge: "Planned" },
      ],
    }],
  },
  { label: "Use cases", href: "/use-cases/" },
  { label: "Integrations", href: "/integrations/" },
  {
    label: "Proof & Trust", href: "/trust/",
    columns: [{
      heading: "Trust",
      links: [
        { label: "Trust center", href: "/trust/", description: "Architecture, data handling and assurance status", icon: "gate" },
        { label: "Claim register", href: "/trust/#claims", description: "Every claim, its scope and its evidence", icon: "check" },
        { label: "Responsible disclosure", href: "/security/", description: "Report a vulnerability privately", icon: "alert" },
        { label: "Service status", href: "/status/", description: "Live component health", icon: "pulse" },
      ],
    }],
  },
  { label: "Resources", href: "/resources/" },
  { label: "Company", href: "/company/" },
]

export const footerLinks = [
  { label: "Privacy", href: "/legal/privacy/" },
  { label: "Terms", href: "/legal/terms/" },
  { label: "Cookies", href: "/legal/cookies/" },
  { label: "Accessibility", href: "/accessibility/" },
  { label: "Responsible disclosure", href: "/security/" },
  { label: "Subprocessors", href: "/legal/subprocessors/" },
  { label: "Status", href: "/status/" },
] as const
