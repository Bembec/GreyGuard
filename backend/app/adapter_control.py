"""Disabled-by-default agent adapter registry and safe request translation."""

import json
import re
from . import db_compat as sqlite3
from datetime import datetime, timezone
from typing import Any

from .database import database_path


ADAPTER_DEFINITIONS = {
    "mcp_gateway": {
        "name": "MCP Tool Gateway",
        "protocol": "Model Context Protocol",
        "description": "Translate MCP tool calls into controlled GreyGuard requests.",
    },
    "langchain": {
        "name": "LangChain",
        "protocol": "LangChain Tool Call",
        "description": "Normalize LangChain tool invocations without importing runtime code.",
    },
    "langgraph": {
        "name": "LangGraph",
        "protocol": "LangGraph Node Action",
        "description": "Constrain graph-node actions through GreyGuard policy.",
    },
    "crewai": {
        "name": "CrewAI",
        "protocol": "CrewAI Tool Call",
        "description": "Control crew tool requests with agent identity and scope enforcement.",
    },
    "autogen": {
        "name": "AutoGen",
        "protocol": "AutoGen Function Call",
        "description": "Translate structured AutoGen function calls into controlled requests.",
    },
    "generic_webhook": {
        "name": "Generic Webhook Agent",
        "protocol": "JSON",
        "description": "Normalize authenticated inbound agent actions.",
    },
    "agentguard_legacy": {
        "name": "AgentGuard Legacy",
        "protocol": "AgentGuard V1",
        "description": "Translate legacy permission-check requests.",
    },
}
SENSITIVE_MARKERS = ("password", "secret", "token", "credential", "api_key")
AVAILABLE_ACTIONS = set()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def initialize_adapter_control(available_actions, org_id="org_default"):
    global AVAILABLE_ACTIONS
    actions = sorted({str(action) for action in available_actions})
    if actions:
        AVAILABLE_ACTIONS = set(actions)
    with sqlite3.connect(database_path) as connection:
        existing_columns = {row[1] for row in connection.execute("PRAGMA table_info(adapter_configs)")}
        if existing_columns and "org_id" not in existing_columns:
            # SQLite cannot ALTER a PRIMARY KEY in place - the old PK (adapter_id alone) would
            # let two orgs collide on the same adapter name, so this rebuilds the table with a
            # composite (adapter_id, org_id) key, carrying every pre-existing row into the
            # default org (same approach as universal_controls.py's reshape).
            connection.execute("ALTER TABLE adapter_configs RENAME TO adapter_configs_pre_org")
        connection.execute("""CREATE TABLE IF NOT EXISTS adapter_configs (
            adapter_id TEXT NOT NULL, org_id TEXT NOT NULL DEFAULT 'org_default',
            name TEXT NOT NULL, protocol TEXT NOT NULL,
            description TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 0,
            owner TEXT, purpose TEXT, allowed_actions_json TEXT NOT NULL,
            updated_at TEXT NOT NULL, updated_by TEXT NOT NULL,
            PRIMARY KEY(adapter_id,org_id))""")
        if existing_columns and "org_id" not in existing_columns:
            connection.execute("""INSERT INTO adapter_configs
                (adapter_id,org_id,name,protocol,description,enabled,owner,purpose,
                 allowed_actions_json,updated_at,updated_by)
                SELECT adapter_id,'org_default',name,protocol,description,enabled,owner,purpose,
                       allowed_actions_json,updated_at,updated_by
                FROM adapter_configs_pre_org""")
            connection.execute("DROP TABLE adapter_configs_pre_org")
        connection.execute("""CREATE TABLE IF NOT EXISTS adapter_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, adapter_id TEXT NOT NULL,
            timestamp TEXT NOT NULL, actor TEXT NOT NULL, event_type TEXT NOT NULL,
            detail TEXT NOT NULL, org_id TEXT NOT NULL DEFAULT 'org_default')""")
        event_columns = {row[1] for row in connection.execute("PRAGMA table_info(adapter_events)")}
        if "org_id" not in event_columns:
            connection.execute("ALTER TABLE adapter_events ADD COLUMN org_id TEXT NOT NULL DEFAULT 'org_default'")
        for adapter_id, definition in ADAPTER_DEFINITIONS.items():
            connection.execute("""INSERT OR IGNORE INTO adapter_configs
                (adapter_id,org_id,name,protocol,description,enabled,owner,purpose,
                 allowed_actions_json,updated_at,updated_by)
                VALUES(?,?,?,?,?,0,NULL,NULL,?,?,?)""", (
                adapter_id, org_id, definition["name"], definition["protocol"],
                definition["description"], json.dumps(actions), utc_now(), "system",
            ))


def _public(row):
    value = dict(row)
    value["enabled"] = bool(value["enabled"])
    value["allowed_actions"] = json.loads(value.pop("allowed_actions_json"))
    value["manifest"] = {
        "adapter_id": value["adapter_id"],
        "protocol": value["protocol"],
        "inbound_only": True,
        "network_egress": False,
        "arbitrary_code": False,
        "credential_storage": False,
        "requires_registered_agent": True,
        "allowed_actions": value["allowed_actions"],
    }
    return value


def list_adapters(org_id):
    initialize_adapter_control([], org_id)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM adapter_configs WHERE org_id=? ORDER BY name", (org_id,)
        ).fetchall()
        return [_public(row) for row in rows]


def get_adapter(adapter_id, org_id):
    initialize_adapter_control([], org_id)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM adapter_configs WHERE adapter_id=? AND org_id=?", (adapter_id, org_id)
        ).fetchone()
    if row is None:
        raise KeyError("Adapter not found.")
    return _public(row)


