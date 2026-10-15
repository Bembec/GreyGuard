import type { StatTone } from "./StatCard"
import { toneFor } from "./tones"

/** A status word with a tone that never relies on colour alone: the word itself is always shown. */
export function StatusBadge({ value, tone }: { value: string | null | undefined; tone?: StatTone }) {
  const label = value ? value.replaceAll("_", " ") : "—"
  return <span className={`gg-badge gg-badge--${tone ?? toneFor(value)}`}>{label}</span>
}
