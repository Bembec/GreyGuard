import {Box,RefreshCw,ShieldCheck,Square} from "lucide-react"
import {useEffect,useState} from "react"
import {Navigate} from "react-router-dom"
import {ErrorState,LoadingState} from "../components/AsyncState"
import {useAuth} from "../context/AuthContext"
import {useToast} from "../context/ToastContext"
import "../styles/execution-isolation.css"
const API=import.meta.env.VITE_API_BASE_URL??"/api"
type Config={enabled:boolean;image:string;cpu_limit:number;memory_mb:number;pids_limit:number;timeout_seconds:number;network_mode:string;read_only:boolean;non_root:boolean;capabilities_dropped:string;arbitrary_commands_allowed:boolean}
type Data={config:Config;history:Array<{execution_id:string;job_type:string;status:string;created_at:string;result:string|null}>}
export const isolationState=(enabled:boolean)=>enabled?"ENABLED":"DISABLED"
export default function ExecutionIsolationPage(){
 const {sessionToken,administrator}=useAuth()
 const {pushToast}=useToast()
 const [data,setData]=useState<Data|null>(null)
 const [loading,setLoading]=useState(true)
 const [loadError,setLoadError]=useState("")
 const headers={"Content-Type":"application/json","X-Admin-Pin":sessionToken??""}
 const load=async()=>{
  setLoading(true);setLoadError("")
  try{const r=await fetch(`${API}/execution-isolation`,{headers});const body=await r.json();if(!r.ok)throw new Error(body.detail??"Unable to load execution isolation controls.");setData(body)}
  catch(error){setLoadError(error instanceof Error?error.message:"Unable to load execution isolation controls.")}
  finally{setLoading(false)}
 }
 useEffect(()=>{void load()},[sessionToken])
 const call=async(path:string,method="POST",body?:unknown)=>{const r=await fetch(`${API}${path}`,{method,headers,body:body?JSON.stringify(body):undefined});const d=await r.json();pushToast({tone:r.ok?"success":"error",title:r.ok?"Isolation control updated":"Operation blocked",message:r.ok?"Execution evidence has been recorded.":d.detail});await load()}
 if(administrator?.role!=="PLATFORM_ADMIN")return <Navigate to="/dashboard" replace/>
 const c=data?.config
 return <main className="isolation-page">
  <section className="isolation-hero"><div><span>Controlled execution</span><h1>Execution isolation</h1><p>Hardened, predefined Docker jobs with network access disabled by default.</p></div><button onClick={()=>void load()}><RefreshCw size={17}/>Refresh</button></section>
  <section className="isolation-boundary"><ShieldCheck/><div><strong>No arbitrary commands</strong><span>Only predefined jobs may run; the container receives no host Docker socket, privileges or network access.</span></div></section>
  {loading&&<LoadingState label="Loading execution isolation controls" rows={3}/>}
  {!loading&&loadError&&<ErrorState message={loadError} onRetry={()=>void load()}/>}
  {!loading&&!loadError&&data&&c&&<>
   <section className="isolation-status"><article><Box/><strong>{isolationState(c.enabled)}</strong><span>Sandbox execution</span></article><article><ShieldCheck/><strong>{c.network_mode.toUpperCase()}</strong><span>Network mode</span></article><article><Square/><strong>{c.memory_mb} MB / {c.cpu_limit} CPU</strong><span>Resource ceiling</span></article></section>
   <section className="isolation-controls"><article><h2>Enforced boundary</h2><dl><div><dt>Image</dt><dd>{c.image}</dd></div><div><dt>Non-root</dt><dd>{String(c.non_root)}</dd></div><div><dt>Read-only root</dt><dd>{String(c.read_only)}</dd></div><div><dt>Capabilities</dt><dd>{c.capabilities_dropped}</dd></div><div><dt>Process limit</dt><dd>{c.pids_limit}</dd></div><div><dt>Timeout</dt><dd>{c.timeout_seconds}s</dd></div></dl></article><article><h2>Administrative actions</h2><p>The sandbox remains disabled until the image and Docker security profile are verified.</p>{!c.enabled&&<button onClick={()=>confirm("Enable predefined Docker sandbox jobs?")&&void call("/execution-isolation","PUT",{...c,enabled:true})}>Enable sandbox</button>}<button className="danger" onClick={()=>confirm("Terminate all active isolated jobs?")&&void call("/execution-isolation/emergency-terminate")}>Emergency terminate</button></article></section>
   <section className="isolation-history"><h2>Execution evidence</h2>{data.history.map(item=><article key={item.execution_id}><code>{item.execution_id}</code><span>{item.job_type}</span><b>{item.status}</b></article>)}</section>
  </>}
 </main>
}
