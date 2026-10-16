import { CalendarRange } from "lucide-react"
import { useId, useState } from "react"

import {
  RANGE_PRESETS,
  customRangeProblem,
  describeRange,
  fromLocalInput,
  toLocalInput,
  type TimeRangeValue,
} from "../../lib/timeRange"

interface TimeRangeControlProps {
  value: TimeRangeValue
  onChange: (value: TimeRangeValue) => void
  /** e.g. "Decided history": says what the range applies to when open work is always shown. */
  label?: string
}

const CUSTOM = "custom"

/**
 * One range control for every evidence list. The server applies the range; this only chooses it.
 * A custom range is checked here with the same rules the server uses, so it never sends one that
 * is certain to fail. The server may still refuse a start older than configured retention.
 */
export function TimeRangeControl({ value, onChange, label = "Time range" }: TimeRangeControlProps) {
  const id = useId()
  const [editing, setEditing] = useState(false)
  const [since, setSince] = useState(() => toLocalInput(value.kind === "custom" ? value.since : new Date(Date.now() - 86_400_000).toISOString()))
  const [until, setUntil] = useState(() => (value.kind === "custom" && value.until ? toLocalInput(value.until) : ""))

  const sinceIso = fromLocalInput(since)
  const untilIso = until ? fromLocalInput(until) : null
  const problem = until && !untilIso ? "Choose a valid end date and time." : customRangeProblem(sinceIso, untilIso)
  const selected = editing ? CUSTOM : value.kind === "preset" ? value.preset : CUSTOM

  function choose(next: string) {
    if (next === CUSTOM) {
      setEditing(true)
      return
    }
    setEditing(false)
    onChange({ kind: "preset", preset: next as (typeof RANGE_PRESETS)[number]["id"] })
  }

  function apply() {
    if (problem || !sinceIso) return
    setEditing(false)
    onChange({ kind: "custom", since: sinceIso, until: untilIso })
  }

  return (
    <div className="gg-time-range">
      <label className="gg-time-range__select">
        <CalendarRange size={15} aria-hidden="true" />
        <span className="gg-sr-only">{label}</span>
        <select value={selected} onChange={(event) => choose(event.target.value)} data-testid="time-range">
          {RANGE_PRESETS.map((preset) => (
            <option key={preset.id} value={preset.id}>{preset.label}</option>
          ))}
          <option value={CUSTOM}>Custom range…</option>
        </select>
      </label>
      {editing && (
        <div className="gg-time-range__custom" role="group" aria-label="Custom time range">
          <label htmlFor={`${id}-since`}>From</label>
          <input id={`${id}-since`} type="datetime-local" value={since} onChange={(event) => setSince(event.target.value)} />
          <label htmlFor={`${id}-until`}>To</label>
          <input id={`${id}-until`} type="datetime-local" value={until} onChange={(event) => setUntil(event.target.value)} aria-describedby={`${id}-hint`} />
          <span id={`${id}-hint`} className="gg-time-range__hint">{problem ?? (until ? "Your local time." : "Leave empty for “now”. Your local time.")}</span>
          <button type="button" className="gg-button" onClick={apply} disabled={Boolean(problem)}>Apply</button>
          <button type="button" className="gg-button" onClick={() => setEditing(false)}>Cancel</button>
        </div>
      )}
    </div>
  )
}

interface RangeNoticeProps {
  range: TimeRangeValue
  /** The server said more records exist in this range than were returned. */
  truncated?: boolean
  /** How many records came back. */
  shown: number
  /** Plural noun, e.g. "requests". */
  noun: string
  /** e.g. "Pending requests are shown whatever the range." */
  openNote?: string
}

/** One honest sentence about what the list holds: the range, and whether it was capped. */
export function RangeNotice({ range, truncated, shown, noun, openNote }: RangeNoticeProps) {
  return (
    <p className="gg-range-notice" aria-live="polite" data-testid="range-notice">
      {truncated ? (
        <><strong>Newest {shown} {noun} {describeRange(range)}.</strong> More exist; narrow the range to see older ones.</>
      ) : (
        <>{shown} {noun} {describeRange(range)}.</>
      )}
      {openNote && <> {openNote}</>}
    </p>
  )
}

interface RangeBarProps {
  value: TimeRangeValue
  onChange: (value: TimeRangeValue) => void
  label?: string
  /** What the list holds; omitted while it loads. */
  notice?: Omit<RangeNoticeProps, "range"> | null
}

/** The range row under a list's toolbar: the choice and what it produced, side by side. */
export function RangeBar({ value, onChange, label, notice }: RangeBarProps) {
  return (
    <div className="gg-range-bar">
      <TimeRangeControl value={value} onChange={onChange} label={label} />
      {notice && <RangeNotice range={value} {...notice} />}
    </div>
  )
}
