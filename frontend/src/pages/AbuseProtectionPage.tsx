import { Activity, AlertTriangle, Ban, Gauge, LockKeyhole, RefreshCw, Save, ShieldAlert, Waves } from "lucide-react"
import { useEffect, useState } from "react"
import { Navigate } from "react-router-dom"
import { ErrorState, LoadingState } from "../components/AsyncState"
import { useAuth } from "../context/AuthContext"
import "../styles/abuse-protection.css"

export type RateLimitPolicy = { category:string;enabled:boolean;request_limit:number;window_seconds:number;block_seconds:number;max_failed_attempts:number;updated_at:string;updated_by:string }
type AbuseEvent = { event_id:string;timestamp:string;category:string;event_type:string;severity:string;identifier_hint:string;request_count:number;detail:string }
type Overview = { summary:{events:number;quota_blocks:number;auth_lockouts:number;bursts:number;active_blocks:number};policies:RateLimitPolicy[];events:AbuseEvent[] }
const API=import.meta.env.VITE_API_BASE_URL??"/api"
export function formatProtectionCategory(category:string){return category.toLowerCase().replaceAll("_"," ").replace(/(^|\s)\S/g,value=>value.toUpperCase())}

export default function AbuseProtectionPage(){
 const {sessionToken,administrator}=useAuth()
 const [data,setData]=useState<Overview|null>(null);const [drafts,setDrafts]=useState<Record<string,RateLimitPolicy>>({});const [message,setMessage]=useState("");const [busy,setBusy]=useState("");const [loading,setLoading]=useState(true);const [loadError,setLoadError]=useState("");const headers={"Content-Type":"application/json","X-Admin-Pin":sessionToken??""}
 const load=async()=>{
  setLoading(true);setLoadError("")
  try{const response=await fetch(`${API}/abuse-protection`,{headers});const body=await response.json();if(!response.ok)throw new Error(body.detail??"Unable to load abuse protection.");const overview=body as Overview;setData(overview);setDrafts(Object.fromEntries(overview.policies.map(policy=>[policy.category,{...policy}])))}
  catch(error){setLoadError(error instanceof Error?error.message:"Unable to load abuse protection.")}
  finally{setLoading(false)}
 }
 useEffect(()=>{void load()},[sessionToken])
 const updateDraft=(category:string,field:keyof RateLimitPolicy,value:number|boolean)=>setDrafts(current=>({...current,[category]:{...current[category],[field]:value}}))
 const save=async(policy:RateLimitPolicy)=>{setBusy(policy.category);setMessage("");try{const response=await fetch(`${API}/abuse-protection/policies/${policy.category}`,{method:"PUT",headers,body:JSON.stringify({enabled:policy.enabled,request_limit:policy.request_limit,window_seconds:policy.window_seconds,block_seconds:policy.block_seconds,max_failed_attempts:policy.max_failed_attempts})});const body=await response.json();if(!response.ok)throw new Error(body.detail??"Policy update failed.");setMessage(`${formatProtectionCategory(policy.category)} protection policy updated.`);await load()}catch(error){setMessage(error instanceof Error?error.message:"Request failed.")}finally{setBusy("")}}
 const summary=data?.summary
 // GET /abuse-protection itself calls require_install_operator() server-side (backend/app/api.py)
 // - this is not merely a mutation-gated page, the entire resource is install-operator-only, so a
 // page-level redirect (not a partial read-only render) is the correct gate.
 if(!administrator?.install_operator)return <Navigate to="/dashboard" replace/>
 return <main className="abuse-page"><section className="abuse-hero"><div><p><ShieldAlert size={15}/> Defensive controls</p><h1>Abuse Protection</h1><span>Throttle excessive traffic, lock repeated failures, and preserve suspicious burst evidence.</span></div><button onClick={()=>void load()}><RefreshCw size={17}/> Refresh</button></section>
 {message&&<p className="abuse-message">{message}</p>}
 {loading&&<LoadingState label="Loading abuse protection" rows={3}/>}
 {!loading&&loadError&&<ErrorState message={loadError} onRetry={()=>void load()}/>}
 {!loading&&!loadError&&data&&<>
 <section className="abuse-metrics"><article><Ban/><div><strong>{summary?.active_blocks??0}</strong><span>Active blocks</span></div></article><article><Gauge/><div><strong>{summary?.quota_blocks??0}</strong><span>Quota blocks</span></div></article><article><LockKeyhole/><div><strong>{summary?.auth_lockouts??0}</strong><span>Auth lockouts</span></div></article><article><Waves/><div><strong>{summary?.bursts??0}</strong><span>Burst warnings</span></div></article></section>
 <section className="protection-section"><header><div><Gauge/><span><strong>Protection policies</strong><small>Changes take effect immediately</small></span></div></header><div className="policy-grid">{Object.values(drafts).map(policy=><article key={policy.category}><div className="policy-title"><div><strong>{formatProtectionCategory(policy.category)}</strong><small>{policy.category}</small></div><label className="switch"><input type="checkbox" checked={policy.enabled} onChange={event=>updateDraft(policy.category,"enabled",event.target.checked)}/><span/></label></div><div className="policy-fields"><label>Request limit<input type="number" min="1" max="10000" value={policy.request_limit} onChange={event=>updateDraft(policy.category,"request_limit",Number(event.target.value))}/></label><label>Window (seconds)<input type="number" min="1" value={policy.window_seconds} onChange={event=>updateDraft(policy.category,"window_seconds",Number(event.target.value))}/></label><label>Block (seconds)<input type="number" min="1" value={policy.block_seconds} onChange={event=>updateDraft(policy.category,"block_seconds",Number(event.target.value))}/></label><label>Failed attempts<input type="number" min="1" max="100" value={policy.max_failed_attempts} onChange={event=>updateDraft(policy.category,"max_failed_attempts",Number(event.target.value))}/></label></div><footer><small>Updated by {policy.updated_by}</small><button disabled={busy===policy.category} onClick={()=>void save(policy)}><Save size={15}/> Save policy</button></footer></article>)}</div></section>
 <section className="protection-section"><header><div><Activity/><span><strong>Abuse evidence</strong><small>{data.events.length} recent defensive events</small></span></div></header>{!data.events.length&&<div className="abuse-empty"><ShieldAlert size={30}/><strong>No abuse events recorded</strong><span>GreyGuard has not detected a quota violation, lockout, or suspicious burst.</span></div>}<div className="abuse-events">{data.events.map(event=><article key={event.event_id}><span className={`event-icon ${event.severity.toLowerCase()}`}>{event.severity==="HIGH"?<AlertTriangle/>:<Waves/>}</span><div><strong>{formatProtectionCategory(event.event_type)}</strong><p>{event.detail}</p><small>{event.category} · {event.identifier_hint} · {event.request_count} requests</small></div><time>{new Date(event.timestamp).toLocaleString()}</time></article>)}</div></section>
 </>}
 </main>
}
