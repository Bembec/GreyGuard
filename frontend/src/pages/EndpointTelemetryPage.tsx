import {Eye,MonitorCheck,Power,RefreshCw,Trash2} from "lucide-react"
import {useEffect,useState} from "react"
import {Navigate} from "react-router-dom"
import {ErrorState,LoadingState} from "../components/AsyncState"
import {useAuth} from "../context/AuthContext"
import {useToast} from "../context/ToastContext"
import "../styles/endpoint-telemetry.css"
const API=import.meta.env.VITE_API_BASE_URL??"/api"
type Collector={collector_id:string;name:string;owner:string;purpose:string;enabled:boolean;visible_indicator:boolean;permissions:string[];approved_directories:string[];retention_days:number;consent_reference:string}
export const telemetryState=(enabled:boolean)=>enabled?"MONITORING":"DISABLED"
export default function EndpointTelemetryPage(){
 const {sessionToken,administrator}=useAuth()
 const {pushToast}=useToast()
 const [collectors,setCollectors]=useState<Collector[]>([])
 const [loading,setLoading]=useState(true)
 const [loadError,setLoadError]=useState("")
 const headers={"Content-Type":"application/json","X-Admin-Pin":sessionToken??""}
 const load=async()=>{
  setLoading(true);setLoadError("")
  try{const r=await fetch(`${API}/endpoint-telemetry`,{headers});const body=await r.json();if(!r.ok)throw new Error(body.detail??"Unable to load endpoint telemetry.");setCollectors(body.collectors)}
  catch(error){setLoadError(error instanceof Error?error.message:"Unable to load endpoint telemetry.")}
  finally{setLoading(false)}
 }
 useEffect(()=>{void load()},[sessionToken])
 const state=async(item:Collector)=>{const r=await fetch(`${API}/endpoint-telemetry/collectors/${item.collector_id}`,{method:"PUT",headers,body:JSON.stringify({enabled:!item.enabled})});const body=await r.json();pushToast({tone:r.ok?"success":"error",title:r.ok?"Collector state updated":"Change blocked",message:r.ok?"The telemetry decision was recorded.":body.detail});if(r.ok)await load()}
 const uninstall=async(item:Collector)=>{const r=await fetch(`${API}/endpoint-telemetry/collectors/${item.collector_id}?confirm=true`,{method:"DELETE",headers});if(r.ok)await load()}
 if(administrator?.role!=="PLATFORM_ADMIN")return <Navigate to="/dashboard" replace/>
 return <main className="endpoint-page">
  <section className="endpoint-hero"><div><span><Eye size={15}/>Visible monitoring only</span><h1>Endpoint telemetry</h1><p>Consent-bound, read-only metadata from explicitly registered GreyGuard endpoints.</p></div><button onClick={()=>void load()}><RefreshCw size={16}/>Refresh</button></section>
  <section className="endpoint-boundary"><MonitorCheck/><div><strong>No payload, credential, screen, microphone or keystroke capture</strong><span>Collectors remain disabled until a Platform Administrator explicitly enables them.</span></div></section>
  {loading&&<LoadingState label="Loading endpoint telemetry" rows={3}/>}
  {!loading&&loadError&&<ErrorState message={loadError} onRetry={()=>void load()}/>}
  {!loading&&!loadError&&
  <section className="collector-list">{collectors.map(item=><article key={item.collector_id}><header><div><h2>{item.name}</h2><span>{item.owner} · consent {item.consent_reference}</span></div><b className={item.enabled?"enabled":"disabled"}>{telemetryState(item.enabled)}</b></header><p>{item.purpose}</p><div className="collector-tags">{item.permissions.map(value=><span key={value}>{value.replaceAll("_"," ")}</span>)}</div><small>{item.retention_days}-day retention · visible indicator {item.visible_indicator?"required":"missing"}</small><footer><button onClick={()=>confirm(`${item.enabled?"Disable":"Enable"} this collector?`)&&void state(item)}><Power size={15}/>{item.enabled?"Disable":"Enable"}</button><button className="danger" onClick={()=>confirm("Disable the collector and begin uninstall/revocation?")&&void uninstall(item)}><Trash2 size={15}/>Uninstall</button></footer></article>)}</section>}
 </main>
}
