"""Time ranges for the evidence lists (P7.5 batch 4d).

A range narrows an org-scoped query and never replaces its org filter: callers AND the fragment
below after their scope clause. Every bound is a bound parameter, never formatted into SQL.

The rules, as approved by the owner on 2026-10-16:
- `since` is inclusive and `until` exclusive; both need an explicit timezone and are compared in UTC.
- `until` without `since` is refused: every range has a start, so it can be held to the lookback.
- The lookback is at most 400 days and never longer than configured retention, so nobody queries
  past what is actually retained (`permitted_lookback_days`).
- Open items (a pending approval, an unresolved alert) stay visible whatever the range; the
  callers that have open items add that themselves (see `in_range_or`).
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

MAX_LOOKBACK_DAYS = 400
# A browser clock a little ahead of the server's must not make "now" an invalid end.
CLOCK_SKEW = timedelta(minutes=5)


def permitted_lookback_days(org_id) -> int:
    """How far back an org may query: never past what retention keeps.

    Today retention is configured install-wide (audit_integrity), so the lookback is the smaller of
    that and the 400-day ceiling. Once per-org retention is authoritative, this reads that org's
    policy instead; every caller already passes org_id."""
    from . import audit_integrity

    retained = audit_integrity.retention_days()
    return MAX_LOOKBACK_DAYS if retained is None else min(MAX_LOOKBACK_DAYS, retained)


@dataclass(frozen=True)
class TimeRange:
    since: str
    until: str | None

    def condition(self, column: str) -> tuple[str, tuple]:
        """The SQL fragment and parameters bounding `column` (a trusted column name, never input)."""
        if self.until is None:
            return f"{column} >= ?", (self.since,)
        return f"({column} >= ? AND {column} < ?)", (self.since, self.until)

    def in_range_or(self, column: str, open_condition: str) -> tuple[str, tuple]:
        """In range, or open: open items are never hidden by a range."""
        fragment, parameters = self.condition(column)
        return f"({fragment} OR {open_condition})", parameters

    def as_dict(self) -> dict:
        return {"since": self.since, "until": self.until}


def _parse(name: str, value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{name} must be an ISO 8601 date and time.") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HTTPException(status_code=422, detail=f"{name} must include a timezone, for example Z or +00:00.")
    return parsed.astimezone(timezone.utc)


def parse_time_range(since: str | None, until: str | None, *, org_id, now: datetime | None = None) -> TimeRange | None:
    """A validated range, or None when neither bound is given (today's unbounded behaviour)."""
    if not since and not until:
        return None
    if not since:
        raise HTTPException(status_code=422, detail="until needs a since: every range has a start.")
    now = now or datetime.now(timezone.utc)
    start = _parse("since", since)
    lookback = permitted_lookback_days(org_id)
    if start < now - timedelta(days=lookback):
        raise HTTPException(status_code=422, detail=f"since may be at most {lookback} days ago.")
    if start > now + CLOCK_SKEW:
        raise HTTPException(status_code=422, detail="since cannot be in the future.")
    end = None
    if until:
        end = _parse("until", until)
        if end <= start:
            raise HTTPException(status_code=422, detail="until must be after since.")
    # Stored timestamps are datetime.isoformat() in UTC, so bounds use the same form and compare
    # correctly as text, including stored values with and without microseconds.
    return TimeRange(start.isoformat(), end.isoformat() if end else None)
