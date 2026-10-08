import {Boxes,RefreshCw,ShieldOff,Trash2,Upload} from "lucide-react"
import {useEffect,useRef,useState,type ChangeEvent} from "react"
import {Navigate} from "react-router-dom"
import {ErrorState,LoadingState} from "../components/AsyncState"
import {useAuth} from "../context/AuthContext"
import {useToast} from "../context/ToastContext"
import "../styles/isolation-operations.css"
const API=import.meta.env.VITE_API_BASE_URL??"/api"
type Workspace={workspace_id:string;agent_name:string;status:string;created_at:string;destroyed_at:string|null}
type Data={config:{global_kill_switch:boolean;network_enabled:boolean;destination_allowlist:string[];dns_allowlist:string[]};workspaces:Workspace[];artifacts:Array<{artifact_id:string;original_name:string;status:string;sha256:string;scan_engine:string|null;scan_result:string|null}>}
export const workspaceState=(status:string)=>status==="ACTIVE"?"ACTIVE":"DESTROYED"
function readFileAsBase64(file:File):Promise<string>{return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>{const result=String(reader.result);resolve(result.slice(result.indexOf(",")+1))};reader.onerror=()=>reject(reader.error);reader.readAsDataURL(file)})}
export default function IsolationOperationsPage(){
 const {sessionToken,administrator}=useAuth()
 const {pushToast}=useToast()
 const [data,setData]=useState<Data|null>(null)
 const [agent,setAgent]=useState("")
 const [uploadTarget,setUploadTarget]=useState<string|null>(null)
 const [loading,setLoading]=useState(true)
 const [loadError,setLoadError]=useState("")
 const fileInput=useRef<HTMLInputElement|null>(null)
 const headers={"Content-Type":"application/json","X-Admin-Pin":sessionToken??""}
 const load=async()=>{
  setLoading(true);setLoadError("")
  try{const r=await fetch(`${API}/isolation-operations`,{headers});const body=await r.json();if(!r.ok)throw new Error(body.detail??"Unable to load isolation operations.");setData(body)}
  catch(error){setLoadError(error instanceof Error?error.message:"Unable to load isolation operations.")}
  finally{setLoading(false)}
 }
 useEffect(()=>{void load()},[sessionToken])
 const call=async(path:string,method="POST",body?:unknown)=>{const r=await fetch(`${API}${path}`,{method,headers,body:body?JSON.stringify(body):undefined});const d=await r.json();pushToast({tone:r.ok?"success":"error",title:r.ok?"Isolation operation completed":"Operation blocked",message:r.ok?"The operation and evidence were recorded.":d.detail});if(r.ok){setAgent("");await load()}}
 const startUpload=(workspaceId:string)=>{setUploadTarget(workspaceId);fileInput.current?.click()}
 const handleFileChosen=async(event:ChangeEvent<HTMLInputElement>)=>{const file=event.target.files?.[0];const workspaceId=uploadTarget;event.target.value="";setUploadTarget(null);if(!file||!workspaceId)return;const content_base64=await readFileAsBase64(file);await call(`/isolation-operations/workspaces/${workspaceId}/artifacts`,"POST",{filename:file.name,content_base64})}
 if(administrator?.role!=="PLATFORM_ADMIN")return <Navigate to="/dashboard" replace/>
 return <main className="isolation-operations-page">
  <input ref={fileInput} type="file" style={{display:"none"}} onChange={e=>void handleFileChosen(e)}/>
  <section className="isolation-operations-hero"><div><span>Workspace containment</span><h1>Isolation operations</h1><p>Per-agent workspaces, quarantine, network boundaries and Kubernetes job isolation.</p></div><button onClick={()=>void load()}><RefreshCw size={17}/>Refresh</button></section>
  {loading&&<LoadingState label="Loading isolation operations" rows={3}/>}
  {!loading&&loadError&&<ErrorState message={loadError} onRetry={()=>void load()}/>}
  {!loading&&!loadError&&data&&<>
   <section className={`kill-switch ${data.config.global_kill_switch?"active":""}`}><ShieldOff/><div><strong>Global execution kill switch</strong><span>{data.config.global_kill_switch?"All new workspaces and isolated jobs are blocked.":"Execution admission is available under configured controls."}</span></div><button onClick={()=>confirm("Change the global execution kill switch?")&&void call("/isolation-operations","PUT",{...data.config,global_kill_switch:!data.config.global_kill_switch})}>{data.config.global_kill_switch?"Restore admission":"Activate kill switch"}</button></section>
   <section className="workspace-create"><input placeholder="Registered agent name" value={agent} onChange={e=>setAgent(e.target.value)}/><button onClick={()=>void call("/isolation-operations/workspaces","POST",{agent_name:agent})}>Create isolated workspace</button></section>
   <section className="operations-grid"><article><header><Boxes/><div><h2>Agent workspaces</h2><span>Destroyed after controlled execution</span></div></header>{data.workspaces.map(w=><div className="operation-row" key={w.workspace_id}><span><strong>{w.agent_name}</strong><small>{w.workspace_id}</small></span><b>{workspaceState(w.status)}</b>{w.status==="ACTIVE"&&<><button title="Quarantine an artifact for scanning" onClick={()=>startUpload(w.workspace_id)}><Upload size={14}/></button><button onClick={()=>confirm(`Destroy ${w.agent_name}'s workspace?`)&&void call(`/isolation-operations/workspaces/${w.workspace_id}`,"DELETE")}><Trash2 size={14}/></button></>}</div>)}</article><article><header><ShieldOff/><div><h2>Quarantined artifacts</h2><span>Never released before scanning &mdash; malware scanning must be explicitly enabled (GREYGUARD_MALWARE_SCANNING_ENABLED)</span></div></header>{data.artifacts.map(a=><div className="operation-row" key={a.artifact_id}><span><strong>{a.original_name}</strong><small>{a.sha256.slice(0,16)}&hellip;{a.scan_result?` · ${a.scan_result}`:""}</small></span><b>{a.status}</b>{a.status==="QUARANTINED"&&<button onClick={()=>void call(`/isolation-operations/artifacts/${a.artifact_id}/scan`,"POST")}>Scan</button>}</div>)}</article></section>
  </>}
 </main>
}
