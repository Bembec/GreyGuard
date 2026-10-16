import { Guidance } from "../components/page/Guidance"
import { PageHeader } from "../components/page/PageHeader"
import {
  Bell,
  Check,
  KeyRound,
  LogOut,
  MonitorCog,
  RefreshCw,
  Save,
  Server,
  ShieldCheck,
  Sparkles,
} from "lucide-react"
import {
  useEffect,
  useMemo,
  useState,
} from "react"

import { OrganizationLifecyclePanel } from "../components/OrganizationLifecyclePanel"
import { PlanUsagePanel } from "../components/PlanUsagePanel"
import { useAuth } from "../context/AuthContext"
import {
  applySettings,
  defaultSettings,
  loadSettings,
  storageKey,
  type AccentChoice,
  type SettingsState,
} from "../lib/interfaceSettings"
import "../styles/settings.css"

function SettingSwitch({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  description: string
}) {
  return (
    <div className="setting-row">
      <div>
        <strong>{label}</strong>
        <p>{description}</p>
      </div>

      <button
        type="button"
        className={
          checked
            ? "settings-switch is-enabled"
            : "settings-switch"
        }
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
      >
        <span />
      </button>
    </div>
  )
}

export default function SettingsPage() {
  const { logout } = useAuth()
  const [settings, setSettings] =
    useState<SettingsState>(loadSettings)

  const [saved, setSaved] = useState(false)

  const apiBaseUrl =
    import.meta.env.VITE_API_BASE_URL
    ?? "/api"

  const environmentLabel = useMemo(
    () => (
      import.meta.env.DEV
        ? "Development"
        : "Production"
    ),
    [],
  )

  useEffect(() => {
    applySettings(settings)
  }, [settings])

  function updateSetting<
    Key extends keyof SettingsState
  >(
    key: Key,
    value: SettingsState[Key],
  ) {
    setSettings((currentSettings) => ({
      ...currentSettings,
      [key]: value,
    }))

    setSaved(false)
  }

  function saveSettings() {
    localStorage.setItem(
      storageKey,
      JSON.stringify(settings),
    )

    applySettings(settings)
    setSaved(true)

    window.setTimeout(() => {
      setSaved(false)
    }, 2500)
  }

  function resetPreferences() {
    setSettings(defaultSettings)

    localStorage.removeItem(storageKey)
    applySettings(defaultSettings)
    setSaved(false)
  }


  return (
    <main className="settings-page gg-page-pad">
      <PageHeader
        title="Settings"
        icon={<MonitorCog size={22} />}
        description="Your organization's plan, usage and lifecycle, this console's display preferences, and the security environment protecting this session."
      />

      <Guidance id="settings" title="What lives here">
        <ul>
          <li><strong>Plan & usage</strong> and <strong>Readiness & data</strong> belong to the organization; install operators assign plans.</li>
          <li>Interface preferences such as density, motion and accent are saved on this device only.</li>
          <li>Exporting organization data is always available, whatever the plan's state.</li>
        </ul>
      </Guidance>

      {/* Configuration facts, not metrics, so they are a facts row rather than KPI cards. */}
      <dl className="gg-facts settings-facts" aria-label="Session and environment">
        <div><dt>Administrator session</dt><dd>Authenticated</dd></div>
        <div><dt>Environment</dt><dd>{environmentLabel}</dd></div>
        <div><dt>API connection</dt><dd>{apiBaseUrl}</dd></div>
        <div><dt>Refresh interval</dt><dd>{settings.refreshInterval} seconds</dd></div>
      </dl>

      <div className="settings-layout">
        <section className="settings-panel">
          <div className="settings-panel-heading">
            <div className="settings-heading-icon">
              <Sparkles size={20} />
            </div>

            <div>
              <span>Workspace appearance</span>
              <h2>Interface preferences</h2>
            </div>
          </div>

          <div className="settings-control-group">
            <label>Interface accent</label>

            <div className="accent-options">
              {(
                [
                  "cyan",
                  "violet",
                  "emerald",
                ] as AccentChoice[]
              ).map((accent) => (
                <button
                  type="button"
                  key={accent}
                  className={
                    settings.accentChoice
                    === accent
                      ? `accent-option ${accent} selected`
                      : `accent-option ${accent}`
                  }
                  onClick={() => {
                    updateSetting(
                      "accentChoice",
                      accent,
                    )
                  }}
                >
                  <span />

                  {accent}

                  {settings.accentChoice
                    === accent && (
                    <Check size={15} />
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="settings-control-group">
            <label>Information density</label>

            <div className="density-options">
              <button
                type="button"
                className={
                  settings.interfaceDensity
                  === "comfortable"
                    ? "density-option selected"
                    : "density-option"
                }
                onClick={() => {
                  updateSetting(
                    "interfaceDensity",
                    "comfortable",
                  )
                }}
              >
                <strong>Comfortable</strong>
                <span>
                  More spacing for investigation
                  and review.
                </span>
              </button>

              <button
                type="button"
                className={
                  settings.interfaceDensity
                  === "compact"
                    ? "density-option selected"
                    : "density-option"
                }
                onClick={() => {
                  updateSetting(
                    "interfaceDensity",
                    "compact",
                  )
                }}
              >
                <strong>Compact</strong>
                <span>
                  Higher information density for
                  active operations.
                </span>
              </button>
            </div>
          </div>

          <SettingSwitch
            checked={settings.reducedMotion}
            onChange={(checked) => {
              updateSetting(
                "reducedMotion",
                checked,
              )
            }}
            label="Reduced motion"
            description="Minimize decorative motion and interface transitions."
          />
        </section>

        <section className="settings-panel">
          <div className="settings-panel-heading">
            <div className="settings-heading-icon">
              <Bell size={20} />
            </div>

            <div>
              <span>Operational awareness</span>
              <h2>Monitoring behaviour</h2>
            </div>
          </div>

          <SettingSwitch
            checked={settings.liveRefresh}
            onChange={(checked) => {
              updateSetting(
                "liveRefresh",
                checked,
              )
            }}
            label="Live information refresh"
            description="Allow command-center views to refresh security information automatically."
          />

          <SettingSwitch
            checked={
              settings.securityNotifications
            }
            onChange={(checked) => {
              updateSetting(
                "securityNotifications",
                checked,
              )
            }}
            label="Security notifications"
            description="Display important approval, suspension and execution notices."
          />

          <div className="settings-control-group">
            <label htmlFor="refresh-interval">
              Refresh interval
            </label>

            <div className="interval-control">
              <input
                id="refresh-interval"
                type="range"
                min="10"
                max="120"
                step="10"
                value={settings.refreshInterval}
                disabled={!settings.liveRefresh}
                onChange={(event) => {
                  updateSetting(
                    "refreshInterval",
                    Number(event.target.value),
                  )
                }}
              />

              <output>
                {settings.refreshInterval}s
              </output>
            </div>
          </div>
        </section>

        <section className="settings-panel">
          <div className="settings-panel-heading">
            <div className="settings-heading-icon">
              <KeyRound size={20} />
            </div>

            <div>
              <span>Session protection</span>
              <h2>Administrator security</h2>
            </div>
          </div>

          <div className="security-information">
            <div>
              <span>Credential storage</span>
              <strong>
                Browser session only
              </strong>
            </div>

            <div>
              <span>Transport header</span>
              <strong>X-Admin-Pin</strong>
            </div>

            <div>
              <span>Secret persistence</span>
              <strong>Not written to disk</strong>
            </div>

            <div>
              <span>Session clearance</span>
              <strong>Available immediately</strong>
            </div>
          </div>

          <div className="settings-security-note">
            <ShieldCheck size={18} />

            <p>
              GreyGuard stores the administrator
              PIN only in this browser tab’s
              session storage. Ending the session
              removes it and returns the interface
              to the authentication screen.
            </p>
          </div>

          <button
            type="button"
            className="settings-danger-button"
            onClick={() => void logout()}
          >
            <LogOut size={17} />
            End administrator session
          </button>
        </section>

        <PlanUsagePanel />
        <OrganizationLifecyclePanel />

        <section className="settings-panel">
          <div className="settings-panel-heading">
            <div className="settings-heading-icon">
              <Server size={20} />
            </div>

            <div>
              <span>Runtime information</span>
              <h2>Control-plane environment</h2>
            </div>
          </div>

          <div className="environment-list">
            <div>
              <span>Frontend mode</span>
              <code>{environmentLabel}</code>
            </div>

            <div>
              <span>API base URL</span>
              <code>{apiBaseUrl}</code>
            </div>

            <div>
              <span>Authentication</span>
              <code>Administrator PIN</code>
            </div>

            <div>
              <span>Network execution</span>
              <code>Disabled</code>
            </div>

            <div>
              <span>Arbitrary commands</span>
              <code>Disabled</code>
            </div>

            <div>
              <span>Filesystem boundary</span>
              <code>Sandbox only</code>
            </div>
          </div>
        </section>
      </div>

      <section className="settings-actions">
        <div>
          <strong>
            Command-center preferences
          </strong>

          <span>
            Changes remain local to this browser.
          </span>
        </div>

        <div className="settings-action-buttons">
          <button
            type="button"
            className="settings-secondary-button"
            onClick={resetPreferences}
          >
            <RefreshCw size={16} />
            Restore defaults
          </button>

          <button
            type="button"
            className="settings-primary-button"
            onClick={saveSettings}
          >
            {saved ? (
              <Check size={16} />
            ) : (
              <Save size={16} />
            )}

            {saved
              ? "Preferences saved"
              : "Save preferences"}
          </button>
        </div>
      </section>
    </main>
  )
}
