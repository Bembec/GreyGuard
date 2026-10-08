import { useEffect, useRef, type RefObject } from "react"

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

interface UseDismissableLayerOptions {
  open: boolean
  onClose: () => void
  /** Full Tab-loop focus trap (true modal dialogs). Default false (Escape + focus restore only). */
  trapFocus?: boolean
  /** Element to focus when the layer opens. Defaults to the container itself. */
  initialFocusRef?: RefObject<HTMLElement | null>
  /** Suppresses Escape-to-close, e.g. while a destructive action is in flight. */
  disabled?: boolean
  /** True modal dialogs should also stop background scroll. */
  lockBodyScroll?: boolean
}

/**
 * Shared open/close behavior for any dismissable overlay (dialog, menu, popover):
 * captures the previously focused element, moves focus in on open, closes and restores
 * focus on Escape, and optionally traps Tab inside the container. Extracted from
 * ConfirmDialog/GlobalSearchDialog, which both hand-rolled this before.
 */
export function useDismissableLayer<T extends HTMLElement = HTMLElement>({
  open,
  onClose,
  trapFocus = false,
  initialFocusRef,
  disabled = false,
  lockBodyScroll = false,
}: UseDismissableLayerOptions) {
  const containerRef = useRef<T>(null)

  useEffect(() => {
    if (!open) return

    const previous = document.activeElement as HTMLElement | null
    const originalOverflow = document.body.style.overflow
    if (lockBodyScroll) document.body.style.overflow = "hidden"

    window.setTimeout(() => {
      (initialFocusRef?.current ?? containerRef.current)?.focus()
    }, 0)

    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (!disabled) onClose()
        return
      }
      if (!trapFocus || event.key !== "Tab") return
      const focusable = [...(containerRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? [])]
      if (!focusable.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener("keydown", keydown)
    return () => {
      document.removeEventListener("keydown", keydown)
      if (lockBodyScroll) document.body.style.overflow = originalOverflow
      previous?.focus()
    }
  }, [open, onClose, trapFocus, disabled, lockBodyScroll, initialFocusRef])

  return containerRef
}
