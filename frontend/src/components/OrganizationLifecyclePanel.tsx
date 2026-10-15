import { CheckCircle2, Circle, Download, ListChecks } from "lucide-react"
import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"

import { ErrorState, LoadingState } from "./AsyncState"
import { useAuth } from "../context/AuthContext"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api"

type ChecklistItem = { key: string; label: string; done: boolean }

export type Lifecycle = {
  org_id: string
  name: string
  status: "ACTIVE" | "OFFBOARDING" | "DELETED"
  offboarding: { started_at: string; reason: string; deletion_eligible_at: string } | null
  checklist: ChecklistItem[]
  checklist_complete: number
}

const headers = () => ({ "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" })

export function checklistProgress(items: ChecklistItem[]): string {
  return `${items.filter((item) => item.done).length} of ${items.length} complete`
}

export function exportFilename(orgId: string, now: Date = new Date()): string {
  return `greyguard-${orgId.replace(/[^a-zA-Z0-9_-]/g, "")}-export-${now.toISOString().slice(0, 10)}.json`
}

/** The active org's lifecycle: onboarding checklist computed by the backend from real data,
 * offboarding status, and - for owners and install operators - a full data export. */
export function OrganizationLifecyclePanel() {
  const { administrator } = useAuth()
  const orgId = administrator?.active_org_id ?? null
  const membership = administrator?.organizations?.find((item) => item.org_id === orgId)
  const canExport = membership?.governance_role === "OWNER" || Boolean(administrator?.install_operator)
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  const lifecycle = useQuery({
    queryKey: ["organization-lifecycle", orgId],
    enabled: Boolean(orgId),
    queryFn: async (): Promise<Lifecycle> => {
      const response = await fetch(`${API_BASE_URL}/organizations/${orgId}/lifecycle`, { headers: headers() })
      if (!response.ok) throw new Error(`Organization status could not be loaded (${response.status}).`)
      return response.json()
    },
  })

  const exportData = async () => {
    if (!orgId) return
    setExporting(true)
    setMessage(null)
    try {
      const response = await fetch(`${API_BASE_URL}/organizations/${orgId}/export`, { method: "POST", headers: headers() })
      const body = await response.json()
      if (!response.ok) throw new Error(body.detail ?? `Export failed (${response.status}).`)
      const url = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: "application/json" }))
      const link = document.createElement("a")
      link.href = url
      link.download = exportFilename(orgId)
      link.click()
      URL.revokeObjectURL(url)
      setMessage(`Exported. Bundle digest ${String(body.digest).slice(0, 16)}…`)
      void queryClient.invalidateQueries({ queryKey: ["organization-lifecycle", orgId] })
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Export failed.")
    } finally {
      setExporting(false)
    }
  }

  if (!orgId) return null
  const data = lifecycle.data

  return (
    <section className="settings-panel">
      <div className="settings-panel-heading">
        <div className="settings-heading-icon">
          <ListChecks size={20} />
        </div>
        <div>
          <span>Organization lifecycle</span>
          <h2>Readiness &amp; data</h2>
        </div>
      </div>

      {lifecycle.isLoading && <LoadingState label="Loading organization status" rows={2} />}
      {lifecycle.isError && <ErrorState message={lifecycle.error.message} onRetry={() => void lifecycle.refetch()} />}
      {data && (
        <>
          {data.status === "OFFBOARDING" && data.offboarding && (
            <p className="plan-notice" role="status">
              This organization is offboarding and is read-only. Its data can be exported until deletion, which is
              possible from {new Date(data.offboarding.deletion_eligible_at).toLocaleDateString()}.
            </p>
          )}
          <div className="environment-list">
            <div>
              <span>Status</span>
              <code>{data.status}</code>
            </div>
            <div>
              <span>Readiness checklist</span>
              <code>{checklistProgress(data.checklist)}</code>
            </div>
          </div>
          <ul className="lifecycle-checklist">
            {data.checklist.map((item) => (
              <li key={item.key} className={item.done ? "is-done" : undefined}>
                {item.done ? <CheckCircle2 size={16} aria-hidden /> : <Circle size={16} aria-hidden />}
                <span>
                  {item.label}
                  <span className="lifecycle-visually-hidden">{item.done ? " (complete)" : " (not complete)"}</span>
                </span>
              </li>
            ))}
          </ul>
          {canExport && (
            <div className="lifecycle-actions">
              <button type="button" className="settings-secondary-button" onClick={() => void exportData()} disabled={exporting}>
                <Download size={16} aria-hidden /> {exporting ? "Exporting…" : "Export organization data"}
              </button>
              {message && <p role="status">{message}</p>}
            </div>
          )}
        </>
      )}
    </section>
  )
}
