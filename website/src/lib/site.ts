export type SiteMode = "preview" | "publish"

export const siteMode: SiteMode = process.env.GREYGUARD_SITE_MODE === "publish" ? "publish" : "preview"

/** The separate administrator application. The site only links to its sign-in page. */
export const consoleUrl = process.env.GREYGUARD_CONSOLE_URL ?? "/sign-in/"

/** The demo-request route (decision W5). Until it is chosen, the call to action explains that. */
export const demoContact = process.env.GREYGUARD_DEMO_CONTACT ?? null

export const primaryNavigation = [
  { label: "Platform", href: "/platform/" },
  { label: "Agent environments", href: "/environments/" },
  { label: "Use cases", href: "/use-cases/" },
  { label: "Integrations", href: "/integrations/" },
  { label: "Proof & Trust", href: "/trust/" },
  { label: "Resources", href: "/resources/" },
  { label: "Company", href: "/company/" },
] as const

export const footerLinks = [
  { label: "Privacy", href: "/legal/privacy/" },
  { label: "Terms", href: "/legal/terms/" },
  { label: "Cookies", href: "/legal/cookies/" },
  { label: "Accessibility", href: "/accessibility/" },
  { label: "Responsible disclosure", href: "/security/" },
  { label: "Subprocessors", href: "/legal/subprocessors/" },
  { label: "Status", href: "/status/" },
] as const