def configure_adapter(adapter_id, enabled, owner, purpose, allowed_actions, actor, org_id):
    current = get_adapter(adapter_id, org_id)
    normalized_owner = str(owner or "").strip()
    normalized_purpose = str(purpose or "").strip()
    normalized_actions = sorted({str(action).strip() for action in allowed_actions if str(action).strip()})
    available = AVAILABLE_ACTIONS or set(current["allowed_actions"])
    if not normalized_actions or not set(normalized_actions) <= available:
        raise ValueError("Adapter actions must be a non-empty subset of available actions.")
    if enabled and (len(normalized_owner) < 3 or len(normalized_purpose) < 10):
        raise ValueError("Enabled adapters require a named owner and purpose statement.")
    timestamp = utc_now()
    with sqlite3.connect(database_path) as connection:
        connection.execute("""UPDATE adapter_configs SET enabled=?,owner=?,purpose=?,
            allowed_actions_json=?,updated_at=?,updated_by=? WHERE adapter_id=? AND org_id=?""", (
            int(bool(enabled)), normalized_owner or None, normalized_purpose or None,
            json.dumps(normalized_actions), timestamp, actor, adapter_id, org_id,
        ))
        connection.execute("""INSERT INTO adapter_events
            (adapter_id,timestamp,actor,event_type,detail,org_id) VALUES(?,?,?,?,?,?)""", (
            adapter_id, timestamp, actor,
            "ADAPTER_ENABLED" if enabled else "ADAPTER_DISABLED",
            "Configuration updated; no credentials stored.", org_id,
        ))
    return get_adapter(adapter_id, org_id)


def _redact(value: Any):
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if any(marker in str(key).lower() for marker in SENSITIVE_MARKERS)
            else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def extract_action(adapter_id, payload):
    """Extract only the action needed for authentication without reading config."""
    if not isinstance(payload, dict):
        return ""
    if adapter_id == "mcp_gateway":
        return payload.get("name", "")
    if adapter_id in {"langchain", "crewai"}:
        return payload.get("tool", "")
    if adapter_id == "langgraph":
        return payload.get("action", "")
    if adapter_id == "autogen":
        call = payload.get("function_call", {})
        return call.get("name", "") if isinstance(call, dict) else ""
    return payload.get("action", payload.get("permission", ""))


def translate_request(adapter_id, payload, org_id, require_enabled=True):
    adapter = get_adapter(adapter_id, org_id)
    if require_enabled and not adapter["enabled"]:
        raise PermissionError("Adapter kill switch is active.")
    if not isinstance(payload, dict):
        raise ValueError("Adapter payload must be a JSON object.")
    if adapter_id == "mcp_gateway":
        action = payload.get("name")
        arguments = payload.get("arguments", {})
        target = arguments.get("target", "") if isinstance(arguments, dict) else ""
        dry_run = payload.get("dry_run", False)
    elif adapter_id == "langchain":
        action = payload.get("tool")
        arguments = payload.get("input", {})
        target = payload.get("target", "")
        dry_run = payload.get("dry_run", False)
    elif adapter_id == "langgraph":
        action = payload.get("action")
        arguments = payload.get("state", {})
        target = payload.get("target", "")
        dry_run = payload.get("dry_run", False)
    elif adapter_id == "crewai":
        action = payload.get("tool")
        arguments = payload.get("arguments", {})
        target = payload.get("target", "")
        dry_run = payload.get("dry_run", False)
    elif adapter_id == "autogen":
        function_call = payload.get("function_call", {})
        if not isinstance(function_call, dict):
            raise ValueError("AutoGen function_call must be an object.")
        action = function_call.get("name")
        arguments = function_call.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as error:
                raise ValueError("AutoGen arguments must contain valid JSON.") from error
        target = payload.get("target", "")
        dry_run = payload.get("dry_run", False)
    else:
        action = payload.get("action", payload.get("permission"))
        target = payload.get("target", payload.get("resource", ""))
        arguments = payload.get("payload", payload.get("context", {}))
        dry_run = payload.get("dry_run", payload.get("dryRun", False))
    if not isinstance(action, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,99}", action):
        raise ValueError("Adapter action is invalid.")
    if action not in adapter["allowed_actions"]:
        raise PermissionError("Action is outside the adapter capability manifest.")
    if not isinstance(target, str) or len(target) > 500:
        raise ValueError("Adapter target is invalid.")
    if not isinstance(arguments, dict) or not isinstance(dry_run, bool):
        raise ValueError("Adapter payload or dry-run value is invalid.")
    if len(json.dumps(payload)) > 32_768:
        raise ValueError("Adapter payload exceeds 32 KiB.")
    return {
        "action": action,
        "target": target,
        "payload": _redact(arguments),
        "dry_run": dry_run,
        "adapter_id": adapter_id,
    }


def test_adapter(adapter_id, org_id):
    action = get_adapter(adapter_id, org_id)["allowed_actions"][0]
    samples = {
        "mcp_gateway": {"name": action, "arguments": {}, "dry_run": True},
        "langchain": {"tool": action, "input": {}, "dry_run": True},
        "langgraph": {"action": action, "state": {}, "dry_run": True},
        "crewai": {"tool": action, "arguments": {}, "dry_run": True},
        "autogen": {
            "function_call": {"name": action, "arguments": "{}"},
            "dry_run": True,
        },
    }
    translated = translate_request(
        adapter_id,
        samples.get(adapter_id, {"action": action, "dry_run": True}),
        org_id,
        require_enabled=False,
    )
    return {
        "status": "PASSED",
        "simulated": True,
        "network_used": False,
        "request_persisted": False,
        "translation": translated,
    }
