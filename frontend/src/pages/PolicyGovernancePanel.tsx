import { useEffect, useState } from "react"
import { useAuth } from "../context/AuthContext"
import "../styles/policy-governance.css"

const API = import.meta.env.VITE_API_BASE_URL ?? "/api"
type Decision = "ALLOW" | "ASK" | "BLOCK"
type Policy = { policy_id:string; version_number:number; status:string; permissions:Record<string,Decision>; risk_weights:Record<string,number>; max_blocked_attempts:number; max_risk_score:number; change_summary:string }

export default function PolicyGovernancePanel() {
  const { sessionToken, administrator } = useAuth()
  const [versions,setVersions]=useState<Policy[]>([])
  const [draft,setDraft]=useState<Policy|null>(null)
  const [message,setMessage]=useState("")
  const headers={"Content-Type":"application/json","x-admin-pin":sessionToken ?? ""}
  const load=async()=>{ if(!sessionToken)return; const r=await fetch(`${API}/policy-versions`,{headers}); const d=await r.json(); if(!r.ok)throw new Error(d.detail); setVersions(d.versions); setDraft(d.versions.find((p:Policy)=>p.status==="DRAFT")??null) }
  useEffect(()=>{load().catch(e=>setMessage(e.message))},[sessionToken])
  const call=async(path:string,method="POST",body?:unknown)=>{const r=await fetch(`${API}${path}`,{method,headers,body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw new Error(d.detail);setMessage("Change completed successfully.");await load();return d}
  const published=versions.find(p=>p.status==="PUBLISHED")
  const create=()=>published&&call("/policy-versions/drafts","POST",{permissions:published.permissions,risk_weights:published.risk_weights,max_blocked_attempts:published.max_blocked_attempts,max_risk_score:published.max_risk_score,change_summary:"New controlled policy revision"})
  const save=()=>draft&&call(`/policy-versions/${draft.policy_id}/draft`,"PUT",draft)
  const updateDecision=(action:string,value:Decision)=>setDraft(d=>d?{...d,permissions:{...d.permissions,[action]:value}}:d)
  if(!sessionToken)return null
  return <section className="policy-governance">
    <header><div><span>Change control</span><h2>Policy versions and approvals</h2></div>{!draft&&administrator?.role!=="AUDITOR"&&<button onClick={create}>Create draft</button>}</header>
    {message&&<p className="governance-message">{message}</p>}
    {draft&&<div className="governance-editor">
      <div className="governance-fields"><label>Change summary<input value={draft.change_summary} onChange={e=>setDraft({...draft,change_summary:e.target.value})}/></label><label>Risk threshold<input type="number" value={draft.max_risk_score} onChange={e=>setDraft({...draft,max_risk_score:Number(e.target.value)})}/></label><label>Blocked attempts<input type="number" value={draft.max_blocked_attempts} onChange={e=>setDraft({...draft,max_blocked_attempts:Number(e.target.value)})}/></label></div>
      <div className="governance-rules">{Object.keys(draft.permissions).sort().map(action=><div key={action}><code>{action}</code><select value={draft.permissions[action]} onChange={e=>updateDecision(action,e.target.value as Decision)}><option>ALLOW</option><option>ASK</option><option>BLOCK</option></select><input type="number" min="0" max="100" value={draft.risk_weights[action]} onChange={e=>setDraft({...draft,risk_weights:{...draft.risk_weights,[action]:Number(e.target.value)}})}/></div>)}</div>
      <div className="governance-actions"><button onClick={save}>Save draft</button><button className="primary" onClick={()=>call(`/policy-versions/${draft.policy_id}/submit`)}>Submit for approval</button></div>
    </div>}
    <div className="version-list">{versions.map(p=><article key={p.policy_id}><div><strong>Version {p.version_number}</strong><span className={`status ${p.status.toLowerCase()}`}>{p.status.replaceAll("_"," ")}</span><p>{p.change_summary}</p></div><div className="version-actions">{p.status==="PENDING_APPROVAL"&&administrator?.role==="PLATFORM_ADMIN"&&<><button onClick={()=>call(`/policy-versions/${p.policy_id}/approve`)}>Approve</button><button onClick={()=>call(`/policy-versions/${p.policy_id}/reject?note=Rejected%20by%20reviewer`)}>Reject</button></>}{p.status==="ARCHIVED"&&administrator?.role==="PLATFORM_ADMIN"&&<button onClick={()=>call(`/policy-versions/${p.policy_id}/rollback`)}>Rollback draft</button>}</div></article>)}</div>
  </section>
}
