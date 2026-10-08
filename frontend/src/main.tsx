import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import App from "./App"
import { applySettings, loadSettings } from "./lib/interfaceSettings"
import "@fontsource/inter/400.css"
import "@fontsource/inter/500.css"
import "@fontsource/inter/600.css"
import "@fontsource/inter/700.css"
import "@fontsource/saira/600.css"
import "@fontsource/saira/700.css"
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

// Applied synchronously before the first render, not inside a React effect - otherwise a
// saved reduced-motion/density/accent preference would only take effect once SettingsPage
// itself mounted, reverting to defaults on every hard reload until the operator revisited it.
applySettings(loadSettings())

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
