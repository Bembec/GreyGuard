import {
  Bell,
  Check,
  Database,
  Gauge,
  KeyRound,
  LogOut,
  MonitorCog,
  RefreshCw,
  Save,
  Server,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react"
import {
  useEffect,
  useMemo,
  useState,
} from "react"

import "../styles/settings.css"


type InterfaceDensity =
  | "comfortable"
  | "compact"

type AccentChoice =
  | "cyan"
  | "violet"
  | "emerald"

type SettingsState = {
  reducedMotion: boolean
  interfaceDensity: InterfaceDensity
  accentChoice: AccentChoice
  liveRefresh: boolean
  securityNotifications: boolean
  refreshInterval: number
}

const storageKey = "greyguard_interface_settings"

const defaultSettings: SettingsState = {
  reducedMotion: false,
  interfaceDensity: "comfortable",
  accentChoice: "cyan",
  liveRefresh: true,
  securityNotifications: true,
  refreshInterval: 30,
}

function loadSettings(): SettingsState {
  const storedSettings =
    localStorage.getItem(storageKey)

  if (!storedSettings) {
    return defaultSettings
  }

  try {
    return {
      ...defaultSettings,
      ...JSON.parse(storedSettings),
    } as SettingsState
  } catch {
    return defaultSettings
  }
}

function applySettings(
  settings: SettingsState,
) {
  const root = document.documentElement

  root.dataset.motion = settings.reducedMotion
    ? "reduced"
    : "full"

  root.dataset.density =
    settings.interfaceDensity

  root.dataset.accent =
    settings.accentChoice
}

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

  function endAdministratorSession() {
    sessionStorage.removeItem(
      "greyguard_admin_pin",
    )

    window.location.reload()
  }

  return (
    <main className="settings-page">
      <section className="settings-hero">
        <div className="settings-hero-copy">
          <span className="settings-eyebrow">
            <SlidersHorizontal size={15} />
            Control configuration
          </span>

          <h1>Settings</h1>

          <p>
            Configure the GreyGuard command
            center experience and inspect the
            security environment currently
            protecting this administrative
            session.
          </p>
        </div>

        <div className="settings-hero-orbit">
          <div className="settings-orbit-ring ring-one" />
          <div className="settings-orbit-ring ring-two" />

          <div className="settings-orbit-core">
            <MonitorCog size={30} />
          </div>

          <span className="orbit-node node-one" />
          <span className="orbit-node node-two" />
          <span className="orbit-node node-three" />
        </div>
      </section>

      <section className="settings-status-grid">
        <article>
          <ShieldCheck size={20} />
          <div>
            <span>Administrator session</span>
            <strong>Authenticated</strong>
          </div>
        </article>

        <article>
          <Server size={20} />
          <div>
            <span>Environment</span>
            <strong>{environmentLabel}</strong>
          </div>
        </article>

        <article>
          <Database size={20} />
          <div>
            <span>API connection</span>
            <strong>{apiBaseUrl}</strong>
          </div>
        </article>

        <article>
          <Gauge size={20} />
          <div>
            <span>Refresh interval</span>
            <strong>
              {settings.refreshInterval} seconds
            </strong>
          </div>
        </article>
      </section>

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
            onClick={endAdministratorSession}
          >
            <LogOut size={17} />
            End administrator session
          </button>
        </section>

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
