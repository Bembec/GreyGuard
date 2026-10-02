import { Inbox, RefreshCw, TriangleAlert } from "lucide-react"
import type { ReactNode } from "react"

export function LoadingState({ label = "Loading", rows = 3 }: { label?: string; rows?: number }) {
  const safeRows = Math.max(1, Math.min(rows, 8))
  return <div className="gg-loading" role="status" aria-label={label}><span className="gg-sr-only">{label}</span>{Array.from({ length: safeRows }, (_, index) => <span className="gg-skeleton" key={index}/>)}</div>
}
export function EmptyState({ title, description, icon, action }: { title: string; description: string; icon?: ReactNode; action?: ReactNode }) {
  return <div className="gg-empty">{icon ?? <Inbox size={30}/>}<strong>{title}</strong><p>{description}</p>{action}</div>
}
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="gg-error" role="alert"><TriangleAlert size={27}/><strong>Something went wrong</strong><p>{message}</p>{onRetry && <button type="button" onClick={onRetry}><RefreshCw size={15}/> Try again</button>}</div>
}
