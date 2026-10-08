import { AuthProvider } from "./context/AuthContext"
import { ToastProvider } from "./context/ToastContext"
import { AppRoutes } from "./routes/AppRoutes"
import { PwaUpdatePrompt } from "./components/PwaUpdatePrompt"

function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
      <PwaUpdatePrompt />
    </ToastProvider>
  )
}

export default App
