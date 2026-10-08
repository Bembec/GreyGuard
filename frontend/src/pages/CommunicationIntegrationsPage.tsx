import {BellRing,RefreshCw,ShieldCheck} from "lucide-react"
import {useEffect,useState} from "react"
import {Navigate} from "react-router-dom"
import {ErrorState,LoadingState} from "../components/AsyncState"
import {useAuth} from "../context/AuthContext"
import {useToast} from "../context/ToastContext"
import "../styles/communication-integrations.css"
const API=import.meta.env.VITE_API_BASE_URL??"/api"
type Destination={destination_id:string;name:string;channel:string;endpoint_reference:string;enabled:boolean;minimum_severity:string;quiet_start_hour:number|null;quiet_end_hour:number|null;critical_bypass:boolean;escalation_minutes:number;credentials_stored:boolean}
type Config={destinations:Destination[];channels:string[];templates:unknown[];recent_deliveries:Array<{delivery_id:string;status:string;subject:string;attempts:number}>}
export const deliveryState=(enabled:boolean)=>enabled?"ENABLED":"DISABLED"
export default function CommunicationIntegrationsPage(){
 const {sessionToken,administrator}=useAuth()
 const {pushToast}=useToast()
 const [data,setData]=useState<Config|null>(null)
 const [name,setName]=useState("")
 const [channel,setChannel]=useState("EMAIL")
 const [reference,setReference]=useState("")
 const [loading,setLoading]=useState(true)
 const [loadError,setLoadError]=useState("")
 const headers={"Content-Type":"application/json","X-Admin-Pin":sessionToken??""}
 const load=async()=>{
  setLoading(true);setLoadError("")
  try{const r=await fetch(`${API}/notification-delivery`,{headers});const body=await r.json();if(!r.ok)throw new Error(body.detail??"Unable to load communication integrations.");setData(body)}
  catch(error){setLoadError(error instanceof Error?error.message:"Unable to load communication integrations.")}
  finally{setLoading(false)}
 }
 useEffect(()=>{void load()},[sessionToken])
 const save=async()=>{const r=await fetch(`${API}/notification-delivery/destinations`,{method:"POST",headers,body:JSON.stringify({name,channel,endpoint_reference:reference,enabled:false,minimum_severity:"HIGH",quiet_start_hour:22,quiet_end_hour:7,critical_bypass:true,escalation_minutes:15})});const d=await r.json();pushToast({tone:r.ok?"success":"error",title:r.ok?"Destination registered disabled":"Configuration rejected",message:r.ok?"Enable only after the external credential and recipient are verified.":d.detail});if(r.ok){setName("");setReference("");await load()}}
 if(administrator?.role!=="PLATFORM_ADMIN")return <Navigate to="/dashboard" replace/>
 return <main className="communications-page">
  <section className="communications-hero"><div><span>Incident communication</span><h1>Communication integrations</h1><p>Control external security notifications, quiet hours, escalation and delivery evidence.</p></div><button onClick={()=>void load()}><RefreshCw size={17}/>Refresh</button></section>
  <section className="communications-boundary"><ShieldCheck/><div><strong>Disabled by default</strong><span>Credentials remain external and destinations must be explicitly enabled after recipient verification.</span></div></section>
  {loading&&<LoadingState label="Loading communication integrations" rows={3}/>}
  {!loading&&loadError&&<ErrorState message={loadError} onRetry={()=>void load()}/>}
  {!loading&&!loadError&&data&&<>
   <section className="communications-create"><input placeholder="Destination name" value={name} onChange={e=>setName(e.target.value)}/><select value={channel} onChange={e=>setChannel(e.target.value)}>{(data.channels.length?data.channels:[channel]).map(c=><option key={c}>{c}</option>)}</select><input placeholder="External credential or endpoint ENV reference" value={reference} onChange={e=>setReference(e.target.value.toUpperCase())}/><button onClick={()=>void save()}>Register disabled</button></section>
   <section className="communications-grid">{data.destinations.map(d=><article key={d.destination_id}><header><BellRing/><div><h2>{d.name}</h2><span>{d.channel}</span></div><b>{deliveryState(d.enabled)}</b></header><code>{d.endpoint_reference}</code><dl><div><dt>Minimum</dt><dd>{d.minimum_severity}</dd></div><div><dt>Quiet hours</dt><dd>{d.quiet_start_hour??"–"}:00–{d.quiet_end_hour??"–"}:00</dd></div><div><dt>Escalation</dt><dd>{d.escalation_minutes} minutes</dd></div><div><dt>Credentials stored</dt><dd>{d.credentials_stored?"Yes":"No"}</dd></div></dl></article>)}</section>
  </>}
 </main>
}
