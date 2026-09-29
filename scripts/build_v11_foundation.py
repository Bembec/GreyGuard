from pathlib import Path


root = Path(__file__).resolve().parents[1]

files = {
    ".editorconfig": """
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
indent_style = space
indent_size = 2
trim_trailing_whitespace = true

[*.py]
indent_size = 4

[*.md]
trim_trailing_whitespace = false
""",
    ".gitattributes": """
* text=auto
*.py text eol=lf
*.ts text eol=lf
*.tsx text eol=lf
*.css text eol=lf
*.json text eol=lf
*.md text eol=lf
*.png binary
*.jpg binary
*.jpeg binary
*.ico binary
""",
    ".env.example": """
GREYGUARD_ADMIN_PIN=replace-with-a-secure-pin
VITE_API_BASE_URL=/api
""",
    "docs/design-system.md": """
# GreyGuard V11 Design System

## Visual Identity

GreyGuard uses the **Sentinel Vault** visual direction: a professional
agent-security control plane combining observability, policy enforcement,
containment, risk intelligence and human approval.

The interface must feel advanced without imitating a fictional
"hacker screen."

## Primary Colours

- Obsidian: `#05070d`
- Deep Navy: `#09111f`
- Graphite: `#111827`
- Steel: `#1f2937`
- Cyan: `#22d3ee`
- Electric Blue: `#3b82f6`
- Violet: `#8b5cf6`
- Success Green: `#22c55e`
- Approval Amber: `#f59e0b`
- Critical Red: `#ef4444`
- Primary Text: `#f8fafc`
- Secondary Text: `#94a3b8`

## Decision Colours

- `ALLOW`: green
- `ASK`: amber
- `BLOCK`: red
- `REFUSED`: rose
- `DRY_RUN`: cyan
- `SUCCEEDED`: green
- `FAILED`: red
- `SUSPENDED`: red
- `ACTIVE`: cyan

## Typography

Use the local system font stack for interface text and a monospace stack
for credentials, request IDs, timestamps and technical evidence.

## Background System

Every major section has its own composition:

- Dashboard: security grid and pulsing nodes
- Agents: agent constellation
- Tool Requests: flowing execution lanes
- Approvals: rotating vault rings
- Policies: policy matrix
- Risk Center: radar field
- Audit: streaming ledger
- Authentication: identity waves
- Sandbox: containment chamber
- Settings: encrypted circuit field

Backgrounds must remain subtle enough for text readability.

## Accessibility

- Visible keyboard focus
- WCAG-conscious contrast
- Reduced-motion mode
- Touch-friendly mobile controls
- Semantic headings and landmarks
- Icons must not be the only status indicator
""",
    "frontend/src/styles/tokens.css": """
:root {
  color-scheme: dark;

  --gg-obsidian: #05070d;
  --gg-navy-950: #07101d;
  --gg-navy-900: #09111f;
  --gg-navy-850: #0c1627;
  --gg-surface-900: #101827;
  --gg-surface-850: #131d2d;
  --gg-surface-800: #172234;
  --gg-surface-700: #223047;

  --gg-text-primary: #f8fafc;
  --gg-text-secondary: #a5b4c7;
  --gg-text-muted: #6f8097;

  --gg-cyan: #22d3ee;
  --gg-cyan-soft: #67e8f9;
  --gg-blue: #3b82f6;
  --gg-violet: #8b5cf6;
  --gg-green: #22c55e;
  --gg-amber: #f59e0b;
  --gg-red: #ef4444;
  --gg-rose: #fb7185;

  --gg-border: rgba(148, 163, 184, 0.16);
  --gg-border-strong: rgba(34, 211, 238, 0.28);
  --gg-panel: rgba(10, 18, 32, 0.78);
  --gg-panel-solid: #0d1727;
  --gg-overlay: rgba(3, 7, 18, 0.78);

  --gg-shadow-sm:
    0 8px 24px rgba(0, 0, 0, 0.2);
  --gg-shadow-md:
    0 18px 50px rgba(0, 0, 0, 0.34);
  --gg-glow-cyan:
    0 0 40px rgba(34, 211, 238, 0.12);
  --gg-glow-violet:
    0 0 44px rgba(139, 92, 246, 0.12);

  --gg-radius-sm: 8px;
  --gg-radius-md: 14px;
  --gg-radius-lg: 20px;
  --gg-radius-xl: 28px;

  --gg-space-1: 0.25rem;
  --gg-space-2: 0.5rem;
  --gg-space-3: 0.75rem;
  --gg-space-4: 1rem;
  --gg-space-5: 1.25rem;
  --gg-space-6: 1.5rem;
  --gg-space-8: 2rem;
  --gg-space-10: 2.5rem;
  --gg-space-12: 3rem;

  --gg-sidebar-width: 280px;
  --gg-sidebar-collapsed: 88px;
  --gg-topbar-height: 76px;

  --gg-font-sans:
    Inter, ui-sans-serif, system-ui, -apple-system,
    BlinkMacSystemFont, "Segoe UI", sans-serif;
  --gg-font-mono:
    "SFMono-Regular", Consolas, "Liberation Mono",
    monospace;

  --gg-ease:
    cubic-bezier(0.22, 1, 0.36, 1);
  --gg-transition-fast:
    150ms var(--gg-ease);
  --gg-transition:
    260ms var(--gg-ease);
  --gg-transition-slow:
    600ms var(--gg-ease);
}

[data-theme="light"] {
  color-scheme: light;

  --gg-obsidian: #edf4fa;
  --gg-navy-950: #f7fafc;
  --gg-navy-900: #eef4f8;
  --gg-navy-850: #e5edf4;
  --gg-surface-900: #ffffff;
  --gg-surface-850: #f7fafc;
  --gg-surface-800: #edf2f7;
  --gg-surface-700: #d7e1eb;

  --gg-text-primary: #0f172a;
  --gg-text-secondary: #40516a;
  --gg-text-muted: #64748b;

  --gg-border: rgba(51, 65, 85, 0.16);
  --gg-border-strong: rgba(8, 145, 178, 0.3);
  --gg-panel: rgba(255, 255, 255, 0.84);
  --gg-panel-solid: #ffffff;
  --gg-overlay: rgba(226, 232, 240, 0.82);
}
""",
    "frontend/src/styles/global.css": """
@import "./tokens.css";

* {
  box-sizing: border-box;
}

html {
  min-width: 320px;
  min-height: 100%;
  background: var(--gg-obsidian);
  scroll-behavior: smooth;
}

body {
  min-width: 320px;
  min-height: 100vh;
  margin: 0;
  overflow-x: hidden;
  color: var(--gg-text-primary);
  background:
    radial-gradient(
      circle at 12% 8%,
      rgba(34, 211, 238, 0.08),
      transparent 30%
    ),
    radial-gradient(
      circle at 88% 6%,
      rgba(139, 92, 246, 0.09),
      transparent 26%
    ),
    var(--gg-obsidian);
  font-family: var(--gg-font-sans);
  font-synthesis: none;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
}

button,
input,
select,
textarea {
  font: inherit;
}

button,
a {
  -webkit-tap-highlight-color: transparent;
}

button {
  color: inherit;
}

a {
  color: inherit;
  text-decoration: none;
}

img,
svg {
  display: block;
  max-width: 100%;
}

h1,
h2,
h3,
h4,
p {
  margin-top: 0;
}

code,
pre,
.gg-mono {
  font-family: var(--gg-font-mono);
}

::selection {
  color: #001018;
  background: var(--gg-cyan-soft);
}

:focus-visible {
  outline: 2px solid var(--gg-cyan);
  outline-offset: 3px;
}

.gg-sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.gg-panel {
  border: 1px solid var(--gg-border);
  border-radius: var(--gg-radius-lg);
  background: var(--gg-panel);
  box-shadow: var(--gg-shadow-sm);
  backdrop-filter: blur(18px);
}

.gg-scrollbar {
  scrollbar-width: thin;
  scrollbar-color:
    rgba(34, 211, 238, 0.25)
    transparent;
}

.gg-scrollbar::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.gg-scrollbar::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(34, 211, 238, 0.25);
}

.gg-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

@media (prefers-reduced-motion: reduce) {
  html {
    scroll-behavior: auto;
  }

  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
""",
    "frontend/src/main.tsx": """
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import App from "./App"
import "./styles/global.css"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

const rootElement = document.getElementById("root")

if (!rootElement) {
  throw new Error("GreyGuard root element was not found.")
}

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
""",
    "frontend/vite.config.ts": """
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\\/api/, ""),
      },
    },
  },
  build: {
    sourcemap: true,
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: {
          react: [
            "react",
            "react-dom",
            "react-router-dom",
          ],
          query: ["@tanstack/react-query"],
          charts: ["recharts"],
          icons: ["lucide-react"],
        },
      },
    },
  },
})
""",
    "frontend/index.html": """
<!doctype html>
<html lang="en" data-theme="dark">
  <head>
    <meta charset="UTF-8" />
    <meta
      name="viewport"
      content="width=device-width, initial-scale=1.0"
    />
    <meta
      name="theme-color"
      content="#05070d"
    />
    <meta
      name="description"
      content="GreyGuard multi-agent security control plane"
    />
    <link
      rel="icon"
      type="image/png"
      href="/brand/greyguard-symbol.png"
    />
    <title>GreyGuard — Agent Security Control Plane</title>
  </head>
  <body>
    <div id="root"></div>
    <script
      type="module"
      src="/src/main.tsx"
    ></script>
  </body>
</html>
""",
}


for relative_path, content in files.items():
    destination = root / relative_path

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination.write_text(
        content.strip() + "\n",
        encoding="utf-8",
    )

    print(
        "Created:",
        destination.relative_to(root),
    )


print()
print(
    "GreyGuard V11 design foundation created."
)