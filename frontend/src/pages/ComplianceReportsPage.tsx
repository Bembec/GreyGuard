import {
  CalendarRange,
  CheckCircle2,
  Download,
  FileCheck2,
  FileJson,
  FileSpreadsheet,
  Fingerprint,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react"
import { useEffect, useState } from "react"

import { useAuth } from "../context/AuthContext"
import "../styles/compliance-reports.css"

type ReportSummary = {
  audit_events: number
  critical_events: number
  security_alerts: number
  open_alerts: number
  policy_versions: number
  administrators: number
  privileged_actions: number
}
type ComplianceReport = {
  report_id: string
  title: string
  created_by: string
  created_at: string
  evidence_hash: string
  integrity_verified?: boolean
  filters: { date_from?: string | null; date_to?: string | null; severities?: string[]; event_types?: string[] }
  summary: ReportSummary
}

const API = import.meta.env.VITE_API_BASE_URL ?? "/api"
const severities = ["HIGH", "CRITICAL"]
const eventTypes = ["POLICY", "AUTHENTICATION", "APPROVAL", "EXECUTION"]

export function formatEvidenceHash(hash: string) {
  return hash.length > 20 ? `${hash.slice(0, 12)}…${hash.slice(-8)}` : hash
}

export default function ComplianceReportsPage() {
  const { sessionToken } = useAuth()
  const [reports, setReports] = useState<ComplianceReport[]>([])
  const [selected, setSelected] = useState<ComplianceReport | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [title, setTitle] = useState("Security Compliance Evidence")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [selectedSeverities, setSelectedSeverities] = useState<string[]>([])
  const [selectedTypes, setSelectedTypes] = useState<string[]>([])
  const [message, setMessage] = useState("")
  const [busy, setBusy] = useState(false)
  const headers = { "Content-Type": "application/json", "X-Admin-Pin": sessionToken ?? "" }

  const load = async () => {
    const response = await fetch(`${API}/compliance-reports`, { headers })
    const body = await response.json()
    if (!response.ok) throw new Error(body.detail ?? "Unable to load compliance reports.")
    setReports(body.reports)
  }
  useEffect(() => { void load().catch((error) => setMessage(error.message)) }, [sessionToken])

  const generate = async () => {
    setBusy(true); setMessage("")
    try {
      const response = await fetch(`${API}/compliance-reports`, {
        method: "POST", headers,
        body: JSON.stringify({ title, date_from: dateFrom || null, date_to: dateTo || null, severities: selectedSeverities, event_types: selectedTypes }),
      })
      const body = await response.json()
      if (!response.ok) throw new Error(body.detail ?? "Report generation failed.")
      setMessage("Immutable compliance evidence captured successfully.")
      setShowCreate(false); await load()
    } catch (error) { setMessage(error instanceof Error ? error.message : "Request failed.") }
    finally { setBusy(false) }
  }

  const inspect = async (report: ComplianceReport) => {
    const response = await fetch(`${API}/compliance-reports/${report.report_id}`, { headers })
    const body = await response.json()
    if (!response.ok) { setMessage(body.detail ?? "Report could not be opened."); return }
    setSelected(body)
  }

  const download = async (report: ComplianceReport, format: "json" | "csv") => {
    const response = await fetch(`${API}/compliance-reports/${report.report_id}/export?format=${format}`, { headers })
    if (!response.ok) { const body = await response.json(); setMessage(body.detail ?? "Export failed."); return }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url; link.download = `${report.report_id}.${format}`; link.click()
    URL.revokeObjectURL(url)
  }

  const toggle = (value: string, current: string[], update: (values: string[]) => void) => update(current.includes(value) ? current.filter((item) => item !== value) : [...current, value])

  return <main className="compliance-page">
    <section className="compliance-hero"><div><p><ShieldCheck size={15} /> Assurance and governance</p><h1>Compliance Reports</h1><span>Capture immutable, verifiable evidence snapshots and export them for review.</span></div><button onClick={() => setShowCreate(true)}><FileCheck2 size={17} /> Generate report</button></section>
    <section className="compliance-assurance"><Fingerprint /><div><strong>Evidence integrity built in</strong><span>Every report is sealed with a SHA-256 fingerprint and verified whenever it is opened.</span></div></section>
    {message && <p className="compliance-message">{message}</p>}

    <section className="compliance-history"><header><div><FileCheck2 /><span><strong>Report history</strong><small>{reports.length} immutable snapshots</small></span></div><button onClick={() => void load()}><RefreshCw size={16} /> Refresh</button></header>
      {reports.length === 0 && <div className="compliance-empty"><FileCheck2 size={31} /><strong>No compliance reports yet</strong><span>Generate the first point-in-time evidence snapshot.</span></div>}
      <div className="compliance-list">{reports.map((report) => <article key={report.report_id}>
        <button className="compliance-main" onClick={() => void inspect(report)}><span className="report-icon"><FileCheck2 /></span><span className="report-copy"><strong>{report.title}</strong><small>{new Date(report.created_at).toLocaleString()} · {report.created_by}</small><code>{formatEvidenceHash(report.evidence_hash)}</code></span></button>
        <div className="report-counts"><span><strong>{report.summary.audit_events}</strong> events</span><span><strong>{report.summary.security_alerts}</strong> alerts</span><span><strong>{report.summary.privileged_actions}</strong> privileged</span></div>
        <div className="report-downloads"><button onClick={() => void download(report, "json")}><FileJson size={16} /> JSON</button><button onClick={() => void download(report, "csv")}><FileSpreadsheet size={16} /> CSV</button></div>
      </article>)}</div>
    </section>

    {showCreate && <div className="compliance-modal"><button className="backdrop" onClick={() => setShowCreate(false)} aria-label="Close"/><section><header><div><h2>Generate evidence report</h2><p>Blank filters include all available evidence.</p></div><button onClick={() => setShowCreate(false)}><X /></button></header>
      <label>Report title<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
      <div className="date-fields"><label>From<input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label><label>To<input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} /></label></div>
      <fieldset><legend>Severity</legend>{severities.map((item) => <label key={item}><input type="checkbox" checked={selectedSeverities.includes(item)} onChange={() => toggle(item, selectedSeverities, setSelectedSeverities)} />{item}</label>)}</fieldset>
      <fieldset><legend>Event types</legend>{eventTypes.map((item) => <label key={item}><input type="checkbox" checked={selectedTypes.includes(item)} onChange={() => toggle(item, selectedTypes, setSelectedTypes)} />{item}</label>)}</fieldset>
      <footer><button className="secondary" onClick={() => setShowCreate(false)}>Cancel</button><button disabled={busy || title.trim().length < 3} onClick={() => void generate()}><CalendarRange size={16} /> Capture evidence</button></footer>
    </section></div>}

    {selected && <div className="compliance-modal"><button className="backdrop" onClick={() => setSelected(null)} aria-label="Close"/><section className="report-details"><header><div><h2>{selected.title}</h2><p>{selected.report_id}</p></div><button onClick={() => setSelected(null)}><X /></button></header>
      <div className={`integrity ${selected.integrity_verified ? "verified" : "failed"}`}><CheckCircle2 /><div><strong>{selected.integrity_verified ? "Integrity verified" : "Integrity check failed"}</strong><code>{selected.evidence_hash}</code></div></div>
      <div className="detail-metrics">{Object.entries(selected.summary).map(([label, value]) => <div key={label}><strong>{value}</strong><span>{label.replaceAll("_", " ")}</span></div>)}</div>
      <footer><button onClick={() => void download(selected, "json")}><Download size={16} /> Export JSON</button><button onClick={() => void download(selected, "csv")}><Download size={16} /> Export CSV</button></footer>
    </section></div>}
  </main>
}
