"""Background delivery worker lifecycle.

`backend.app.api` runs as two uvicorn worker processes in production
(`deployment/backend.Dockerfile`). Each process starts one of these loops on
startup; both loops poll the same database. That is safe only because every
queue table uses an atomic claim (see `outbound_delivery.new_claim_token` and
each module's `process_*`/`run_due_schedules` function) before a worker acts
on a row, so the two processes never act on the same row twice.

This module owns only the loop and its start/stop lifecycle. It intentionally
contains no delivery logic of its own.
"""
from __future__ import annotations

import asyncio
import os
import socket
import sys

from .incident_integrations import process_incidents, real_sender as send_incident
from .notification_delivery import process_deliveries, real_sender as send_notification
from .report_governance import run_due_schedules
from .security_exports import process_queue, real_sender as send_export

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def _running_under_pytest() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules


def _enabled() -> bool:
    override = os.environ.get("GREYGUARD_DELIVERY_WORKER_ENABLED", "").strip().lower()
    if override:
        return override == "true"
    # Any FastAPI TestClient(app) run as a context manager triggers this same lifespan, often
    # against the real on-disk dev database (no test in this suite overrides GREYGUARD_DATA_DIR
    # for API-level tests). Defaulting to disabled under pytest keeps a test from ever making a
    # real outbound send; GREYGUARD_DELIVERY_WORKER_ENABLED=true overrides this for a test that
    # specifically wants to exercise the worker loop itself.
    return not _running_under_pytest()


def _interval_seconds() -> float:
    try:
        return max(1.0, float(os.environ.get("GREYGUARD_DELIVERY_INTERVAL_SECONDS", "15")))
    except ValueError:
        return 15.0


def _batch_limit() -> int:
    try:
        return max(1, int(os.environ.get("GREYGUARD_DELIVERY_BATCH_LIMIT", "25")))
    except ValueError:
        return 25


def _run_tick() -> None:
    """One pass over every outbound queue. Never let one subsystem's failure stop the others."""
    limit = _batch_limit()
    for label, action in (
        ("notification_delivery", lambda: process_deliveries(send_notification, limit=limit, worker_id=WORKER_ID)),
        ("incident_integrations", lambda: process_incidents(send_incident, limit=limit, worker_id=WORKER_ID)),
        ("security_exports", lambda: process_queue(send_export, limit=limit, worker_id=WORKER_ID)),
        ("report_governance", lambda: run_due_schedules(notifier=send_notification, limit=limit, worker_id=WORKER_ID)),
    ):
        try:
            action()
        except Exception:
            # A fully unexpected error (e.g. the database file is briefly unavailable during a
            # restart) must not take down the API process or the other three subsystems' delivery.
            # The individual queue functions already turn ordinary send failures into
            # QUEUED/DEAD_LETTER state before this point, so reaching here is itself unusual and
            # worth surfacing through whatever process-level log aggregation is configured.
            import logging
            logging.getLogger("greyguard.outbound_worker").exception("Delivery tick failed for %s", label)


async def _loop(stop_event: "asyncio.Event") -> None:
    interval = _interval_seconds()
    while not stop_event.is_set():
        await asyncio.to_thread(_run_tick)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


def start_worker() -> tuple["asyncio.Task | None", "asyncio.Event | None"]:
    if not _enabled():
        return None, None
    stop_event = asyncio.Event()
    task = asyncio.create_task(_loop(stop_event), name="greyguard-outbound-delivery-worker")
    return task, stop_event


async def stop_worker(task, stop_event, *, grace_seconds: float = 10.0) -> None:
    if task is None:
        return
    stop_event.set()
    try:
        await asyncio.wait_for(task, timeout=grace_seconds)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        task.cancel()
