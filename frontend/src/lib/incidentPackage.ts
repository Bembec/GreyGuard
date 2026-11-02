/** The download name for an incident package. The incident id never shapes a path. */
export function safePackageFilename(alertId: string) {
  return `greyguard-incident-${alertId.replace(/[^a-zA-Z0-9_-]/g, "-")}.json`
}
