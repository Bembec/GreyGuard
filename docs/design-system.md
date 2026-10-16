# GreyGuard console design system (v2)

Adopted in P7.5 on 2026-10-16. It replaces the earlier "Sentinel Vault" direction, whose per-page animated backgrounds, glows and large rounded cards made the console look unlike both its references and the public website.

## Direction

The console follows the signed-in consoles that security and developer teams already use: Linear, GitLab, Grafana, Datadog, and Vercel's Geist system. They were studied from their public product pages and playgrounds. What they share, and what GreyGuard now does:

- **A compact left sidebar.** One-line items, 16 px icons and quiet section labels. Descriptions live in tooltips, not under every item. Top mega-menus are a public-website pattern.
- **A slim top bar** with the breadcrumb, page title, search, notifications and user menu.
- **Flat surfaces separated by hairline borders.** No glows, gradients, orbits, grids or watermarks behind content.
- **Colour that carries meaning.** Cyan marks only the active item, keyboard focus and the primary action. Green, amber and red mark status.
- **Dense, legible data.** Small type, tabular numbers, and table headers in normal case.

The palette is the public website's, so the site and the console read as one company.

## Tokens (`frontend/src/styles/tokens.css`)

| Role | Token | Value |
|---|---|---|
| Canvas | `--gg-navy-950` | `#050a12` (brand navy) |
| Sidebar | `--gg-navy-900` | `#08101b` |
| Surface (cards, panels) | `--gg-surface-900` | `#0b1421` |
| Raised surface (menus, dialogs) | `--gg-surface-850` | `#0e1826` |
| Hairline / strong border | `--gg-border` / `--gg-border-strong` | slate at 13% / 24% |
| Hover / selected | `--gg-hover` / `--gg-selected` | slate 7% / cyan 10% |
| Text | `--gg-text-primary` / `-secondary` / `-muted` | `#edf2f6` / `#a3afbb` / `#6d7a89` |
| Accent | `--gg-cyan` | `#48c8f8` (brand glow) |
| Status | `--gg-green` / `--gg-amber` / `--gg-red` | `#4ade80` / `#fbbf24` / `#f87171` |
| Radius | `--gg-radius-sm` / `-md` / `-lg` | 6 / 8 / 10 px |
| Shell | `--gg-sidebar-width` / `--gg-topbar-height` | 248 px / 52 px |

The glow tokens (`--gg-glow-*`) resolve to `none` so that older rules still compile. Do not reintroduce glows.

## Typography

- Interface text is Inter at a 14 px base. Page titles are Inter 600 at 1.5 rem; panel titles at 0.95 rem.
- Saira, the brand display face, is kept for the sign-in and splash screens and for the public website.
- Labels, eyebrows and table headers use normal case in muted text. Status values that are uppercase in the data (ALLOW, ACTIVE) stay as they are.
- Numbers use tabular figures.
- The monospace stack is for credentials, request IDs, hashes and technical evidence.

## Components (`frontend/src/components/page/`)

- **`PageHeader`**: the title, a one-sentence purpose and page actions. The workspace sits in the breadcrumb, so it is not repeated above the title. The eyebrow carries only extra context, such as the organization.
- **`StatGrid` / `StatCard`**: two to five KPIs. A flat card with a muted label, the value, a hint, and a status-coloured icon (`tone`). Configuration facts are not KPIs: use a `gg-facts` row instead.
- **`Panel`**, **`DataTable`**, **`FilterBar`**, **`Guidance`**, **`StatusBadge`**, and the empty, loading and error states.
- **Buttons:** 32 px high with a 6 px radius. `gg-button--primary` is solid cyan with dark text and is used once per area. `gg-button--danger` is for destructive actions, which are always confirmed.
- **Native dropdowns** are normalised for the whole content area in `page-kit.css`.

Pages built before the page kit keep their own layouts. Each of their stylesheets ends with a "Design v2" block that flattens their surfaces, quiets their labels and hides their decorative layers. New work uses the page kit instead.

## Decision colours

- `ALLOW`, `SUCCEEDED`: green
- `ASK`: amber
- `BLOCK`, `FAILED`, `SUSPENDED`: red
- `REFUSED`: rose
- `DRY_RUN`, `ACTIVE`: cyan

## Accessibility

- Visible keyboard focus: a 2 px cyan outline.
- WCAG-conscious contrast on every surface.
- Reduced-motion mode. Nothing in the shell animates by default.
- Touch-friendly mobile controls, and no horizontal scroll at 390 px (checked for every page in `e2e/every-page.spec.ts`).
- Semantic headings and landmarks.
- Icons are never the only status indicator.

## Light theme

The console is dark-only for now (decision V2). Because colours now flow through these tokens, a light theme is a token set rather than a rewrite of every stylesheet.
