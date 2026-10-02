import { AuthProvider } from "./context/AuthContext"
import { ToastProvider } from "./context/ToastContext"
import { AppRoutes } from "./routes/AppRoutes"

function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </ToastProvider>
  )
}

export default App
