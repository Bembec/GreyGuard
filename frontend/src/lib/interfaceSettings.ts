export type InterfaceDensity = "comfortable" | "compact"
export type AccentChoice = "cyan" | "violet" | "emerald"

export type SettingsState = {
  reducedMotion: boolean
  interfaceDensity: InterfaceDensity
  accentChoice: AccentChoice
  liveRefresh: boolean
  securityNotifications: boolean
  refreshInterval: number
}

export const storageKey = "greyguard_interface_settings"

export const defaultSettings: SettingsState = {
  reducedMotion: false,
  interfaceDensity: "comfortable",
  accentChoice: "cyan",
  liveRefresh: true,
  securityNotifications: true,
  refreshInterval: 30,
}

export function loadSettings(): SettingsState {
  const storedSettings = localStorage.getItem(storageKey)
  if (!storedSettings) return defaultSettings
  try {
    return { ...defaultSettings, ...JSON.parse(storedSettings) } as SettingsState
  } catch {
    return defaultSettings
  }
}

/**
 * Sets the data-motion/data-density/data-accent attributes CSS reads (see settings.css).
 * Must also run once at boot (see main.tsx) - without that, a saved preference only took
 * effect while SettingsPage itself was mounted and silently reverted to defaults on every
 * hard reload, since nothing else ever read localStorage back out.
 */
export function applySettings(settings: SettingsState) {
  const root = document.documentElement
  root.dataset.motion = settings.reducedMotion ? "reduced" : "full"
  root.dataset.density = settings.interfaceDensity
  root.dataset.accent = settings.accentChoice
}
