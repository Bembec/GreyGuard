import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"


export default defineConfig({
  plugins: [
    react(),
  ],

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