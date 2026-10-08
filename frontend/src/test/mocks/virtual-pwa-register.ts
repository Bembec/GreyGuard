import { vi } from "vitest"

// Stands in for the real virtual:pwa-register module, which only resolves under an actual
// Vite build via vite-plugin-pwa (see vitest.config.ts's resolve.alias). Tests configure this
// mock's behavior directly rather than through vi.mock, since Vite's own import-analysis
// plugin resolves the "virtual:" specifier before vi.mock's module registry can intervene.
export const registerSW = vi.fn()
