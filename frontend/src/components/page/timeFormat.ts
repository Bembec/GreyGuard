/** "4 min ago" style relative time for operational lists; the full timestamp goes in a title. */
export function relativeTime(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "Never"
  const then = Date.parse(iso)
  if (Number.isNaN(then)) return iso
  const seconds = Math.round((now - then) / 1000)
  if (seconds < 0) return "Just now"
  if (seconds < 60) return "Just now"
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days} d ago`
  return new Date(then).toLocaleDateString()
}

export function greetingFor(hour: number): string {
  if (hour < 5) return "Good evening"
  if (hour < 12) return "Good morning"
  if (hour < 18) return "Good afternoon"
  return "Good evening"
}
