import {
  Ban, KeyRound, Plus, RefreshCw, Search, ShieldCheck,
  ShieldEllipsis, UserCog, UsersRound, X,
} from "lucide-react"
import { useMemo, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useAuth } from "../context/AuthContext"
import { useToast } from "../context/ToastContext"
import { ConfirmDialog } from "../components/ConfirmDialog"
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState"
import { useDismissableLayer } from "../hooks/useDismissableLayer"
import "../styles/team-access.css"

export type AdminRole = "PLATFORM_ADMIN" | "SECURITY_ANALYST" | "AUDITOR"
export type AdminStatus = "ACTIVE" | "DISABLED"
type Administrator = {
  admin_id: string; email: string; display_name: string; role: AdminRole;
  status: AdminStatus; created_at: string; last_login_at: string | null; permissions: string[]
}
type ListResponse = { administrators: Administrator[]; count: number }
const API = import.meta.env.VITE_API_BASE_URL ?? "/api"

export const roleDescriptions: Record<AdminRole, string> = {
  PLATFORM_ADMIN: "Full platform, identity and policy administration",
  SECURITY_ANALYST: "Investigations, approvals and operational response",
  AUDITOR: "Read-only access to evidence and control posture",
}
export function formatRole(role: AdminRole) {
  return role.replaceAll("_", " ").toLowerCase().replace(/(^|\s)\S/g, c => c.toUpperCase())
}

function headers() {
  const token = sessionStorage.getItem("greyguard_admin_pin")
  if (!token) throw new Error("Administrator session is missing.")
  return { "Content-Type": "application/json", "X-Admin-Pin": token }
}
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, { ...options, headers: { ...headers(), ...options.headers } })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error((body as { detail?: string }).detail ?? `Request failed: ${response.status}`)
  return body as T
}

