"""Live administrator security-event streaming for GreyGuard."""

import asyncio
import json
from collections import deque
from collections.abc import AsyncIterator

from fastapi import Request

from .alerts import sync_alerts_from_events
from .database import get_administrator_audit_events


def encode_sse(
    event_name: str,
    data: dict,
    event_id: str | None = None,
) -> str:
    """Encode one Server-Sent Event message."""

    lines = []

    if event_id:
        lines.append(f"id: {event_id}")

    lines.append(f"event: {event_name}")
    lines.append(
        "data: "
        + json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
    )

    return "\n".join(lines) + "\n\n"


async def stream_administrator_events(
    request: Request,
    event_type: str | None = None,
    agent_name: str | None = None,
    limit: int = 100,
    include_history: bool = True,
    poll_interval: float = 1.0,
) -> AsyncIterator[str]:
    """Stream unified GreyGuard evidence to an administrator."""

    seen_event_ids: set[str] = set()
    seen_event_order: deque[str] = deque()
    maximum_seen_events = 2000

    def remember_event(event_id: str) -> None:
        """Remember an event ID while limiting memory usage."""

        if event_id in seen_event_ids:
            return

        seen_event_ids.add(event_id)
        seen_event_order.append(event_id)

        while len(seen_event_order) > maximum_seen_events:
            oldest_event_id = seen_event_order.popleft()
            seen_event_ids.discard(oldest_event_id)

    yield encode_sse(
        event_name="stream-ready",
        data={
            "status": "connected",
            "application": "GreyGuard",
            "stream": "administrator-security-events",
            "include_history": include_history,
            "filters": {
                "event_type": event_type,
                "agent_name": agent_name,
                "limit": limit,
            },
        },
    )

    initial_response = get_administrator_audit_events(
        event_type=event_type,
        agent_name=agent_name,
        limit=limit,
    )

    initial_events = initial_response["events"]
    sync_alerts_from_events(initial_events)

    for event in initial_events:
        event_id = str(event["event_id"])
        remember_event(event_id)

    if include_history:
        for event in reversed(initial_events):
            yield encode_sse(
                event_name="greyguard-event",
                event_id=str(event["event_id"]),
                data=event,
            )

    heartbeat_elapsed = 0.0

    try:
        while True:
            if await request.is_disconnected():
                break

            await asyncio.sleep(poll_interval)
            heartbeat_elapsed += poll_interval

            current_response = get_administrator_audit_events(
                event_type=event_type,
                agent_name=agent_name,
                limit=limit,
            )

            current_events = current_response["events"]
            sync_alerts_from_events(current_events)

            new_events = []

            for event in current_events:
                event_id = str(event["event_id"])

                if event_id not in seen_event_ids:
                    new_events.append(event)

            for event in reversed(new_events):
                event_id = str(event["event_id"])
                remember_event(event_id)

                yield encode_sse(
                    event_name="greyguard-event",
                    event_id=event_id,
                    data=event,
                )

            if heartbeat_elapsed >= 15:
                yield encode_sse(
                    event_name="heartbeat",
                    data={
                        "status": "connected",
                        "stream": (
                            "administrator-security-events"
                        ),
                    },
                )
                heartbeat_elapsed = 0.0

    except asyncio.CancelledError:
        return
