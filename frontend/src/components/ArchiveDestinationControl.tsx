import { Archive } from "lucide-react"
import { useState } from "react"

import { ConfirmDialog } from "./ConfirmDialog"
import { useToast } from "../context/ToastContext"
import { usePermission } from "../hooks/usePermission"

const API = import.meta.env.VITE_API_BASE_URL ?? "/api"
// The server requires an archive reason of at least this length (archival._reason).
const REASON_MIN_LENGTH = 10

export type DestinationKind = "security_export" | "incident" | "notification"

export const destinationArchiveState = (archivedAt?: string | null) => (archivedAt ? "ARCHIVED" : null)

/** Retire a destination for good (P4 decision D6): disabled, history kept, capacity freed. Only a
 * Platform Admin may archive; an archived destination shows when it was archived instead. */
export function ArchiveDestinationControl({ kind, destinationId, name, archivedAt, onArchived }: {
  kind: DestinationKind; destinationId: string; name: string; archivedAt?: string | null; onArchived: () => void | Promise<void>
}) {
  const canArchive = usePermission({ role: "PLATFORM_ADMIN" })
  const { pushToast } = useToast()
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)

  if (archivedAt) return <p className="archive-note">Archived {new Date(archivedAt).toLocaleDateString()} · kept as history; cannot be re-enabled.</p>
  if (!canArchive) return null

  const archive = async () => {
    setBusy(true)
    try {
      const response = await fetch(`${API}/integrations/${kind}/${encodeURIComponent(destinationId)}/archive`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" },
        body: JSON.stringify({ reason: reason.trim() }),
      })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) {
        pushToast({ tone: "error", title: "Archive refused", message: typeof body.detail === "string" ? body.detail : `Request failed (${response.status}).` })
        return
      }
      pushToast({ tone: "success", title: `${name} archived`, message: "Its delivery history is kept, and it no longer counts toward plan capacity." })
      setOpen(false)
      await onArchived()
    } finally {
      setBusy(false)
    }
  }

  return <>
    <button type="button" className="archive-button" onClick={() => { setReason(""); setOpen(true) }}><Archive size={15}/> Archive</button>
    <ConfirmDialog
      open={open}
      title={`Archive ${name}?`}
      description="It is disabled for good and stops counting toward plan capacity. Its delivery history is kept. A new destination will need a new name. This cannot be undone."
      confirmLabel="Archive destination"
      busy={busy}
      confirmDisabled={reason.trim().length < REASON_MIN_LENGTH}
      onCancel={() => setOpen(false)}
      onConfirm={() => void archive()}
    >
      <label className="gg-confirm__field">
        Reason (recorded in the audit log)
        <textarea value={reason} minLength={REASON_MIN_LENGTH} maxLength={1000} rows={3} onChange={(event) => setReason(event.target.value)}/>
      </label>
    </ConfirmDialog>
  </>
}