export default function TeamAccessPage() {
  const { administrator } = useAuth()
  const { pushToast } = useToast()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState("")
  const [creating, setCreating] = useState(false)
  const [selected, setSelected] = useState<Administrator | null>(null)
  const [confirmAdmin, setConfirmAdmin] = useState<Administrator | null>(null)
  const [form, setForm] = useState({ email: "", display_name: "", role: "SECURITY_ANALYST" as AdminRole, password: "" })
  const [edit, setEdit] = useState({ display_name: "", role: "AUDITOR" as AdminRole, status: "ACTIVE" as AdminStatus, password: "" })
  const drawerCloseRef = useRef<HTMLButtonElement>(null)
  const drawerRef = useDismissableLayer<HTMLDivElement>({
    open: creating || !!selected,
    onClose: () => { setCreating(false); setSelected(null) },
    trapFocus: true,
    initialFocusRef: drawerCloseRef,
    lockBodyScroll: true,
  })

  const team = useQuery({ queryKey: ["administrators"], queryFn: () => request<ListResponse>("/administrators") })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["administrators"] })
  const create = useMutation({
    mutationFn: () => request<Administrator>("/administrators", { method: "POST", body: JSON.stringify(form) }),
    onSuccess: async () => { setCreating(false); setForm({ email: "", display_name: "", role: "SECURITY_ANALYST", password: "" }); pushToast({tone:"success",title:"Administrator created",message:"The accountable operator can now sign in with the assigned role."}); await refresh() },
  })
  const update = useMutation({
    mutationFn: () => request<Administrator>(`/administrators/${selected?.admin_id}`, { method: "PUT", body: JSON.stringify({ display_name: edit.display_name, role: edit.role, status: edit.status }) }),
    onSuccess: async value => { setSelected(value); pushToast({tone:"success",title:"Access profile updated"}); await refresh() },
  })
  const resetPassword = useMutation({
    mutationFn: () => request(`/administrators/${selected?.admin_id}/password`, { method: "POST", body: JSON.stringify({ new_password: edit.password }) }),
    onSuccess: () => { setEdit(current => ({ ...current, password: "" })); pushToast({tone:"success",title:"Password reset",message:"Existing sessions were revoked automatically."}) },
  })
  const revoke = useMutation({
    mutationFn: (admin: Administrator) => request(`/administrators/${admin.admin_id}/sessions/revoke`, { method: "POST" }),
    onSuccess: () => { setConfirmAdmin(null);pushToast({tone:"success",title:"Sessions revoked",message:"The administrator must authenticate again."}) },
  })

  const entries = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return (team.data?.administrators ?? []).filter(item => !needle || [item.email, item.display_name, item.role, item.status].some(value => value.toLowerCase().includes(needle)))
  }, [search, team.data])
  const open = (item: Administrator) => {
    setSelected(item)
    setEdit({ display_name: item.display_name, role: item.role, status: item.status, password: "" })
  }

  if (!administrator?.install_operator) return <main className="team-page"><section className="team-denied"><Ban size={34}/><h1>Install operator access required</h1><p>Your role cannot manage operator identities.</p></section></main>

  return <main className="team-page">
    <section className="team-hero"><div><p><ShieldEllipsis size={15}/> Identity administration</p><h1>Team & Access</h1><span>Create accountable operators and enforce least-privilege roles.</span></div><button type="button" onClick={()=>setCreating(true)}><Plus size={17}/> Add administrator</button></section>
    <section className="team-stats"><article><UsersRound/><div><strong>{team.data?.count ?? 0}</strong><span>Total operators</span></div></article><article><ShieldCheck/><div><strong>{team.data?.administrators.filter(x=>x.status==="ACTIVE").length ?? 0}</strong><span>Active accounts</span></div></article><article><UserCog/><div><strong>3</strong><span>Enforced roles</span></div></article></section>
    <section className="team-panel"><header><label><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search operators or roles"/></label><button type="button" onClick={()=>void refresh()}><RefreshCw size={16}/>Refresh</button></header>
      {team.isLoading && <LoadingState label="Loading administrator accounts" rows={3}/>} 
      {team.isError && <ErrorState message={team.error.message} onRetry={() => void refresh()}/>} 
      {!team.isLoading&&!team.isError&&entries.length===0&&<EmptyState icon={<UsersRound size={30}/>} title="No administrators found" description="No operator account matches the current search."/>}
      <div className="team-grid">{entries.map(item=><button type="button" className="team-card" key={item.admin_id} onClick={()=>open(item)}><span className={`team-avatar team-avatar--${item.status.toLowerCase()}`}>{item.display_name.slice(0,2).toUpperCase()}</span><div><strong>{item.display_name}</strong><small>{item.email}</small></div><span className="team-role">{formatRole(item.role)}</span><span className={`team-status team-status--${item.status.toLowerCase()}`}>{item.status}</span></button>)}</div>
    </section>

    {(creating || selected) && <div className="team-modal"><button type="button" className="team-backdrop" onClick={()=>{setCreating(false);setSelected(null)}} aria-label="Close"/><section ref={drawerRef} className="team-drawer" role="dialog" aria-modal="true" aria-label={creating?"Add administrator":"Manage administrator"}><header><div><p>Role-based control</p><h2>{creating?"Add administrator":"Manage administrator"}</h2></div><button ref={drawerCloseRef} type="button" onClick={()=>{setCreating(false);setSelected(null)}} aria-label="Close"><X/></button></header>
      {creating ? <form onSubmit={e=>{e.preventDefault();create.mutate()}}><label>Display name<input required value={form.display_name} onChange={e=>setForm({...form,display_name:e.target.value})}/></label><label>Email<input required type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label><label>Role<select value={form.role} onChange={e=>setForm({...form,role:e.target.value as AdminRole})}>{Object.keys(roleDescriptions).map(role=><option key={role} value={role}>{formatRole(role as AdminRole)}</option>)}</select><small>{roleDescriptions[form.role]}</small></label><label>Temporary password<input required type="password" minLength={12} value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></label><button disabled={create.isPending}>{create.isPending?"Creating…":"Create accountable operator"}</button>{create.isError&&<p className="team-error">{create.error.message}</p>}</form>
      : selected && <div className="team-edit"><label>Display name<input value={edit.display_name} onChange={e=>setEdit({...edit,display_name:e.target.value})}/></label><label>Role<select value={edit.role} onChange={e=>setEdit({...edit,role:e.target.value as AdminRole})}>{Object.keys(roleDescriptions).map(role=><option key={role} value={role}>{formatRole(role as AdminRole)}</option>)}</select><small>{roleDescriptions[edit.role]}</small></label><label>Status<select value={edit.status} onChange={e=>setEdit({...edit,status:e.target.value as AdminStatus})}><option>ACTIVE</option><option>DISABLED</option></select></label><button onClick={()=>update.mutate()} disabled={update.isPending}>Save access profile</button><hr/><label>New password<input type="password" minLength={12} value={edit.password} onChange={e=>setEdit({...edit,password:e.target.value})} placeholder="At least 12 characters"/></label><button className="team-secondary" disabled={edit.password.length<12||resetPassword.isPending} onClick={()=>resetPassword.mutate()}><KeyRound size={16}/>Reset password</button><button className="team-danger" onClick={()=>setConfirmAdmin(selected)}>Revoke active sessions</button>{(update.isError||resetPassword.isError||revoke.isError)&&<p className="team-error">{update.error?.message||resetPassword.error?.message||revoke.error?.message}</p>}</div>}
    </section></div>}
    <ConfirmDialog open={Boolean(confirmAdmin)} title="Revoke active sessions?" description={`${confirmAdmin?.display_name ?? "This administrator"} will be signed out from every active session and must authenticate again.`} confirmLabel="Revoke sessions" busy={revoke.isPending} onCancel={()=>setConfirmAdmin(null)} onConfirm={()=>confirmAdmin&&revoke.mutate(confirmAdmin)}/>
  </main>
}
