"""Redacted tracing, correlation, structured logs, and Prometheus metrics."""

import contextvars
import hashlib
import json
import logging
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone

from .database import database_path


current_correlation_id = contextvars.ContextVar("correlation_id", default="")
_metrics = {}
_metrics_lock = threading.Lock()
_logger = logging.getLogger("greyguard.observability")
_sensitive = ("password", "secret", "token", "credential", "authorization", "api_key", "pin")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def redact(value):
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if any(marker in str(key).lower() for marker in _sensitive)
            else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    text = str(value) if isinstance(value, str) else value
    if isinstance(text, str):
        return re.sub(
            r"(?i)(password|secret|token|credential|api[_-]?key|pin)=([^&\s]+)",
            r"\1=[REDACTED]", text,
        )
    return value


def initialize_observability():
    with sqlite3.connect(database_path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS observability_config (
            config_id INTEGER PRIMARY KEY CHECK(config_id=1), tracing_enabled INTEGER NOT NULL,
            metrics_enabled INTEGER NOT NULL, structured_logs_enabled INTEGER NOT NULL,
            sample_rate REAL NOT NULL, retention_limit INTEGER NOT NULL,
            updated_at TEXT NOT NULL, updated_by TEXT NOT NULL)""")
        connection.execute("""INSERT OR IGNORE INTO observability_config VALUES
            (1,1,1,1,0.25,5000,?,?)""", (utc_now(), "system"))
        connection.execute("""CREATE TABLE IF NOT EXISTS observability_spans (
            span_id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, correlation_id TEXT NOT NULL,
            timestamp TEXT NOT NULL, duration_ms REAL NOT NULL, method TEXT NOT NULL,
            path TEXT NOT NULL, status_code INTEGER NOT NULL, sampled INTEGER NOT NULL)""")
        connection.execute("""CREATE TABLE IF NOT EXISTS observability_correlations (
            request_id TEXT PRIMARY KEY, correlation_id TEXT NOT NULL,
            created_at TEXT NOT NULL)""")


def bind_request(request_id, correlation_id=None):
    correlation = correlation_id or current_correlation_id.get()
    if request_id and correlation:
        with sqlite3.connect(database_path) as connection:
            connection.execute("INSERT OR REPLACE INTO observability_correlations VALUES(?,?,?)",
                               (str(request_id), correlation, utc_now()))


def _bound_correlation(path):
    match = re.search(r"/tool-requests/([^/]+)", path)
    if not match:
        return None
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT correlation_id FROM observability_correlations WHERE request_id=?",
            (match.group(1),),
        ).fetchone()
    return row[0] if row else None


def get_config():
    initialize_observability()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = dict(connection.execute("SELECT * FROM observability_config WHERE config_id=1").fetchone())
    for key in ("tracing_enabled", "metrics_enabled", "structured_logs_enabled"):
        row[key] = bool(row[key])
    return row


def update_config(tracing_enabled, metrics_enabled, structured_logs_enabled,
                  sample_rate, retention_limit, actor):
    if not 0 <= sample_rate <= 1:
        raise ValueError("Trace sample rate must be between 0 and 1.")
    if not 100 <= retention_limit <= 100_000:
        raise ValueError("Trace retention must be between 100 and 100000 spans.")
    with sqlite3.connect(database_path) as connection:
        connection.execute("""UPDATE observability_config SET tracing_enabled=?,metrics_enabled=?,
            structured_logs_enabled=?,sample_rate=?,retention_limit=?,updated_at=?,updated_by=?
            WHERE config_id=1""", (
            int(tracing_enabled), int(metrics_enabled), int(structured_logs_enabled),
            float(sample_rate), int(retention_limit), utc_now(), actor,
        ))
    return get_config()


def start_request(method, path, incoming_correlation=None, traceparent=None):
    config = get_config()
    valid_incoming = incoming_correlation if incoming_correlation and re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", incoming_correlation) else None
    correlation = valid_incoming or _bound_correlation(path) or "corr_" + secrets.token_hex(16)
    trace_match = re.fullmatch(r"00-([0-9a-f]{32})-[0-9a-f]{16}-0[01]", traceparent or "")
    trace_id = trace_match.group(1) if trace_match else secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    threshold = int(config["sample_rate"] * 10_000)
    sampled = config["tracing_enabled"] and int(hashlib.sha256(trace_id.encode()).hexdigest()[:8], 16) % 10_000 < threshold
    current_correlation_id.set(correlation)
    return {"trace_id": trace_id, "span_id": span_id, "correlation_id": correlation,
            "started": time.perf_counter(), "sampled": sampled, "method": method, "path": redact(path)}


def finish_request(context, status_code):
    config = get_config()
    duration = round((time.perf_counter() - context["started"]) * 1000, 3)
    if config["metrics_enabled"]:
        key = (context["method"], context["path"], int(status_code))
        with _metrics_lock:
            count, total = _metrics.get(key, (0, 0.0))
            _metrics[key] = (count + 1, total + duration)
    event = redact({"timestamp": utc_now(), "event": "http_request", **context,
                    "duration_ms": duration, "status_code": int(status_code)})
    event.pop("started", None)
    if config["structured_logs_enabled"]:
        _logger.info(json.dumps(event, separators=(",", ":"), sort_keys=True))
    if context["sampled"]:
        with sqlite3.connect(database_path) as connection:
            connection.execute("INSERT INTO observability_spans VALUES(?,?,?,?,?,?,?,?,1)", (
                context["span_id"], context["trace_id"], context["correlation_id"],
                event["timestamp"], duration, context["method"], context["path"], status_code,
            ))
            limit = config["retention_limit"]
            connection.execute("""DELETE FROM observability_spans WHERE span_id IN (
                SELECT span_id FROM observability_spans ORDER BY timestamp DESC LIMIT -1 OFFSET ?)
            """, (limit,))
    return event


def prometheus_metrics():
    lines = ["# HELP greyguard_http_requests_total Total GreyGuard HTTP requests.",
             "# TYPE greyguard_http_requests_total counter",
             "# HELP greyguard_http_request_duration_milliseconds_total Total request duration.",
             "# TYPE greyguard_http_request_duration_milliseconds_total counter"]
    with _metrics_lock:
        items = list(_metrics.items())
    for (method, path, status), (count, duration) in items:
        labels = f'method="{method}",path="{path}",status="{status}"'
        lines.append(f"greyguard_http_requests_total{{{labels}}} {count}")
        lines.append(f"greyguard_http_request_duration_milliseconds_total{{{labels}}} {duration:.3f}")
    return "\n".join(lines) + "\n"


def otlp_export(limit=200):
    initialize_observability()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM observability_spans ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    spans = [{
        "traceId": row["trace_id"], "spanId": row["span_id"],
        "name": f'{row["method"]} {row["path"]}', "kind": 2,
        "attributes": [
            {"key": "greyguard.correlation_id", "value": {"stringValue": row["correlation_id"]}},
            {"key": "http.response.status_code", "value": {"intValue": row["status_code"]}},
        ],
    } for row in rows]
    return {"resourceSpans": [{"resource": {"attributes": [
        {"key": "service.name", "value": {"stringValue": "greyguard-control-plane"}}
    ]}, "scopeSpans": [{"scope": {"name": "greyguard.observability"}, "spans": spans}]}]}
