// Post-build checks for the public site. Run after `astro build`; exits non-zero on any problem.
// No dependencies: it reads the built files in dist/ directly.
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs"
import { join, relative } from "node:path"

const dist = new URL("../dist/", import.meta.url).pathname
const registry = JSON.parse(readFileSync(new URL("../../config/decisions.json", import.meta.url), "utf8"))
const decided = new Set(registry.decisions.filter((item) => item.status === "decided").map((item) => item.id))
// Legal pages and the decision that approves each.
const LEGAL_PAGES = { "legal/privacy/index.html": "LEG-01", "legal/terms/index.html": "LEG-02", "legal/cookies/index.html": "LEG-03", "legal/subprocessors/index.html": "LEG-05" }
const problems = []
const fail = (file, message) => problems.push(`${file}: ${message}`)

function htmlFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    return statSync(path).isDirectory() ? htmlFiles(path) : name.endsWith(".html") ? [path] : []
  })
}

const REQUIRED_NAV = ["Platform", "Agent environments", "Use cases", "Integrations", "Proof &amp; Trust", "Resources", "Company", "Sign in"]
const REQUIRED_FOOTER = ["Privacy", "Terms", "Cookies", "Accessibility", "Responsible disclosure", "Subprocessors", "Status"]
const REQUIRED_HEADERS = ["Content-Security-Policy:", "Strict-Transport-Security:", "X-Content-Type-Options: nosniff", "Referrer-Policy:", "Permissions-Policy:", "frame-ancestors 'none'", "script-src 'none'"]

if (!existsSync(dist)) {
  console.error("dist/ is missing: run `npm run build` first.")
  process.exit(1)
}

const files = htmlFiles(dist)
for (const path of files) {
  const file = relative(dist, path)
  const html = readFileSync(path, "utf8")
  // A strict CSP: no scripts at all, and no inline styles.
  if (/<script\b/i.test(html)) fail(file, "contains a <script> tag; the site ships no scripts")
  if (/<style\b/i.test(html)) fail(file, "contains an inline <style> block")
  if (/\sstyle=/i.test(html)) fail(file, "contains an inline style attribute")
  if (!/<html lang="en"/.test(html)) fail(file, "is missing lang=\"en\"")
  if (!/<title>[^<]+<\/title>/.test(html)) fail(file, "has no <title>")
  if (!/<meta name="description" content="[^"]+"/.test(html)) fail(file, "has no meta description")
  if (!/<link rel="canonical" href="https?:\/\/[^"]+"/.test(html)) fail(file, "has no canonical URL")
  const h1s = html.match(/<h1\b/g) ?? []
  if (h1s.length !== 1) fail(file, `has ${h1s.length} <h1> elements; each page needs exactly one`)
  if (!html.includes('href="#main"')) fail(file, "has no skip link")
  for (const label of REQUIRED_NAV) if (!html.includes(`>${label}</a>`)) fail(file, `is missing the "${label}" navigation item`)
  // A footer link may carry a "(draft)" marker in preview builds while its document is unapproved.
  for (const label of REQUIRED_FOOTER) if (!html.includes(`>${label}</a>`) && !html.includes(`>${label}<span class="draft-tag">`)) fail(file, `is missing the "${label}" footer link`)
  for (const [, alt] of html.matchAll(/<img\b[^>]*?alt="([^"]*)"/g)) if (alt === undefined) fail(file, "has an image without alt text")
  if (/<img\b(?![^>]*\balt=)/.test(html)) fail(file, "has an image without alt text")
  // No dead actions: every link goes somewhere and no button sits without a purpose.
  if (/href=""|href="#"(?=[\s>])/.test(html)) fail(file, "has a link that goes nowhere")
  if (/<button(?![^>]*\btype=)/.test(html)) fail(file, "has a button with no declared behaviour")
  // No placeholder copy on customer-facing pages.
  const text = html.replace(/<[^>]+>/g, " ")
  if (/lorem ipsum|\bTODO\b|\bFIXME\b|\bTBD\b/i.test(text)) fail(file, "contains placeholder text")
  // A publish build carries no preview-only markers.
  if (process.env.GREYGUARD_SITE_MODE === "publish" && /class="(preview-banner|preview-note|draft-tag)"/.test(html)) fail(file, "shows a preview-only marker in a publish build")
  // A legal document that is not approved is shown only as a labelled draft, and never indexed.
  const legalDecision = LEGAL_PAGES[file.replaceAll("\\", "/")]
  if (legalDecision && !decided.has(legalDecision)) {
    if (!html.includes("Draft: awaiting qualified legal review")) fail(file, `is not approved (${legalDecision}) but is not labelled as a draft`)
    if (!html.includes('content="noindex, nofollow"')) fail(file, `is not approved (${legalDecision}) but could be indexed`)
  }
  // Every internal link must resolve to a built file.
  for (const [, href] of html.matchAll(/href="(\/[^"#?]*)"/g)) {
    const target = join(dist, href)
    const ok = existsSync(target) && (statSync(target).isFile() || existsSync(join(target, "index.html")))
    if (!ok) fail(file, `links to ${href}, which does not exist`)
  }
  // Pages marked noindex stay noindex; nothing is indexable until a publish build.
  if (process.env.GREYGUARD_SITE_MODE !== "publish" && !html.includes('content="noindex, nofollow"')) fail(file, "is indexable in a preview build")
}

const headers = existsSync(join(dist, "_headers")) ? readFileSync(join(dist, "_headers"), "utf8") : ""
for (const header of REQUIRED_HEADERS) if (!headers.includes(header)) fail("_headers", `is missing ${header}`)

if (problems.length) {
  console.error(`Site check: ${problems.length} problem(s)`)
  for (const item of problems) console.error(`  - ${item}`)
  process.exit(1)
}
console.log(`Site check OK: ${files.length} pages, security headers present, no scripts or inline styles.`)
