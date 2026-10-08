import {Link2,RefreshCw,ShieldCheck,TicketCheck} from "lucide-react"
import {useEffect,useState} from "react"
import {Navigate} from "react-router-dom"
import {ErrorState,LoadingState} from "../components/AsyncState"
import {useAuth} from "../context/AuthContext"
import {useToast} from "../context/ToastContext"
import "../styles/incident-integrations.css"
const API=import.meta.env.VITE_API_BASE_URL??"/api"
type Destination={destination_id:string;name:string;system_type:string;endpoint:string;credential_reference:string;project_or_table:string;enabled:boolean;credentials_stored:boolean}
type Config={destinations:Destination[];systems:string[];records:Array<{record_id:string;status:string;external_id:string|null}>;approval_links:Array<{link_id:string;request_id:string;expires_at:string;used_at:string|null}>}
export const approvalLinkState=(used:string|null,expires:string)=>used?"USED":new Date(expires)<=new Date()?"EXPIRED":"ACTIVE"
export default function IncidentIntegrationsPage(){
 const {sessionToken,administrator}=useAuth()
 const {pushToast}=useToast()
 const [data,setData]=useState<Config|null>(null)
 const [name,setName]=useState("")
 const [system,setSystem]=useState("JIRA")
 const [endpoint,setEndpoint]=useState("")
 const [reference,setReference]=useState("")
 const [target,setTarget]=useState("")
 const [loading,setLoading]=useState(true)
 const [loadError,setLoadError]=useState("")
 const headers={"Content-Type":"application/json","X-Admin-Pin":sessionToken??""}
 const load=async()=>{
  setLoading(true);setLoadError("")
  try{const r=await fetch(`${API}/incident-integrations`,{headers});const body=await r.json();if(!r.ok)throw new Error(body.detail??"Unable to load incident integrations.");setData(body)}
  catch(error){setLoadError(error instanceof Error?error.message:"Unable to load incident integrations.")}
  finally{setLoading(false)}
 }
 useEffect(()=>{void load()},[sessionToken])
 const save=async()=>{const r=await fetch(`${API}/incident-integrations/destinations`,{method:"POST",headers,body:JSON.stringify({name,system_type:system,endpoint,credential_reference:reference,project_or_table:target,enabled:false})});const d=await r.json();pushToast({tone:r.ok?"success":"error",title:r.ok?"Incident integration registered":"Configuration rejected",message:r.ok?"The integration remains disabled until explicitly reviewed.":d.detail});if(r.ok){setName("");setEndpoint("");setReference("");setTarget("");await load()}}
 if(administrator?.role!=="PLATFORM_ADMIN")return <Navigate to="/dashboard" replace/>
 return <main className="incident-integrations-page">
  <section className="incident-integrations-hero"><div><span>Incident workflow</span><h1>Incident integrations</h1><p>Control Jira, ServiceNow, expiring approval links and signed callbacks.</p></div><button onClick={()=>void load()}><RefreshCw size={17}/>Refresh</button></section>
  <section className="incident-integrations-boundary"><ShieldCheck/><div><strong>Human authority preserved</strong><span>Approval links require an authenticated administrator, expire quickly and work only once.</span></div></section>
  {loading&&<LoadingState label="Loading incident integrations" rows={3}/>}
  {!loading&&loadError&&<ErrorState message={loadError} onRetry={()=>void load()}/>}
  {!loading&&!loadError&&data&&<>
   <section className="incident-integrations-create"><input placeholder="Integration name" value={name} onChange={e=>setName(e.target.value)}/><select value={system} onChange={e=>setSystem(e.target.value)}>{(data.systems.length?data.systems:[system]).map(s=><option key={s}>{s}</option>)}</select><input placeholder="HTTPS endpoint" value={endpoint} onChange={e=>setEndpoint(e.target.value)}/><input placeholder="Credential ENV reference" value={reference} onChange={e=>setReference(e.target.value.toUpperCase())}/><input placeholder={system==="JIRA"?"Project key":"Incident table"} value={target} onChange={e=>setTarget(e.target.value)}/><button onClick={()=>void save()}>Register disabled</button></section>
   <section className="incident-integrations-grid">{data.destinations.map(d=><article key={d.destination_id}><header><TicketCheck/><div><h2>{d.name}</h2><span>{d.system_type}</span></div><b>{d.enabled?"ENABLED":"DISABLED"}</b></header><code>{d.endpoint}</code><dl><div><dt>Target</dt><dd>{d.project_or_table}</dd></div><div><dt>Credential storage</dt><dd>{d.credentials_stored?"Stored":"External reference"}</dd></div></dl></article>)}</section>
   <section className="approval-link-evidence"><header><Link2/><div><h2>Approval-link evidence</h2><span>Tokens are never listed after creation.</span></div></header>{data.approval_links.map(link=><article key={link.link_id}><code>{link.request_id}</code><span>{link.expires_at}</span><b>{approvalLinkState(link.used_at,link.expires_at)}</b></article>)}</section>
  </>}
 </main>
}
