import { AlertTriangle, X } from "lucide-react"
import { useRef } from "react"

import { useDismissableLayer } from "../hooks/useDismissableLayer"

type Props = { open: boolean; title: string; description: string; confirmLabel: string; cancelLabel?: string; tone?: "danger" | "warning"; busy?: boolean; onConfirm: () => void; onCancel: () => void }

export function ConfirmDialog({ open, title, description, confirmLabel, cancelLabel = "Cancel", tone = "danger", busy = false, onConfirm, onCancel }: Props) {
  const cancelRef = useRef<HTMLButtonElement>(null)
  const dialogRef = useDismissableLayer<HTMLElement>({
    open, onClose: onCancel, trapFocus: true, initialFocusRef: cancelRef, disabled: busy, lockBodyScroll: true,
  })
  if (!open) return null
  return <div className="gg-confirm" role="presentation"><button className="gg-confirm__backdrop" type="button" onClick={() => !busy && onCancel()} aria-label="Cancel action"/><section ref={dialogRef} role="alertdialog" aria-modal="true" aria-labelledby="gg-confirm-title" aria-describedby="gg-confirm-description"><header><span className={`gg-confirm__icon gg-confirm__icon--${tone}`}><AlertTriangle size={22}/></span><button type="button" onClick={onCancel} disabled={busy} aria-label="Close confirmation"><X size={19}/></button></header><h2 id="gg-confirm-title">{title}</h2><p id="gg-confirm-description">{description}</p><footer><button ref={cancelRef} type="button" className="gg-confirm__cancel" onClick={onCancel} disabled={busy}>{cancelLabel}</button><button type="button" className={`gg-confirm__action gg-confirm__action--${tone}`} onClick={onConfirm} disabled={busy}>{busy ? "Working…" : confirmLabel}</button></footer></section></div>
}
