import { AlertTriangle, X } from "lucide-react"
import { useEffect, useRef } from "react"

type Props = { open: boolean; title: string; description: string; confirmLabel: string; cancelLabel?: string; tone?: "danger" | "warning"; busy?: boolean; onConfirm: () => void; onCancel: () => void }

export function ConfirmDialog({ open, title, description, confirmLabel, cancelLabel = "Cancel", tone = "danger", busy = false, onConfirm, onCancel }: Props) {
  const dialogRef = useRef<HTMLElement>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    cancelRef.current?.focus()
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onCancel()
      if (event.key !== "Tab") return
      const focusable = [...(dialogRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])') ?? [])]
      if (!focusable.length) return
      const first = focusable[0]; const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener("keydown", keydown)
    return () => { document.removeEventListener("keydown", keydown); document.body.style.overflow = originalOverflow; previous?.focus() }
  }, [busy, onCancel, open])
  if (!open) return null
  return <div className="gg-confirm" role="presentation"><button className="gg-confirm__backdrop" type="button" onClick={() => !busy && onCancel()} aria-label="Cancel action"/><section ref={dialogRef} role="alertdialog" aria-modal="true" aria-labelledby="gg-confirm-title" aria-describedby="gg-confirm-description"><header><span className={`gg-confirm__icon gg-confirm__icon--${tone}`}><AlertTriangle size={22}/></span><button type="button" onClick={onCancel} disabled={busy} aria-label="Close confirmation"><X size={19}/></button></header><h2 id="gg-confirm-title">{title}</h2><p id="gg-confirm-description">{description}</p><footer><button ref={cancelRef} type="button" className="gg-confirm__cancel" onClick={onCancel} disabled={busy}>{cancelLabel}</button><button type="button" className={`gg-confirm__action gg-confirm__action--${tone}`} onClick={onConfirm} disabled={busy}>{busy ? "Working…" : confirmLabel}</button></footer></section></div>
}
