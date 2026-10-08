import {AlertTriangle,CalendarClock,RefreshCw,ShieldCheck} from "lucide-react"
import {useEffect,useMemo,useRef,useState} from "react"
import {ErrorState,LoadingState} from "../components/AsyncState"
import {useAuth} from "../context/AuthContext"
import {useToast} from "../context/ToastContext"
import {useDismissableLayer} from "../hooks/useDismissableLayer"
import "../styles/threat-register.css"
const API=import.meta.env.VITE_API_BASE_URL??"/api"
type Risk="LOW"|"MEDIUM"|"HIGH"|"CRITICAL"
type Threat={threat_id:string;title:string;status:string;severity:Risk;asset:string;threat_actor:string;attack_path:string;existing_controls:string[];residual_risk:Risk;test_evidence:string[];incident_response:string;owner:string;review_date:string|null;overdue:boolean}
type Summary={total:number;needs_review:number;critical:number;high_residual_risk:number;overdue:number}
export const riskRank=(risk:Risk)=>({LOW:1,MEDIUM:2,HIGH:3,CRITICAL:4})[risk]
export default function ThreatRegisterPage(){
 const {sessionToken,administrator}=useAuth()
 const {pushToast}=useToast()
 const [items,setItems]=useState<Threat[]>([])
 const [summary,setSummary]=useState<Summary|null>(null)
 const [selected,setSelected]=useState<Threat|null>(null)
 const [filter,setFilter]=useState("ALL")
 const [loading,setLoading]=useState(true)
 const [loadError,setLoadError]=useState("")
 const closeRef=useRef<HTMLButtonElement>(null)
 const dialogRef=useDismissableLayer<HTMLDivElement>({open:!!selected,onClose:()=>setSelected(null),trapFocus:true,initialFocusRef:closeRef,lockBodyScroll:true})
 const headers={"Content-Type":"application/json","X-Admin-Pin":sessionToken??""}
 const load=async()=>{
  setLoading(true);setLoadError("")
  try{const r=await fetch(`${API}/threat-register`,{headers});const body=await r.json();if(!r.ok)throw new Error(body.detail??"Unable to load the threat register.");setItems(body.threats);setSummary(body.summary)}
  catch(error){setLoadError(error instanceof Error?error.message:"Unable to load the threat register.")}
  finally{setLoading(false)}
 }
 useEffect(()=>{void load()},[sessionToken])
 const visible=useMemo(()=>items.filter(item=>filter==="ALL"||item.status===filter),[items,filter])
 const save=async()=>{if(!selected)return;const r=await fetch(`${API}/threat-register/${selected.threat_id}`,{method:"PUT",headers,body:JSON.stringify(selected)});const d=await r.json();pushToast({tone:r.ok?"success":"error",title:r.ok?"Threat review saved":"Review rejected",message:r.ok?"Risk ownership and evidence history were updated.":d.detail});if(r.ok){setSelected(null);await load()}}
 return <main className="threat-page">
  <section className="threat-hero"><div><span><ShieldCheck size={15}/>Security risk governance</span><h1>Threat and vulnerability register</h1><p>Track attack paths, controls, evidence, ownership, residual risk and scheduled review.</p></div><button onClick={()=>void load()}><RefreshCw size={16}/>Refresh</button></section>
  {loading&&<LoadingState label="Loading the threat register" rows={3}/>}
  {!loading&&loadError&&<ErrorState message={loadError} onRetry={()=>void load()}/>}
  {!loading&&!loadError&&<>
  <section className="threat-summary"><article><strong>{summary?.total??0}</strong><span>Registered threats</span></article><article><strong>{summary?.needs_review??0}</strong><span>Need review</span></article><article><strong>{summary?.high_residual_risk??0}</strong><span>High residual risk</span></article><article><strong>{summary?.overdue??0}</strong><span>Overdue reviews</span></article></section>
  <section className="threat-toolbar"><div>{["ALL","NEEDS_REVIEW","OPEN","MONITORED","MITIGATED","ACCEPTED"].map(value=><button className={filter===value?"active":""} onClick={()=>setFilter(value)} key={value}>{value.replaceAll("_"," ")}</button>)}</div><small>{administrator?.role==="PLATFORM_ADMIN"?"Select a threat to review or update it.":"Read-only risk visibility for your role."}</small></section>
  <section className="threat-grid">{visible.map(item=><button className="threat-card" key={item.threat_id} onClick={()=>administrator?.role==="PLATFORM_ADMIN"&&setSelected({...item})}><header><span className={item.severity.toLowerCase()}>{item.severity}</span><b>{item.status.replaceAll("_"," ")}</b></header><h2>{item.title}</h2><p>{item.asset}</p><div><span>Residual <strong>{item.residual_risk}</strong></span><span>Owner <strong>{item.owner}</strong></span></div>{item.overdue&&<small><CalendarClock size={13}/>Review overdue</small>}</button>)}</section>
  {selected&&<div ref={dialogRef} className="threat-modal" role="dialog" aria-modal="true" aria-label="Threat review"><form onSubmit={event=>{event.preventDefault();void save()}}><header><div><span>{selected.threat_id}</span><h2>{selected.title}</h2></div><button ref={closeRef} type="button" onClick={()=>setSelected(null)}>Close</button></header><div className="form-grid"><label>Status<select value={selected.status} onChange={e=>setSelected({...selected,status:e.target.value})}>{["NEEDS_REVIEW","OPEN","MONITORED","MITIGATED","ACCEPTED"].map(v=><option key={v}>{v}</option>)}</select></label><label>Severity<select value={selected.severity} onChange={e=>setSelected({...selected,severity:e.target.value as Risk})}>{["LOW","MEDIUM","HIGH","CRITICAL"].map(v=><option key={v}>{v}</option>)}</select></label><label>Residual risk<select value={selected.residual_risk} onChange={e=>setSelected({...selected,residual_risk:e.target.value as Risk})}>{["LOW","MEDIUM","HIGH","CRITICAL"].map(v=><option key={v}>{v}</option>)}</select></label><label>Review date<input type="date" value={selected.review_date??""} onChange={e=>setSelected({...selected,review_date:e.target.value||null})}/></label></div><label>Asset<input value={selected.asset} onChange={e=>setSelected({...selected,asset:e.target.value})}/></label><label>Threat actor<input value={selected.threat_actor} onChange={e=>setSelected({...selected,threat_actor:e.target.value})}/></label><label>Attack path<textarea value={selected.attack_path} onChange={e=>setSelected({...selected,attack_path:e.target.value})}/></label><label>Existing controls — one per line<textarea value={selected.existing_controls.join("\n")} onChange={e=>setSelected({...selected,existing_controls:e.target.value.split("\n").filter(Boolean)})}/></label><label>Test evidence — one reference per line<textarea value={selected.test_evidence.join("\n")} onChange={e=>setSelected({...selected,test_evidence:e.target.value.split("\n").filter(Boolean)})}/></label><label>Incident response<textarea value={selected.incident_response} onChange={e=>setSelected({...selected,incident_response:e.target.value})}/></label><label>Owner<input value={selected.owner} onChange={e=>setSelected({...selected,owner:e.target.value})}/></label><div className="review-warning"><AlertTriangle size={16}/>Mitigated or accepted risks require controls, test evidence, and a review date.</div><button className="save-review" type="submit">Save reviewed threat</button></form></div>}
  </>}
 </main>
}
