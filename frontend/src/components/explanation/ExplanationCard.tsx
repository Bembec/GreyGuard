import { AlertTriangle, CheckCircle2, CircleHelp, Fingerprint, Info, ShieldCheck } from "lucide-react"
import { Link } from "react-router-dom"

import "../../styles/explanation.css"

/** The server's explanation (backend/app/decision_explanation.py). Every sentence comes from there. */
export interface Explanation {
  request_id: string
  decision: string
  basis: "recorded" | "inferred"
  reason: string
  policy: { basis: "recorded" | "inferred"; version_id: string | null; version_number: number | null; source: string | null; published_at: string | null; unchanged_since_decision: boolean | null }
  matched_rule: null | { id: string; name: string; type: string; snapshot: Record<string, unknown> }
  authentication: { method: string | null; summary: string }
  requested: { action: string; target: string; dry_run: boolean; agent_name: string; decided_at: string }
  approval_path: { required: boolean; status: string; reviews: Array<{ decision: string; actor: string; timestamp: string }>; summary?: string }
  next_step: { text: string; path: string | null; available: boolean; unavailable_reason?: string }
  limitations: Array<{ id: string; text: string }>
  integrity: { record_intact: boolean | null; policy_unchanged: boolean | null }
  why_you_see_this: string
}

function formatDate(value?: string | null) {
  if (!value) return "Not recorded"
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date)
}

const DESTINATIONS: Record<string, string> = { "/approvals": "Open Approvals", "/policies": "Open Policies" }

const RULE_TYPES: Record<string, string> = {
  PERMISSION: "Policy rule",
  DEFAULT_RULE: "Default rule (unlisted actions are blocked)",
  EMERGENCY_CONTROL: "Emergency control",
  AGENT_STATE: "Agent state",
}

/** Why GreyGuard decided as it did. Recorded facts and inferences are never mixed. No confidence score. */
export function ExplanationCard({ explanation }: { explanation: Explanation }) {
  const { policy, matched_rule: rule, integrity } = explanation
  const policyLabel = policy.version_number !== null ? `Policy v${policy.version_number}` : policy.source === "BUILTIN" ? "Built-in defaults" : "No policy version"
  return (
    <section className={`explanation explanation--${explanation.basis}`} aria-label="Why GreyGuard decided this">
      <header className="explanation__header">
        <span className={`explanation__decision decision--${explanation.decision.toLowerCase()}`}>{explanation.decision}</span>
        <span className={`explanation__basis basis--${explanation.basis}`}>
          {explanation.basis === "recorded" ? "Exact decision record" : "Inferred, not recorded"}
        </span>
      </header>
      <p className="explanation__reason" data-testid="explanation-reason">{explanation.reason}</p>

      <dl className="explanation__facts">
        <div>
          <dt>Policy and version</dt>
          <dd>
            {policyLabel}
            {policy.published_at && <> · published {formatDate(policy.published_at)}</>}
            {policy.basis === "inferred" && <> <em>(inferred from publication time)</em></>}
          </dd>
        </div>
        <div>
          <dt>Matched rule</dt>
          <dd>{rule ? <>{rule.name} <code>{rule.id}</code> <small>{RULE_TYPES[rule.type] ?? rule.type}</small></> : "Not recorded for this request."}</dd>
        </div>
        <div>
          <dt>Identity</dt>
          <dd><Fingerprint size={13} aria-hidden="true" /> {explanation.requested.agent_name}. {explanation.authentication.summary}</dd>
        </div>
        <div>
          <dt>Requested</dt>
          <dd><code>{explanation.requested.action}</code>{explanation.requested.target && <> on <code>{explanation.requested.target}</code></>}{explanation.requested.dry_run && " (dry run)"} · {formatDate(explanation.requested.decided_at)}</dd>
        </div>
        <div>
          <dt>Approval path</dt>
          <dd>
            {explanation.approval_path.required
              ? explanation.approval_path.reviews.length > 0
                ? explanation.approval_path.reviews.map((review) => `${review.decision.toLowerCase()} by ${review.actor}, ${formatDate(review.timestamp)}`).join("; ")
                : `Approval required: ${explanation.approval_path.status.toLowerCase()}.`
              : explanation.approval_path.summary}
          </dd>
        </div>
      </dl>

      <div className="explanation__next">
        <strong>Recommended next step</strong>
        <p>{explanation.next_step.text}</p>
        {explanation.next_step.available && explanation.next_step.path && <Link className="gg-button" to={explanation.next_step.path}>{DESTINATIONS[explanation.next_step.path] ?? "Open"}</Link>}
        {!explanation.next_step.available && explanation.next_step.unavailable_reason && (
          <p className="explanation__unavailable"><CircleHelp size={14} aria-hidden="true" /> <span><strong>Why is this unavailable?</strong> {explanation.next_step.unavailable_reason}</span></p>
        )}
      </div>

      <div className="explanation__integrity" aria-label="Evidence integrity">
        {integrity.record_intact === null ? (
          <p><Info size={14} aria-hidden="true" /> No decision record to verify: this request predates exact records.</p>
        ) : integrity.record_intact ? (
          <p className="is-ok"><CheckCircle2 size={14} aria-hidden="true" /> The decision record matches the fingerprint taken when it was written.</p>
        ) : (
          <p className="is-bad"><AlertTriangle size={14} aria-hidden="true" /> The decision record no longer matches its fingerprint. Treat it as tampered.</p>
        )}
        {integrity.policy_unchanged === true && <p className="is-ok"><ShieldCheck size={14} aria-hidden="true" /> The policy version still holds the content that decided.</p>}
      </div>

      {explanation.limitations.length > 0 && (
        <details className="explanation__limits">
          <summary>Known limitations ({explanation.limitations.length})</summary>
          <ul>{explanation.limitations.map((item) => <li key={item.id}>{item.text}</li>)}</ul>
        </details>
      )}
      <p className="explanation__why"><Info size={13} aria-hidden="true" /> <span><strong>Why am I seeing this?</strong> {explanation.why_you_see_this}</span></p>
    </section>
  )
}
