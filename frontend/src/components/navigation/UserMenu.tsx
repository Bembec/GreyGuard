import { Building2, ChevronDown, LockKeyhole, LogOut, Settings, ShieldCheck } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router-dom"

import { useAuth } from "../../context/AuthContext"
import { useDismissableLayer } from "../../hooks/useDismissableLayer"
import "../../styles/user-menu.css"

const ROLE_LABELS: Record<string, string> = {
  PLATFORM_ADMIN: "Platform Administrator",
  SECURITY_ANALYST: "Security Analyst",
  AUDITOR: "Auditor",
}

/** Replaces the previously static, non-interactive topbar operator label. */
export function UserMenu() {
  const { administrator, switchActiveOrg, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [switching, setSwitching] = useState(false)
  const panelRef = useDismissableLayer<HTMLDivElement>({ open, onClose: () => setOpen(false), trapFocus: true })

  if (!administrator) return null

  function go(path: string) {
    setOpen(false)
    navigate(path)
  }

  async function selectOrg(orgId: string) {
    if (orgId === administrator?.active_org_id || switching) return
    setSwitching(true)
    try {
      await switchActiveOrg(orgId)
    } finally {
      setSwitching(false)
    }
  }

  const organizations = administrator.organizations ?? []

  return (
    <div className="user-menu">
      <button
        type="button"
        className="user-menu__trigger"
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls="user-menu-panel"
        onClick={() => setOpen((value) => !value)}
      >
        <span className="user-menu__avatar">
          <ShieldCheck size={16} />
        </span>
        <span className="user-menu__identity">
          <strong>{administrator.display_name}</strong>
          <small>{ROLE_LABELS[administrator.role] ?? administrator.role}</small>
        </span>
        <ChevronDown size={15} />
      </button>
      {open && (
        <div id="user-menu-panel" ref={panelRef} className="user-menu__panel" role="menu" aria-label="Administrator menu">
          <div className="user-menu__panel-header">
            <strong>{administrator.display_name}</strong>
            <small>{administrator.email}</small>
          </div>
          {organizations.length > 1 && (
            <div className="user-menu__orgs">
              <small>
                <Building2 size={13} />
                Organization
              </small>
              {organizations.map((org) => (
                <button
                  key={org.org_id}
                  type="button"
                  role="menuitemradio"
                  aria-checked={org.org_id === administrator.active_org_id}
                  className={
                    org.org_id === administrator.active_org_id
                      ? "user-menu__org is-active"
                      : "user-menu__org"
                  }
                  disabled={switching}
                  onClick={() => void selectOrg(org.org_id)}
                >
                  {org.org_name}
                </button>
              ))}
            </div>
          )}
          <button type="button" role="menuitem" onClick={() => go("/account-security")}>
            <LockKeyhole size={16} />
            Account security
          </button>
          <button type="button" role="menuitem" onClick={() => go("/settings")}>
            <Settings size={16} />
            Settings
          </button>
          <div className="user-menu__divider" />
          <button type="button" role="menuitem" className="user-menu__signout" onClick={() => logout()}>
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
