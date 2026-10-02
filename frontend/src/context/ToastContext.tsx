import { AlertCircle, CheckCircle2, Info, TriangleAlert, X } from "lucide-react"
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react"
import "../styles/ux-foundation.css"

export type ToastTone = "success" | "error" | "warning" | "info"
export type ToastInput = { tone: ToastTone; title: string; message?: string; duration?: number }
type Toast = ToastInput & { id: number }
type ToastContextValue = { pushToast: (toast: ToastInput) => number; dismissToast: (id: number) => void }
const ToastContext = createContext<ToastContextValue | null>(null)

export function normalizeToastDuration(duration?: number) {
  return Math.max(2000, Math.min(duration ?? 5000, 15000))
}

const icons = { success: CheckCircle2, error: AlertCircle, warning: TriangleAlert, info: Info }

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)
  const dismissToast = useCallback((id: number) => setToasts((items) => items.filter((item) => item.id !== id)), [])
  const pushToast = useCallback((input: ToastInput) => {
    const id = nextId.current++
    setToasts((items) => [...items.slice(-3), { ...input, id }])
    window.setTimeout(() => dismissToast(id), normalizeToastDuration(input.duration))
    return id
  }, [dismissToast])
  const value = useMemo(() => ({ pushToast, dismissToast }), [pushToast, dismissToast])
  return <ToastContext.Provider value={value}>{children}<section className="gg-toast-region" aria-label="Notifications" aria-live="polite">{toasts.map((toast) => { const Icon = icons[toast.tone]; return <article className={`gg-toast gg-toast--${toast.tone}`} key={toast.id} role={toast.tone === "error" ? "alert" : "status"}><span className="gg-toast__icon"><Icon size={19}/></span><div><strong>{toast.title}</strong>{toast.message && <p>{toast.message}</p>}</div><button type="button" onClick={() => dismissToast(toast.id)} aria-label="Dismiss notification"><X size={17}/></button></article> })}</section></ToastContext.Provider>
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error("useToast must be used inside ToastProvider.")
  return context
}
