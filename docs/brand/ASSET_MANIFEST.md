# Brand asset manifest

<!-- Generated from config/brand-assets.json by `python scripts/brand_assets.py sync`. Do not edit by hand. -->

Put the final file at the slot's path (same name), update width, height and status "final" here, then run python scripts/brand_assets.py sync and, for the website, npm run brand in website/. No page or component changes are needed.

Status: **final** = approved master in place; **provisional** = the current approved artwork, in use until the
designer's masters arrive (decisions BRAND-01 and BRAND-02); **missing** = no file yet, so the fallback renders.
Paths are relative to `frontend/public/`. The website derives its web-sized copies with `npm run brand`.

| Slot | Use | Path | Size now | Status | Falls back to | Final requirement |
|---|---|---|---|---|---|---|
| `lockup-dark` | Primary lockup on dark backgrounds: console and website headers, footers, splash | `brand/logos/primary/greyguard-primary-stacked.png` | 1839×855 | provisional | — | Transparent lockup for dark backgrounds; SVG master plus PNG/WebP at 1x, 2x and 4x |
| `lockup-horizontal-dark` | Horizontal lockup (mark beside wordmark) for compact headers | `brand/logos/horizontal/greyguard-horizontal-dark.png` | 920×610 | provisional | — | True horizontal lockup, transparent, readable at 160 px wide |
| `lockup-light` | Lockup for light backgrounds: documents, print, light pages | `brand/logos/light/greyguard-lockup-light.png` | — | missing | lockup-dark | Full-colour lockup designed for light backgrounds |
| `symbol` | Symbol-only mark: collapsed navigation, avatars, compact contexts | `brand/logos/symbol/greyguard-symbol-dark.png` | 700×700 | provisional | — | Flat symbol readable at 16 px, transparent |
| `symbol-mono` | Single-colour mark for monochrome print and embossing | `brand/logos/mono/greyguard-symbol-mono.png` | — | missing | symbol | White and black single-colour versions of the symbol |
| `favicon-16` | Browser tab icon, 16 px | `brand/icons/favicon/favicon-16.png` | 16×16 | provisional | — | Simplified pixel-hinted mark at 16 px |
| `favicon-32` | Browser tab icon, 32 px | `brand/icons/favicon/favicon-32.png` | 32×32 | provisional | — | Simplified mark at 32 px |
| `favicon-48` | Browser and desktop shortcut icon, 48 px | `brand/icons/favicon/favicon-48.png` | 48×48 | provisional | — | Simplified mark at 48 px |
| `favicon-ico` | Multi-size ICO for older browsers | `brand/icons/favicon/favicon.ico` | — | provisional | — | ICO containing 16, 32 and 48 px |
| `apple-touch-180` | iOS home-screen icon | `brand/icons/application/apple-touch-icon-180.png` | 180×180 | provisional | — | 180 px icon on an opaque background |
| `pwa-192` | Installable app icon, 192 px | `brand/icons/pwa/icon-192.png` | 192×192 | provisional | — | 192 px app icon |
| `pwa-512` | Installable app icon, 512 px | `brand/icons/pwa/icon-512.png` | 512×512 | provisional | — | 512 px app icon |
| `pwa-maskable-512` | Maskable app icon for adaptive launchers | `brand/icons/pwa/icon-maskable-512.png` | 512×512 | provisional | — | 512 px icon with the mark inside the 80% safe zone |
| `social-preview` | Link preview image for social networks and chat | `brand/social/greyguard-social-1200x630.png` | — | missing | lockup-dark | 1200 x 630 px preview image |
| `document-logo` | Logo for generated documents and reports | `brand/documents/greyguard-document-logo.png` | — | missing | lockup-dark | Print-ready lockup for white paper, also as PDF/SVG |
| `splash` | Optional splash-screen rendering (the metallic hero style) | `brand/logos/primary/greyguard-primary-stacked.png` | 1839×855 | provisional | — | Optional hero rendering rebuilt on the final geometry |
