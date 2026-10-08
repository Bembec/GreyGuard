import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import { VitePWA } from "vite-plugin-pwa"

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // "prompt" (not "autoUpdate"): an operator mid-session is never silently swapped onto new
      // app code. PwaUpdatePrompt surfaces a banner and the operator chooses when to reload.
      registerType: "prompt",
      injectRegister: false,
      includeAssets: ["brand/icons/favicon/favicon.ico"],
      manifest: {
        name: "GreyGuard — Agent Security Control Plane",
        short_name: "GreyGuard",
        description: "GreyGuard multi-agent security control plane",
        theme_color: "#050A12",
        background_color: "#050A12",
        display: "standalone",
        start_url: "/",
        scope: "/",
        icons: [
          { src: "/brand/icons/pwa/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/brand/icons/pwa/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/brand/icons/pwa/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // Precache only the built app shell (JS/CSS/fonts/icons/manifest) - never the API. A
        // security console must never serve cached/stale incident, risk or audit data while
        // appearing live, so there is no runtimeCaching entry for /api/* at all: those requests
        // always go straight to the network, untouched by the service worker, and a real
        // network failure surfaces through the existing AsyncState error states rather than a
        // silently stale response.
        navigateFallbackDenylist: [/^\/api\//],
        cleanupOutdatedCaches: true,
      },
      devOptions: {
        // Never register a service worker under `vite dev` or the Playwright/e2e preview
        // server - only a genuine production build should be cached.
        enabled: false,
      },
    }),
  ],

  server: {
    port: 5173,
    strictPort: false,

    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) =>
          path.replace(/^\/api/, ""),
      },
    },
  },

  build: {
    sourcemap: true,
    chunkSizeWarningLimit: 700,
  },
})