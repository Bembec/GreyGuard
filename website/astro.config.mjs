import { defineConfig } from "astro/config"

// Two build modes. "preview" (the default) is for review: unapproved claims are shown, clearly
// marked, and every page asks search engines not to index it. "publish" is the only mode that may
// be deployed publicly: it needs the real site URL, and it fails if any page uses a claim the
// project owner has not approved (see src/lib/claims.ts).
const mode = process.env.GREYGUARD_SITE_MODE ?? "preview"
if (!["preview", "publish"].includes(mode)) throw new Error(`Unknown GREYGUARD_SITE_MODE: ${mode}`)
const site = process.env.GREYGUARD_SITE_URL
if (mode === "publish" && !site) throw new Error("A publish build needs GREYGUARD_SITE_URL (decision W4: the domain).")

export default defineConfig({
  site: site ?? "https://preview.greyguard.invalid",
  output: "static",
  trailingSlash: "always",
  build: {
    format: "directory",
    // No inline styles or scripts anywhere, so the strict Content-Security-Policy holds.
    inlineStylesheets: "never",
  },
  devToolbar: { enabled: false },
})
