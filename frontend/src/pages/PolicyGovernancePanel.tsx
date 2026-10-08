import { useEffect, useState } from "react"
import { useAuth } from "../context/AuthContext"
import "../styles/policy-governance.css"

const API = import.meta.env.VITE_API_BASE_URL ?? "/api"
type Decision = "ALLOW" | "ASK" | "BLOCK"
type Policy = { policy_id:string; version_number:number; status:string; permissions:Record<string,Decision>; risk_weights:Record<string,number>; max_blocked_attempts:number; max_risk_score:number; change_summary:string }
type EmergencyControls = {global_deny:boolean;disabled_agents:string[];disabled_tools:string[];disabled_integrations:string[]}
type PolicyAdapter = {adapter_type:string;enabled:boolean;endpoint:string|null;owner:string;purpose:string;credentials_stored:boolean}
type PolicyRollout = {rollout_id:string;policy_id:string;percentage:number;status:string;agent_allowlist:string[]}

export default function PolicyGovernancePanel() {
  const { sessionToken, administrator } = useAuth()
  const [versions,setVersions]=useState<Policy[]>([])
  const [draft,setDraft]=useState<Policy|null>(null)
  const [message,setMessage]=useState("")
  const [simulation,setSimulation]=useState<Record<string,unknown>|null>(null)
  const [conflicts,setConflicts]=useState<Array<{action:string;severity:string;detail:string}>>([])
  const [emergency,setEmergency]=useState<EmergencyControls>({global_deny:false,disabled_agents:[],disabled_tools:[],disabled_integrations:[]})
  const [adapters,setAdapters]=useState<PolicyAdapter[]>([])
  const [rollouts,setRollouts]=useState<PolicyRollout[]>([])
  const headers={"Content-Type":"application/json","x-admin-pin":sessionToken ?? ""}
  const load=async()=>{ if(!sessionToken)return; const [r,e,a,o]=await Promise.all([fetch(`${API}/policy-versions`,{headers}),fetch(`${API}/policy-emergency-controls`,{headers}),fetch(`${API}/policy-adapters`,{headers}),fetch(`${API}/policy-rollouts`,{headers})]); const d=await r.json(); const controls=await e.json();const adapterData=await a.json();const rolloutData=await o.json(); if(!r.ok)throw new Error(d.detail); if(!e.ok)throw new Error(controls.detail); setVersions(d.versions); setDraft(d.versions.find((p:Policy)=>p.status==="DRAFT")??null);setEmergency(controls);setAdapters(adapterData.adapters??[]);setRollouts(rolloutData.rollouts??[]) }
  useEffect(()=>{load().catch(e=>setMessage(e.message))},[sessionToken])
  const call=async(path:string,method="POST",body?:unknown)=>{const r=await fetch(`${API}${path}`,{method,headers,body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw new Error(d.detail);setMessage("Change completed successfully.");await load();return d}
  const published=versions.find(p=>p.status==="PUBLISHED")
  const create=()=>published&&call("/policy-versions/drafts","POST",{permissions:published.permissions,risk_weights:published.risk_weights,max_blocked_attempts:published.max_blocked_attempts,max_risk_score:published.max_risk_score,change_summary:"New controlled policy revision"})
  const save=()=>draft&&call(`/policy-versions/${draft.policy_id}/draft`,"PUT",draft)
  const updateDecision=(action:string,value:Decision)=>setDraft(d=>d?{...d,permissions:{...d.permissions,[action]:value}}:d)
  const review=async(policy:Policy)=>{const [s,c]=await Promise.all([call(`/policy-versions/${policy.policy_id}/simulate`,"POST",{action:Object.keys(policy.permissions)[0],has_scope:true,suspended:false,current_risk:0}),fetch(`${API}/policy-versions/${policy.policy_id}/conflicts`,{headers}).then(r=>r.json())]);setSimulation(s);setConflicts(c.conflicts??[])}
  const saveEmergency=()=>call("/policy-emergency-controls","PUT",emergency)
  const toggleAdapter=(adapter:PolicyAdapter)=>{const endpoint=adapter.enabled?adapter.endpoint:window.prompt(`HTTPS endpoint for ${adapter.adapter_type}`,adapter.endpoint??"");if(!adapter.enabled&&!endpoint)return Promise.resolve();return call(`/policy-adapters/${adapter.adapter_type}`,"PUT",{enabled:!adapter.enabled,endpoint,owner:adapter.owner||"Platform Security",purpose:adapter.purpose||"External policy decision integration"})}
  const startRollout=(policy:Policy)=>call("/policy-rollouts","POST",{policy_id:policy.policy_id,percentage:0,agent_allowlist:[]})
  if(!sessionToken)return null
  // POST /policy-versions/drafts, PUT .../draft and POST .../submit all call require_policy_editor()
  // server-side (backend/app/api.py) - PLATFORM_ADMIN and SECURITY_ANALYST only, not AUDITOR.
  const canEditPolicy=administrator?.role!=="AUDITOR"
  return <section className="policy-governance">
    <header><div><span>Change control</span><h2>Policy versions and approvals</h2></div>{!draft&&canEditPolicy&&<button onClick={create}>Create draft</button>}</header>
    {message&&<p className="governance-message">{message}</p>}
    <div className="emergency-controls"><div><strong>Emergency policy controls</strong><p>Fail closed globally or disable individual agents, tools and integrations.</p></div><label><input type="checkbox" checked={emergency.global_deny} disabled={administrator?.role!=="PLATFORM_ADMIN"} onChange={e=>setEmergency({...emergency,global_deny:e.target.checked})}/> Global deny</label>{administrator?.role==="PLATFORM_ADMIN"&&<button className={emergency.global_deny?"danger":""} onClick={saveEmergency}>Save emergency controls</button>}</div>
    {draft&&<div className="governance-editor">
      {!canEditPolicy&&<p className="gg-readonly-note">Your role has read-only access to policy drafts. Platform Administrator or Security Analyst access is required to edit or submit them.</p>}
      <div className="governance-fields"><label>Change summary<input value={draft.change_summary} disabled={!canEditPolicy} onChange={e=>setDraft({...draft,change_summary:e.target.value})}/></label><label>Risk threshold<input type="number" value={draft.max_risk_score} disabled={!canEditPolicy} onChange={e=>setDraft({...draft,max_risk_score:Number(e.target.value)})}/></label><label>Blocked attempts<input type="number" value={draft.max_blocked_attempts} disabled={!canEditPolicy} onChange={e=>setDraft({...draft,max_blocked_attempts:Number(e.target.value)})}/></label></div>
      <div className="governance-rules">{Object.keys(draft.permissions).sort().map(action=><div key={action}><code>{action}</code><select value={draft.permissions[action]} disabled={!canEditPolicy} onChange={e=>updateDecision(action,e.target.value as Decision)}><option>ALLOW</option><option>ASK</option><option>BLOCK</option></select><input type="number" min="0" max="100" value={draft.risk_weights[action]} disabled={!canEditPolicy} onChange={e=>setDraft({...draft,risk_weights:{...draft.risk_weights,[action]:Number(e.target.value)}})}/></div>)}</div>
      {canEditPolicy&&<div className="governance-actions"><button onClick={save}>Save draft</button><button className="primary" onClick={()=>call(`/policy-versions/${draft.policy_id}/submit`)}>Submit for approval</button></div>}
    </div>}
    <div className="version-list">{versions.map(p=><article key={p.policy_id}><div><strong>Version {p.version_number}</strong><span className={`status ${p.status.toLowerCase()}`}>{p.status.replaceAll("_"," ")}</span><p>{p.change_summary}</p></div><div className="version-actions"><button onClick={()=>review(p)}>Simulate & review</button>{p.status==="PENDING_APPROVAL"&&administrator?.role==="PLATFORM_ADMIN"&&<><button onClick={()=>call(`/policy-versions/${p.policy_id}/approve`)}>Approve</button><button onClick={()=>call(`/policy-versions/${p.policy_id}/reject?note=Rejected%20by%20reviewer`)}>Reject</button></>}{p.status==="ARCHIVED"&&administrator?.role==="PLATFORM_ADMIN"&&<button onClick={()=>call(`/policy-versions/${p.policy_id}/rollback`)}>Rollback draft</button>}</div></article>)}</div>
    {simulation&&<div className="governance-review"><strong>Simulation result</strong><pre>{JSON.stringify(simulation,null,2)}</pre><strong>Conflict findings: {conflicts.length}</strong>{conflicts.map(item=><p key={`${item.action}-${item.detail}`}>{item.severity}: {item.action} — {item.detail}</p>)}</div>}
    <div className="policy-integrations"><h3>Policy adapters</h3><p>Adapters remain disabled until a Platform Administrator assigns an owner, purpose and HTTPS endpoint.</p><div className="adapter-grid">{adapters.map(adapter=><article key={adapter.adapter_type}><strong>{adapter.adapter_type}</strong><span className={`status ${adapter.enabled?"published":"rejected"}`}>{adapter.enabled?"ENABLED":"DISABLED"}</span><small>Credentials stored: {String(adapter.credentials_stored)}</small>{administrator?.role==="PLATFORM_ADMIN"&&<button onClick={()=>toggleAdapter(adapter)}>{adapter.enabled?"Disable":"Configure & enable"}</button>}</article>)}</div><h3>Staged rollouts</h3>{rollouts.length===0&&<p>No active or historical rollout.</p>}{rollouts.map(rollout=><p key={rollout.rollout_id}>{rollout.status} — {rollout.percentage}% — policy {rollout.policy_id.slice(0,8)}</p>)}{administrator?.role==="PLATFORM_ADMIN"&&versions.filter(p=>p.status==="PENDING_APPROVAL").map(p=><button key={p.policy_id} onClick={()=>startRollout(p)}>Stage version {p.version_number} at 0%</button>)}</div>
  </section>
}
