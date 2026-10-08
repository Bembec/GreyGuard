import { fileURLToPath } from "node:url"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"


export default defineConfig({
  plugins: [
    react(),
  ],

  resolve: {
    alias: {
      // The real "virtual:pwa-register" module only exists under an actual Vite build via
      // vite-plugin-pwa (not registered here) - this stub lets PwaUpdatePrompt.tsx resolve
      // under Vitest at all; see src/test/PwaUpdatePrompt.test.tsx for how tests drive it.
      "virtual:pwa-register": fileURLToPath(new URL("./src/test/mocks/virtual-pwa-register.ts", import.meta.url)),
    },
  },

  test: {
    environment: "node",
    globals: false,
    pool: "threads",
    maxWorkers: 1,
    fileParallelism: false,
    isolate: false,
    clearMocks: true,
    restoreMocks: true,
  },
})