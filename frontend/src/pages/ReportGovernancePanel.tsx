import {CalendarClock,FileSignature,ShieldCheck,Trash2} from "lucide-react"
import {useEffect,useState} from "react"
import {ErrorState,LoadingState} from "../components/AsyncState"
import {useAuth} from "../context/AuthContext"
import {useToast} from "../context/ToastContext"
import "../styles/report-governance.css"
const API=import.meta.env.VITE_API_BASE_URL??"/api"
type Schedule={schedule_id:string;title:string;frequency:string;enabled:boolean;next_run_at:string}
type Mapping={framework:string;control:string;evidence:string}
type Overview={schedules:Schedule[];control_mapping:Mapping[];retention:{data_sets:Array<{data_set:string;records:number}>}}
export const scheduleState=(enabled:boolean)=>enabled?"ACTIVE":"DISABLED"
export default function ReportGovernancePanel(){
 const {sessionToken,administrator}=useAuth()
 const {pushToast}=useToast()
 const [data,setData]=useState<Overview|null>(null)
 const [title,setTitle]=useState("Weekly security evidence")
 const [nextRun,setNextRun]=useState("")
 const [loading,setLoading]=useState(true)
 const [loadError,setLoadError]=useState("")
 const headers={"Content-Type":"application/json","X-Admin-Pin":sessionToken??""}
 const load=async()=>{
  setLoading(true);setLoadError("")
  try{const r=await fetch(`${API}/report-governance`,{headers});const body=await r.json();if(!r.ok)throw new Error(body.detail??"Unable to load report governance.");setData(body)}
  catch(error){setLoadError(error instanceof Error?error.message:"Unable to load report governance.")}
  finally{setLoading(false)}
 }
 useEffect(()=>{void load()},[sessionToken])
 const schedule=async()=>{const r=await fetch(`${API}/report-governance/schedules`,{method:"POST",headers,body:JSON.stringify({title,frequency:"WEEKLY",next_run_at:new Date(nextRun).toISOString()})});const body=await r.json();pushToast({tone:r.ok?"success":"error",title:r.ok?"Report scheduled":"Schedule rejected",message:r.ok?"The report schedule is active.":body.detail});if(r.ok)await load()}
 const disable=async(id:string)=>{const r=await fetch(`${API}/report-governance/schedules/${id}`,{method:"DELETE",headers});if(r.ok)await load()}
 return <section className="report-governance">
  <header><div><FileSignature/><span><strong>Report governance</strong><small>Signed evidence, scheduling and control mappings</small></span></div></header>
  {administrator?.role==="PLATFORM_ADMIN"&&<div className="schedule-create"><input value={title} onChange={e=>setTitle(e.target.value)} aria-label="Schedule title"/><input type="datetime-local" value={nextRun} onChange={e=>setNextRun(e.target.value)} aria-label="Next run"/><button disabled={!nextRun} onClick={()=>void schedule()}><CalendarClock size={16}/>Schedule weekly</button></div>}
  {loading&&<LoadingState label="Loading report governance" rows={3}/>}
  {!loading&&loadError&&<ErrorState message={loadError} onRetry={()=>void load()}/>}
  {!loading&&!loadError&&data&&<div className="governance-columns"><article><h3>Scheduled reports</h3>{data.schedules.map(item=><div className="governance-row" key={item.schedule_id}><span><strong>{item.title}</strong><small>{item.frequency} · {new Date(item.next_run_at).toLocaleString()}</small></span><b>{scheduleState(item.enabled)}</b>{item.enabled&&administrator?.role==="PLATFORM_ADMIN"&&<button onClick={()=>confirm("Disable this report schedule?")&&void disable(item.schedule_id)}><Trash2 size={14}/></button>}</div>)}</article><article><h3><ShieldCheck size={17}/>Compliance mappings</h3>{data.control_mapping.map(item=><div className="mapping-row" key={`${item.framework}-${item.control}`}><strong>{item.framework} · {item.control}</strong><span>{item.evidence}</span></div>)}</article></div>}
 </section>
}
