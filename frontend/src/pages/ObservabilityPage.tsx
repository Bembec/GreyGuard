import { Activity, Braces, RefreshCw, Save, ShieldCheck, Waypoints } from "lucide-react"
import { useEffect, useState } from "react"
import { Navigate } from "react-router-dom"
import { ErrorState, LoadingState } from "../components/AsyncState"
import { useAuth } from "../context/AuthContext"
import "../styles/observability.css"

export type ObservabilityConfig={tracing_enabled:boolean;metrics_enabled:boolean;structured_logs_enabled:boolean;sample_rate:number;retention_limit:number;updated_at:string;updated_by:string}
const API=import.meta.env.VITE_API_BASE_URL??"/api"
export const samplingPercent=(rate:number)=>`${Math.round(rate*100)}%`

export default function ObservabilityPage(){
 const {sessionToken,administrator}=useAuth();const [config,setConfig]=useState<ObservabilityConfig|null>(null);const [metrics,setMetrics]=useState("");const [message,setMessage]=useState("");const [busy,setBusy]=useState(false);const [loading,setLoading]=useState(true);const [loadError,setLoadError]=useState("");const headers={"Content-Type":"application/json","X-Admin-Pin":sessionToken??""}
 const load=async()=>{
  setLoading(true);setLoadError("")
  try{const [configuration,metricResponse]=await Promise.all([fetch(`${API}/observability/config`,{headers}),fetch(`${API}/observability/metrics`,{headers})]);const body=await configuration.json();if(!configuration.ok)throw new Error(body.detail??"Unable to load observability controls.");setConfig(body);setMetrics(metricResponse.ok?await metricResponse.text():"Metrics unavailable.")}
  catch(error){setLoadError(error instanceof Error?error.message:"Unable to load observability controls.")}
  finally{setLoading(false)}
 }
 useEffect(()=>{void load()},[sessionToken])
 const save=async()=>{if(!config)return;setBusy(true);try{const response=await fetch(`${API}/observability/config`,{method:"PUT",headers,body:JSON.stringify(config)});const body=await response.json();if(!response.ok)throw new Error(body.detail??"Observability update failed.");setConfig(body);setMessage("Observability controls updated.")}catch(error){setMessage(error instanceof Error?error.message:"Request failed.")}finally{setBusy(false)}}
 const exportTraces=async()=>{const response=await fetch(`${API}/observability/traces`,{headers});const body=await response.json();if(!response.ok){setMessage(body.detail??"Trace export failed.");return}const url=URL.createObjectURL(new Blob([JSON.stringify(body,null,2)],{type:"application/json"}));const link=document.createElement("a");link.href=url;link.download="greyguard-otlp-traces.json";link.click();URL.revokeObjectURL(url)}
 if(administrator?.role!=="PLATFORM_ADMIN")return <Navigate to="/dashboard" replace/>
 return <main className="observability-page"><section className="observability-hero"><div><p><Waypoints size={15}/> Telemetry governance</p><h1>Observability</h1><span>Control trace sampling, Prometheus metrics, structured logs, and redacted OTLP evidence.</span></div><button onClick={()=>void load()}><RefreshCw size={17}/> Refresh</button></section>{message&&<p className="observability-message">{message}</p>}
 <section className="telemetry-boundary"><ShieldCheck/><div><strong>Redaction before export</strong><span>Credentials, tokens, secrets, passwords, authorization values and PINs are removed before telemetry is stored or exported.</span></div></section>
 {loading&&<LoadingState label="Loading observability controls" rows={3}/>}
 {!loading&&loadError&&<ErrorState message={loadError} onRetry={()=>void load()}/>}
 {!loading&&!loadError&&config&&<section className="observability-grid"><article><header><Activity/><div><strong>Collection controls</strong><small>Changes apply to new requests</small></div></header>{([['tracing_enabled','OpenTelemetry traces'],['metrics_enabled','Prometheus metrics'],['structured_logs_enabled','Structured JSON logs']] as const).map(([key,label])=><label className="telemetry-toggle" key={key}><span>{label}</span><input type="checkbox" checked={config[key]} onChange={event=>setConfig({...config,[key]:event.target.checked})}/></label>)}<label>Trace sampling <strong>{samplingPercent(config.sample_rate)}</strong><input type="range" min="0" max="1" step="0.05" value={config.sample_rate} onChange={event=>setConfig({...config,sample_rate:Number(event.target.value)})}/></label><label>Retained spans<input type="number" min="100" max="100000" value={config.retention_limit} onChange={event=>setConfig({...config,retention_limit:Number(event.target.value)})}/></label><button disabled={busy} onClick={()=>void save()}><Save size={16}/> Save controls</button></article><article><header><Braces/><div><strong>Prometheus preview</strong><small>Credential-free scrape format</small></div></header><pre>{metrics||"No request metrics recorded yet."}</pre><button onClick={()=>void exportTraces()}>Export OTLP traces</button></article></section>}</main>
}
