import {Ban,FlaskConical,Play,RefreshCw,ShieldAlert} from "lucide-react"
import {useEffect,useState} from "react"
import {Navigate} from "react-router-dom"
import {ErrorState,LoadingState} from "../components/AsyncState"
import {useAuth} from "../context/AuthContext"
import {useToast} from "../context/ToastContext"
import "../styles/simulations.css"
const API=import.meta.env.VITE_API_BASE_URL??"/api"
type Scenario={scenario_id:string;title:string;attempt:string;decision:string;severity:string;risk_added:number;fictional_target:string;operational:boolean}
type Run=Scenario&{run_id:string;simulated:boolean;real_action_executed:boolean;environment_reset:boolean;created_at:string}
type Data={enabled:boolean;simulation_only:boolean;network_access:boolean;scenarios:Scenario[];runs:Run[]}
export const simulationBanner=(simulated:boolean)=>simulated?"SIMULATION ONLY — NO REAL ACTION":"INVALID RECORD"
export default function SimulationsPage(){
 const {sessionToken,administrator}=useAuth()
 const {pushToast}=useToast()
 const [data,setData]=useState<Data|null>(null)
 const [loading,setLoading]=useState(true)
 const [loadError,setLoadError]=useState("")
 const headers={"Content-Type":"application/json","X-Admin-Pin":sessionToken??""}
 const load=async()=>{
  setLoading(true);setLoadError("")
  try{const r=await fetch(`${API}/simulations`,{headers});const body=await r.json();if(!r.ok)throw new Error(body.detail??"Unable to load the simulation lab.");setData(body)}
  catch(error){setLoadError(error instanceof Error?error.message:"Unable to load the simulation lab.")}
  finally{setLoading(false)}
 }
 useEffect(()=>{void load()},[sessionToken])
 const state=async()=>{const r=await fetch(`${API}/simulations`,{method:"PUT",headers,body:JSON.stringify({enabled:!data?.enabled})});if(r.ok)await load()}
 const run=async(id:string)=>{const r=await fetch(`${API}/simulations/run`,{method:"POST",headers,body:JSON.stringify({scenario_id:id})});const body=await r.json();pushToast({tone:r.ok?"success":"error",title:r.ok?"Safe simulation completed":"Simulation blocked",message:r.ok?"No real action executed; defensive evidence was preserved.":body.detail});if(r.ok)await load()}
 if(administrator?.role!=="PLATFORM_ADMIN")return <Navigate to="/dashboard" replace/>
 return <main className="simulation-page">
  {loading&&<LoadingState label="Loading the simulation lab" rows={3}/>}
  {!loading&&loadError&&<ErrorState message={loadError} onRetry={()=>void load()}/>}
  {!loading&&!loadError&&data&&<>
   <section className="simulation-banner"><FlaskConical/><div><strong>SIMULATION ONLY — NO REAL ACTION</strong><span>Fictional targets, predefined outputs, zero filesystem, process or network side effects.</span></div><button onClick={()=>confirm("Change the simulation lab state?")&&void state()}>{data.enabled?"Disable lab":"Enable lab"}</button></section>
   <section className="simulation-hero"><div><span><Ban size={15}/>Prohibited-capability register</span><h1>Adversarial simulation lab</h1><p>Validate how GreyGuard detects, refuses, alerts and preserves evidence.</p></div><button onClick={()=>void load()}><RefreshCw size={16}/>Refresh</button></section>
   <section className="scenario-grid">{data.scenarios.map(item=><article key={item.scenario_id}><header><ShieldAlert/><b>{item.severity}</b></header><h2>{item.title}</h2><p>{item.attempt} · {item.fictional_target}</p><div><span>{item.decision}</span><span>+{item.risk_added} risk</span></div><button disabled={!data.enabled} onClick={()=>void run(item.scenario_id)}><Play size={15}/>Run predefined simulation</button></article>)}</section>
   {data.runs.length?<section className="simulation-history"><h2>Simulation evidence</h2>{data.runs.map(item=><div key={item.run_id}><span><strong>{item.title}</strong><small>{new Date(item.created_at).toLocaleString()}</small></span><b>{simulationBanner(item.simulated)}</b></div>)}</section>:null}
  </>}
 </main>
}
