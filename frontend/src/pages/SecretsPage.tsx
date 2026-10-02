import { useEffect,useState } from "react"
import { KeyRound,RefreshCw,ShieldOff } from "lucide-react"
import { useAuth } from "../context/AuthContext"
import "../styles/secrets.css"
const API=import.meta.env.VITE_API_BASE_URL??"/api"
type Secret={secret_id:string;name:string;provider:string;reference:string;status:string;created_at:string;last_accessed_at:string|null;access_count:number}
export default function SecretsPage(){
 const {sessionToken,administrator}=useAuth();const [items,setItems]=useState<Secret[]>([]);const [name,setName]=useState("");const [reference,setReference]=useState("");const [message,setMessage]=useState("")
 const headers={"Content-Type":"application/json","x-admin-pin":sessionToken??""}
 const load=async()=>{const r=await fetch(`${API}/secrets`,{headers});const d=await r.json();if(!r.ok)throw new Error(d.detail);setItems(d.secrets)}
 useEffect(()=>{load().catch(e=>setMessage(e.message))},[sessionToken])
 const call=async(path:string,body?:unknown)=>{const r=await fetch(`${API}${path}`,{method:"POST",headers,body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw new Error(d.detail);setMessage("Secret lifecycle updated without exposing its value.");setName("");setReference("");await load()}
 return <main className="secrets-page"><section className="secrets-heading"><div><span>Zero-value exposure</span><h1>Secret lifecycle management</h1><p>GreyGuard stores references and audit evidence only. Secret values are retrieved just in time and never displayed.</p></div><KeyRound size={42}/></section>
 {administrator?.role==="PLATFORM_ADMIN"&&<section className="secret-create"><input placeholder="Display name" value={name} onChange={e=>setName(e.target.value)}/><input placeholder="ENVIRONMENT_VARIABLE" value={reference} onChange={e=>setReference(e.target.value.toUpperCase())}/><button onClick={()=>call("/secrets",{name,reference})}>Register reference</button></section>}
 {message&&<p className="secret-message">{message}</p>}<section className="secret-grid">{items.map(s=><article key={s.secret_id}><div className="secret-card-head"><KeyRound/><span className={s.status.toLowerCase()}>{s.status}</span></div><h2>{s.name}</h2><code>{s.reference}</code><dl><div><dt>Provider</dt><dd>{s.provider}</dd></div><div><dt>Access count</dt><dd>{s.access_count}</dd></div><div><dt>Last accessed</dt><dd>{s.last_accessed_at??"Never"}</dd></div></dl>{administrator?.role==="PLATFORM_ADMIN"&&<div className="secret-actions"><button onClick={()=>{const next=prompt("New environment-variable reference",s.reference);if(next)call(`/secrets/${s.secret_id}/rotate`,{reference:next.toUpperCase()})}}><RefreshCw size={15}/>Rotate</button>{s.status==="ACTIVE"&&<button className="danger" onClick={()=>call(`/secrets/${s.secret_id}/revoke`)}><ShieldOff size={15}/>Revoke</button>}</div>}</article>)}</section></main>
}
