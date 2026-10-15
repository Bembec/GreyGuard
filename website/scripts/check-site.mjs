// Post-build checks for the public site. Run after `astro build`; exits non-zero on any problem.
// No dependencies: it reads the built files in dist/ directly.
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs"
import { join, relative } from "node:path"

const dist = new URL("../dist/", import.meta.url).pathname
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
  for (const label of REQUIRED_FOOTER) if (!html.includes(`>${label}</a>`)) fail(file, `is missing the "${label}" footer link`)
  for (const [, alt] of html.matchAll(/<img\b[^>]*?alt="([^"]*)"/g)) if (alt === undefined) fail(file, "has an image without alt text")
  if (/<img\b(?![^>]*\balt=)/.test(html)) fail(file, "has an image without alt text")
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
