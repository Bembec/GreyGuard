"""
GreyGuard evaluates AI-agent actions before tools execute them.

Version 10 adds a policy-enforced tool gateway, persistent tool
requests, human approvals, dry runs, replay protection, controlled
execution, and execution evidence.
"""

import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import datetime
from getpass import getpass
from pathlib import Path

from database import (
    claim_tool_request_execution,
    complete_tool_request_execution,
    create_agent_identity as save_agent_identity,
    decide_tool_request,
    get_agent_identities,
    get_agent_identity,
    get_audit_summary,
    get_recent_audit_events,
    get_tool_request,
    get_tool_request_details,
    initialize_database,
    revoke_agent_credential as revoke_stored_credential,
    rotate_agent_credential as rotate_stored_credential,
    save_audit_event,
    save_authentication_event,
    save_blocked_execution_result,
    save_tool_request,
    update_agent_scopes as update_stored_scopes,
)
from tool_gateway import (
    ToolGatewayError,
    execute_tool,
    get_supported_tools,
    initialize_sandbox,
)


permissions = {
    "list_files": "ALLOW",
    "read_file": "ALLOW",
    "search_logs": "ALLOW",
    "write_note": "ASK",
    "delete_file": "ASK",
    "run_program": "ASK",
    "send_email": "BLOCK",
    "view_audit": "ALLOW",
    "audit_summary": "ALLOW",
}

risk_weights = {
    "list_files": 0,
    "read_file": 0,
    "search_logs": 0,
    "write_note": 10,
    "delete_file": 20,
    "run_program": 25,
    "send_email": 40,
    "view_audit": 0,
    "audit_summary": 0,
}

max_blocked_attempts = 3
max_risk_score = 100

credential_prefix = "gg_"
credential_hash_iterations = 310_000

project_path = Path(__file__).parent
log_path = (
    project_path / "greyguard_security.log"
)
state_path = (
    project_path / "greyguard_state.json"
)

agent_states = {}
active_agent_name = ""


class AgentAuthenticationError(Exception):
    """Raised when an agent cannot prove its identity."""


class AgentScopeError(Exception):
    """Raised when an agent lacks an action scope."""


def current_timestamp():
    """Return the current local timestamp."""

    return (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )


def create_agent_state():
    """Create a clean security state."""

    return {
        "agent_status": "ACTIVE",
        "blocked_attempts": 0,
        "risk_score": 0,
    }


def normalize_agent_name(name):
    """Normalize an agent name."""

    return (
        str(name)
        .strip()
        .lower()
        .replace(" ", "_")
    )


def normalize_action(action):
    """Normalize an action name."""

    return (
        str(action)
        .strip()
        .lower()
        .replace(" ", "_")
    )


def get_risk_level(score):
    """Convert a risk score into a level."""

    if score >= 100:
        return "CRITICAL"

    if score >= 60:
        return "HIGH"

    if score >= 20:
        return "MEDIUM"

    return "LOW"


def get_agent_state(agent_name):
    """Return one agent's security state."""

    normalized_name = normalize_agent_name(
        agent_name
    )

    if normalized_name not in agent_states:
        raise KeyError(
            f"Unknown agent: {normalized_name}"
        )

    return agent_states[normalized_name]


def get_current_state():
    """Return the active terminal agent's state."""

    return get_agent_state(
        active_agent_name
    )


def request_human_approval(action):
    """Ask for terminal approval."""

    while True:
        response = input(
            f"Approve '{action}'? Enter yes or no: "
        ).strip().lower()

        if response in ("yes", "y"):
            return "APPROVED"

        if response in ("no", "n"):
            return "DENIED"

        print(
            "Invalid response. Enter yes or no."
        )


def authenticate_admin():
    """Authenticate the terminal administrator."""

    admin_pin = os.getenv(
        "GREYGUARD_ADMIN_PIN"
    )

    if not admin_pin:
        print(
            "Administrator PIN is not configured."
        )
        return False

    entered_pin = getpass(
        "Enter administrator PIN: "
    )

    return hmac.compare_digest(
        entered_pin,
        admin_pin,
    )


def load_state():
    """Load saved multi-agent state."""

    default_data = {
        "active_agent": "default_agent",
        "agents": {
            "default_agent": (
                create_agent_state()
            ),
        },
    }

    if not state_path.exists():
        return default_data

    try:
        with state_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            saved_state = json.load(file)

        if not isinstance(saved_state, dict):
            raise ValueError(
                "Invalid state format."
            )

        if (
            isinstance(
                saved_state.get("agents"),
                dict,
            )
            and saved_state["agents"]
        ):
            return saved_state

        if "agent_status" in saved_state:
            return {
                "active_agent": "legacy_agent",
                "agents": {
                    "legacy_agent": {
                        "agent_status": (
                            saved_state.get(
                                "agent_status",
                                "ACTIVE",
                            )
                        ),
                        "blocked_attempts": (
                            saved_state.get(
                                "blocked_attempts",
                                0,
                            )
                        ),
                        "risk_score": (
                            saved_state.get(
                                "risk_score",
                                0,
                            )
                        ),
                    }
                },
            }

        raise ValueError(
            "Unknown state format."
        )

    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
    ):
        print(
            "Warning: saved state could not be loaded."
        )
        return default_data


def save_state():
    """Save every agent's security state."""

    state_data = {
        "active_agent": active_agent_name,
        "agents": agent_states,
    }

    with state_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            state_data,
            file,
            indent=4,
        )


def initialize_greyguard():
    """Initialize GreyGuard V10."""

    global agent_states
    global active_agent_name

    initialize_database()
    initialize_sandbox()

    saved_state = load_state()

    agent_states = saved_state["agents"]
    active_agent_name = saved_state[
        "active_agent"
    ]

    if active_agent_name not in agent_states:
        agent_states[active_agent_name] = (
            create_agent_state()
        )

    save_state()


def register_agent(agent_name):
    """Register a security state for an agent."""

    normalized_name = normalize_agent_name(
        agent_name
    )

    if not normalized_name:
        raise ValueError(
            "Agent name cannot be empty."
        )

    created = False

    if normalized_name not in agent_states:
        agent_states[normalized_name] = (
            create_agent_state()
        )
        created = True
        save_state()

    return {
        "agent_name": normalized_name,
        "created": created,
        "state": agent_states[
            normalized_name
        ],
    }


def normalize_scopes(scopes):
    """Validate and normalize scopes."""

    if not isinstance(scopes, list):
        raise ValueError(
            "Scopes must be provided as a list."
        )

    normalized_scopes = []

    for scope in scopes:
        normalized_scope = normalize_action(
            scope
        )

        if not normalized_scope:
            continue

        if normalized_scope not in permissions:
            raise ValueError(
                f"Unknown action scope: "
                f"{normalized_scope}"
            )

        if (
            normalized_scope
            not in normalized_scopes
        ):
            normalized_scopes.append(
                normalized_scope
            )

    if not normalized_scopes:
        raise ValueError(
            "At least one valid scope is required."
        )

    return sorted(normalized_scopes)


def generate_agent_credential():
    """Generate a credential shown once."""

    return (
        credential_prefix
        + secrets.token_urlsafe(32)
    )


def generate_credential_salt():
    """Generate a credential salt."""

    return secrets.token_hex(16)


def hash_agent_credential(
    credential,
    credential_salt,
):
    """Create a salted credential hash."""

    if not credential:
        raise ValueError(
            "Credential cannot be empty."
        )

    try:
        salt_bytes = bytes.fromhex(
            credential_salt
        )

    except ValueError as error:
        raise ValueError(
            "Stored credential salt is invalid."
        ) from error

    credential_hash = hashlib.pbkdf2_hmac(
        "sha256",
        credential.encode("utf-8"),
        salt_bytes,
        credential_hash_iterations,
    )

    return credential_hash.hex()


def public_identity(identity):
    """Remove private hash information."""

    if identity is None:
        return None

    return {
        "agent_name": identity["agent_name"],
        "scopes": identity["scopes"],
        "credential_status": identity[
            "credential_status"
        ],
        "created_at": identity["created_at"],
        "rotated_at": identity["rotated_at"],
        "revoked_at": identity["revoked_at"],
    }


def get_public_agent_identity(agent_name):
    """Return one safe identity record."""

    normalized_name = normalize_agent_name(
        agent_name
    )

    identity = get_agent_identity(
        normalized_name
    )

    if identity is None:
        raise KeyError(
            f"Identity not found: "
            f"{normalized_name}"
        )

    return public_identity(identity)


def list_public_agent_identities():
    """Return all safe identity records."""

    return get_agent_identities()


def issue_agent_credential(
    agent_name,
    scopes,
):
    """Create an identity and credential."""

    normalized_name = normalize_agent_name(
        agent_name
    )

    if not normalized_name:
        raise ValueError(
            "Agent name cannot be empty."
        )

    normalized_scopes = normalize_scopes(
        scopes
    )

    if (
        get_agent_identity(
            normalized_name
        )
        is not None
    ):
        raise ValueError(
            "An identity already exists for "
            f"{normalized_name}."
        )

    registration = register_agent(
        normalized_name
    )

    credential = generate_agent_credential()
    credential_salt = (
        generate_credential_salt()
    )
    credential_hash = hash_agent_credential(
        credential,
        credential_salt,
    )

    created = save_agent_identity(
        agent_name=normalized_name,
        credential_salt=credential_salt,
        credential_hash=credential_hash,
        scopes=normalized_scopes,
        timestamp=current_timestamp(),
    )

    if not created:
        raise ValueError(
            "Agent identity could not be created."
        )

    identity = get_agent_identity(
        normalized_name
    )

    return {
        "agent_name": normalized_name,
        "agent_created": registration[
            "created"
        ],
        "credential": credential,
        "credential_notice": (
            "Save this credential now. "
            "GreyGuard will not display it again."
        ),
        "identity": public_identity(identity),
    }


def rotate_agent_credential(agent_name):
    """Replace an agent credential."""

    normalized_name = normalize_agent_name(
        agent_name
    )

    identity = get_agent_identity(
        normalized_name
    )

    if identity is None:
        raise KeyError(
            f"Identity not found: "
            f"{normalized_name}"
        )

    credential = generate_agent_credential()
    credential_salt = (
        generate_credential_salt()
    )
    credential_hash = hash_agent_credential(
        credential,
        credential_salt,
    )

    updated = rotate_stored_credential(
        agent_name=normalized_name,
        credential_salt=credential_salt,
        credential_hash=credential_hash,
        timestamp=current_timestamp(),
    )

    if not updated:
        raise KeyError(
            f"Identity not found: "
            f"{normalized_name}"
        )

    updated_identity = get_agent_identity(
        normalized_name
    )

    return {
        "agent_name": normalized_name,
        "credential": credential,
        "credential_notice": (
            "Save this new credential now. "
            "The previous credential no longer works."
        ),
        "identity": public_identity(
            updated_identity
        ),
    }


def revoke_agent_credential(agent_name):
    """Revoke an agent credential."""

    normalized_name = normalize_agent_name(
        agent_name
    )

    identity = get_agent_identity(
        normalized_name
    )

    if identity is None:
        raise KeyError(
            f"Identity not found: "
            f"{normalized_name}"
        )

    if (
        identity["credential_status"]
        == "REVOKED"
    ):
        return {
            "agent_name": normalized_name,
            "revoked": False,
            "message": (
                "Credential is already revoked."
            ),
            "identity": public_identity(
                identity
            ),
        }

    revoked = revoke_stored_credential(
        agent_name=normalized_name,
        timestamp=current_timestamp(),
    )

    if not revoked:
        raise KeyError(
            f"Identity not found: "
            f"{normalized_name}"
        )

    updated_identity = get_agent_identity(
        normalized_name
    )

    return {
        "agent_name": normalized_name,
        "revoked": True,
        "message": (
            "Agent credential has been revoked."
        ),
        "identity": public_identity(
            updated_identity
        ),
    }


def set_agent_scopes(
    agent_name,
    scopes,
):
    """Replace an identity's scopes."""

    normalized_name = normalize_agent_name(
        agent_name
    )
    normalized_scopes = normalize_scopes(
        scopes
    )

    if (
        get_agent_identity(
            normalized_name
        )
        is None
    ):
        raise KeyError(
            f"Identity not found: "
            f"{normalized_name}"
        )

    updated = update_stored_scopes(
        agent_name=normalized_name,
        scopes=normalized_scopes,
    )

    if not updated:
        raise KeyError(
            f"Identity not found: "
            f"{normalized_name}"
        )

    return public_identity(
        get_agent_identity(
            normalized_name
        )
    )


def record_authentication_event(
    claimed_agent_name,
    authenticated_agent_name,
    action,
    outcome,
    reason,
):
    """Store an authentication event."""

    save_authentication_event(
        timestamp=current_timestamp(),
        claimed_agent_name=(
            claimed_agent_name
        ),
        authenticated_agent_name=(
            authenticated_agent_name
        ),
        action=action,
        outcome=outcome,
        reason=reason,
    )


def authentication_failed(
    claimed_agent_name,
    action,
    reason,
):
    """Record and raise a generic authentication error."""

    record_authentication_event(
        claimed_agent_name=(
            claimed_agent_name
        ),
        authenticated_agent_name=None,
        action=action,
        outcome="AUTHENTICATION_FAILED",
        reason=reason,
    )

    raise AgentAuthenticationError(
        "Agent authentication failed."
    )


def authenticate_agent(
    agent_name,
    credential,
    action=None,
):
    """Authenticate an agent credential."""

    normalized_name = normalize_agent_name(
        agent_name
    )

    if not normalized_name:
        authentication_failed(
            claimed_agent_name=None,
            action=action,
            reason="Agent name was missing.",
        )

    identity = get_agent_identity(
        normalized_name
    )

    if identity is None:
        authentication_failed(
            claimed_agent_name=normalized_name,
            action=action,
            reason=(
                "Agent identity was not found."
            ),
        )

    if (
        identity["credential_status"]
        != "ACTIVE"
    ):
        authentication_failed(
            claimed_agent_name=normalized_name,
            action=action,
            reason=(
                "Agent credential is revoked."
            ),
        )

    if not credential:
        authentication_failed(
            claimed_agent_name=normalized_name,
            action=action,
            reason=(
                "Agent credential was missing."
            ),
        )

    supplied_hash = hash_agent_credential(
        credential,
        identity["credential_salt"],
    )

    if not hmac.compare_digest(
        supplied_hash,
        identity["credential_hash"],
    ):
        authentication_failed(
            claimed_agent_name=normalized_name,
            action=action,
            reason=(
                "Agent credential was invalid."
            ),
        )

    record_authentication_event(
        claimed_agent_name=normalized_name,
        authenticated_agent_name=(
            normalized_name
        ),
        action=action,
        outcome="AUTHENTICATED",
        reason=(
            "Agent credential was verified."
        ),
    )

    return public_identity(identity)


def enforce_agent_scope(
    authenticated_identity,
    action,
):
    """Require the requested action scope."""

    normalized_action = normalize_action(
        action
    )
    agent_name = authenticated_identity[
        "agent_name"
    ]

    if (
        normalized_action
        not in authenticated_identity["scopes"]
    ):
        record_authentication_event(
            claimed_agent_name=agent_name,
            authenticated_agent_name=(
                agent_name
            ),
            action=normalized_action,
            outcome="SCOPE_DENIED",
            reason=(
                "Authenticated agent lacks "
                "the required action scope."
            ),
        )

        raise AgentScopeError(
            "Agent is not authorized for "
            f"scope: {normalized_action}"
        )

    record_authentication_event(
        claimed_agent_name=agent_name,
        authenticated_agent_name=agent_name,
        action=normalized_action,
        outcome="SCOPE_ALLOWED",
        reason=(
            "Authenticated agent has the "
            "required action scope."
        ),
    )

    return normalized_action


def authenticate_and_authorize_agent(
    agent_name,
    credential,
    action,
):
    """Authenticate identity and enforce scope."""

    identity = authenticate_agent(
        agent_name=agent_name,
        credential=credential,
        action=normalize_action(action),
    )

    normalized_action = enforce_agent_scope(
        identity,
        action,
    )

    return {
        "identity": identity,
        "action": normalized_action,
    }


def write_log(
    agent_name,
    action,
    decision,
    approval="NOT_REQUIRED",
    risk_added=0,
):
    """Record one policy event."""

    normalized_name = normalize_agent_name(
        agent_name
    )
    current_state = get_agent_state(
        normalized_name
    )

    timestamp = current_timestamp()
    risk_score = current_state["risk_score"]
    risk_level = get_risk_level(
        risk_score
    )
    agent_status = current_state[
        "agent_status"
    ]
    blocked_attempts = current_state[
        "blocked_attempts"
    ]

    with log_path.open(
        "a",
        encoding="utf-8",
    ) as log:
        log.write(
            f"{timestamp} | "
            f"Agent: {normalized_name} | "
            f"Action: {action} | "
            f"Decision: {decision} | "
            f"Approval: {approval} | "
            f"Risk score: {risk_score} | "
            f"Risk level: {risk_level} | "
            f"Agent status: {agent_status} | "
            f"Blocked attempts: "
            f"{blocked_attempts}\n"
        )

    save_audit_event(
        agent_name=normalized_name,
        timestamp=timestamp,
        action=action,
        decision=decision,
        approval=approval,
        risk_added=risk_added,
        risk_score=risk_score,
        risk_level=risk_level,
        agent_status=agent_status,
        blocked_attempts=blocked_attempts,
    )


def action_result(
    agent_name,
    action,
    policy_decision,
    approval,
    risk_added,
    message,
):
    """Build a policy result."""

    state = get_agent_state(
        agent_name
    )

    return {
        "agent_name": agent_name,
        "action": action,
        "policy_decision": policy_decision,
        "approval": approval,
        "risk_added": risk_added,
        "risk_score": state["risk_score"],
        "risk_level": get_risk_level(
            state["risk_score"]
        ),
        "blocked_attempts": state[
            "blocked_attempts"
        ],
        "agent_status": state[
            "agent_status"
        ],
        "message": message,
    }


def evaluate_action(
    agent_name,
    action,
    approval=None,
):
    """Evaluate one action for an agent."""

    normalized_name = normalize_agent_name(
        agent_name
    )
    normalized_action = normalize_action(
        action
    )
    state = get_agent_state(
        normalized_name
    )

    if state["agent_status"] == "SUSPENDED":
        write_log(
            agent_name=normalized_name,
            action=normalized_action,
            decision="REFUSED",
            approval="NOT_REQUIRED",
            risk_added=0,
        )

        return action_result(
            agent_name=normalized_name,
            action=normalized_action,
            policy_decision="REFUSED",
            approval="NOT_REQUIRED",
            risk_added=0,
            message=(
                "Action refused because the "
                "agent is suspended."
            ),
        )

    policy_decision = permissions.get(
        normalized_action,
        "BLOCK",
    )
    risk_added = risk_weights.get(
        normalized_action,
        50,
    )

    state["risk_score"] += risk_added

    if policy_decision == "ASK":
        if approval in (
            "APPROVED",
            "DENIED",
        ):
            approval_result = approval
        else:
            approval_result = "PENDING"

    else:
        approval_result = "NOT_REQUIRED"

    if policy_decision == "BLOCK":
        state["blocked_attempts"] += 1

    if (
        state["blocked_attempts"]
        >= max_blocked_attempts
        or state["risk_score"]
        >= max_risk_score
    ):
        state["agent_status"] = "SUSPENDED"

    save_state()

    write_log(
        agent_name=normalized_name,
        action=normalized_action,
        decision=policy_decision,
        approval=approval_result,
        risk_added=risk_added,
    )

    if policy_decision == "ALLOW":
        message = "Action allowed by policy."

    elif policy_decision == "ASK":
        if approval_result == "APPROVED":
            message = (
                "Action approved by a human."
            )

        elif approval_result == "DENIED":
            message = (
                "Action denied by a human."
            )

        else:
            message = (
                "Action requires human approval."
            )

    else:
        message = "Action blocked by policy."

    if state["agent_status"] == "SUSPENDED":
        message += (
            " Agent reached a security "
            "threshold and is now suspended."
        )

    return action_result(
        agent_name=normalized_name,
        action=normalized_action,
        policy_decision=policy_decision,
        approval=approval_result,
        risk_added=risk_added,
        message=message,
    )


def execute_saved_tool_request(request_id):
    """Execute one authorized saved request."""

    request = get_tool_request(
        request_id
    )

    if request is None:
        raise KeyError(
            f"Tool request not found: "
            f"{request_id}"
        )

    if request["policy_decision"] not in (
        "ALLOW",
        "ASK",
    ):
        result = {
            "success": False,
            "message": (
                "Policy does not permit execution."
            ),
        }

        save_blocked_execution_result(
            request_id=request_id,
            timestamp=current_timestamp(),
            result=result,
        )

        return get_tool_request_details(
            request_id
        )

    if (
        request["policy_decision"] == "ASK"
        and request["approval_status"]
        != "APPROVED"
    ):
        return get_tool_request_details(
            request_id
        )

    claimed = claim_tool_request_execution(
        request_id=request_id,
        timestamp=current_timestamp(),
    )

    if not claimed:
        return get_tool_request_details(
            request_id
        )

    try:
        result = execute_tool(
            action=request["action"],
            target=request["target"],
            payload=request["payload"],
            dry_run=request["dry_run"],
        )
        execution_status = ("DRY_RUN" if request["dry_run"] else "SUCCEEDED")

    except ToolGatewayError as error:
        execution_status = "FAILED"
        result = {
            "success": False,
            "error": str(error),
        }

    except Exception:
        execution_status = "FAILED"
        result = {
            "success": False,
            "error": (
                "Controlled tool execution failed."
            ),
        }

    complete_tool_request_execution(
        request_id=request_id,
        timestamp=current_timestamp(),
        execution_status=execution_status,
        result=result,
    )

    return get_tool_request_details(
        request_id
    )


def submit_tool_request(
    agent_name,
    action,
    target="",
    payload=None,
    dry_run=False,
):
    """Create and process a tool request."""

    normalized_name = normalize_agent_name(
        agent_name
    )
    normalized_action = normalize_action(
        action
    )

    if payload is None:
        payload = {}

    if not isinstance(payload, dict):
        raise ValueError(
            "Tool payload must be a JSON object."
        )

    if not isinstance(target, str):
        raise ValueError(
            "Tool target must be a string."
        )

    if not isinstance(dry_run, bool):
        raise ValueError(
            "Dry-run must be true or false."
        )

    policy_result = evaluate_action(
        agent_name=normalized_name,
        action=normalized_action,
    )

    policy_decision = policy_result[
        "policy_decision"
    ]
    approval_status = policy_result[
        "approval"
    ]

    if (
        normalized_action
        not in get_supported_tools()
    ):
        execution_status = "BLOCKED"

    elif policy_decision == "ALLOW":
        execution_status = "NOT_STARTED"

    elif policy_decision == "ASK":
        execution_status = (
            "NOT_STARTED"
        )

    else:
        execution_status = "BLOCKED"

    request_id = str(uuid.uuid4())

    save_tool_request(
        request_id=request_id,
        agent_name=normalized_name,
        timestamp=current_timestamp(),
        action=normalized_action,
        target=target.strip(),
        payload=payload,
        dry_run=dry_run,
        policy_decision=policy_decision,
        approval_status=approval_status,
        execution_status=execution_status,
        risk_added=policy_result[
            "risk_added"
        ],
        risk_score=policy_result[
            "risk_score"
        ],
    )

    if execution_status == "BLOCKED":
        save_blocked_execution_result(
            request_id=request_id,
            timestamp=current_timestamp(),
            result={
                "success": False,
                "message": (
                    "Tool execution was blocked."
                ),
            },
        )

        return get_tool_request_details(
            request_id
        )

    if execution_status == "NOT_STARTED":
        return execute_saved_tool_request(
            request_id
        )

    return get_tool_request_details(
        request_id
    )


def review_tool_request(
    request_id,
    actor,
    decision,
    note=None,
):
    """Approve or deny a pending tool request."""

    normalized_decision = (
        str(decision)
        .strip()
        .upper()
    )

    if normalized_decision not in (
        "APPROVED",
        "DENIED",
    ):
        raise ValueError(
            "Decision must be APPROVED or DENIED."
        )

    request = get_tool_request(
        request_id
    )

    if request is None:
        raise KeyError(
            f"Tool request not found: "
            f"{request_id}"
        )

    if (
        request["approval_status"]
        != "PENDING"
    ):
        raise ValueError(
            "Tool request is no longer "
            "awaiting approval."
        )

    changed = decide_tool_request(
        request_id=request_id,
        timestamp=current_timestamp(),
        actor=(
            str(actor).strip()
            or "administrator"
        ),
        decision=normalized_decision,
        note=note,
    )

    if not changed:
        raise ValueError(
            "Tool request could not be reviewed."
        )

    if normalized_decision == "APPROVED":
        return execute_saved_tool_request(
            request_id
        )

    return get_tool_request_details(
        request_id
    )


def reset_agent(agent_name):
    """Reset one suspended agent."""

    normalized_name = normalize_agent_name(
        agent_name
    )
    state = get_agent_state(
        normalized_name
    )

    if state["agent_status"] == "ACTIVE":
        write_log(
            agent_name=normalized_name,
            action="reset",
            decision="RESET",
            approval="NOT_REQUIRED",
            risk_added=0,
        )

        return {
            "agent_name": normalized_name,
            "reset": False,
            "message": (
                "Reset is not required because "
                "the agent is already active."
            ),
            "state": state,
        }

    state["agent_status"] = "ACTIVE"
    state["blocked_attempts"] = 0
    state["risk_score"] = 0

    save_state()

    write_log(
        agent_name=normalized_name,
        action="reset",
        decision="RESET",
        approval="APPROVED",
        risk_added=0,
    )

    return {
        "agent_name": normalized_name,
        "reset": True,
        "message": (
            "Agent has been manually reset."
        ),
        "state": state,
    }


def display_agents():
    """Display registered agents."""

    print(
        "\nGreyGuard - Registered Agents"
    )

    for agent_name, state in sorted(
        agent_states.items()
    ):
        marker = ""

        if agent_name == active_agent_name:
            marker = " (CURRENT)"

        print(
            f"{agent_name}{marker} | "
            f"Status: "
            f"{state['agent_status']} | "
            f"Risk: {state['risk_score']} "
            f"("
            f"{get_risk_level(state['risk_score'])}"
            f") | "
            f"Blocked: "
            f"{state['blocked_attempts']}"
        )


def switch_agent():
    """Switch the terminal agent."""

    global active_agent_name

    entered_name = input(
        "Enter the agent name: "
    ).strip()

    registration = register_agent(
        entered_name
    )

    active_agent_name = registration[
        "agent_name"
    ]

    save_state()

    if registration["created"]:
        print(
            "New agent registered:",
            active_agent_name,
        )

    print(
        "Active agent changed to:",
        active_agent_name,
    )


def display_recent_audit_events():
    """Display recent agent audit events."""

    events = get_recent_audit_events(
        active_agent_name,
        limit=5,
    )

    print(
        "\nGreyGuard - Recent Audit Events:",
        active_agent_name,
    )

    if not events:
        print(
            "No audit events found."
        )
        return

    for event in events:
        print(
            f"{event[1]} | "
            f"Action: {event[2]} | "
            f"Decision: {event[3]} | "
            f"Approval: {event[4]} | "
            f"Risk: {event[5]} "
            f"({event[6]}) | "
            f"Status: {event[7]}"
        )


def display_audit_summary():
    """Display the current agent's summary."""

    summary = get_audit_summary(
        active_agent_name
    )

    print(
        "\nGreyGuard - Audit Summary:",
        active_agent_name,
    )

    for name, value in summary.items():
        print(
            name.replace("_", " ").title(),
            ":",
            value,
        )


def display_action_result(result):
    """Display an action evaluation."""

    print(
        "Policy decision:",
        result["policy_decision"],
    )
    print(
        "Approval:",
        result["approval"],
    )
    print(
        "Risk added:",
        result["risk_added"],
    )
    print(
        "Risk score:",
        result["risk_score"],
    )
    print(
        "Risk level:",
        result["risk_level"],
    )
    print(
        "Agent status:",
        result["agent_status"],
    )
    print(
        "Message:",
        result["message"],
    )


def run_cli():
    """Start the GreyGuard terminal interface."""

    global active_agent_name

    initialize_greyguard()

    print(
        "GreyGuard V10 multi-agent state loaded."
    )
    print(
        "Active agent:",
        active_agent_name,
    )

    while True:
        state = get_current_state()

        print(
            "\nActive agent:",
            active_agent_name,
        )
        print(
            "Agent status:",
            state["agent_status"],
        )
        print(
            "Risk score:",
            state["risk_score"],
        )

        action = input(
            "Enter an action, 'list_agents', "
            "'switch_agent', 'recent_audit', "
            "'audit_summary', 'reset', or "
            "'quit': "
        ).strip().lower()

        if action == "quit":
            save_state()
            print(
                "GreyGuard state saved."
            )
            print(
                "GreyGuard closed."
            )
            break

        if action == "list_agents":
            display_agents()
            continue

        if action == "switch_agent":
            try:
                switch_agent()

            except ValueError as error:
                print(error)

            continue

        if action == "recent_audit":
            display_recent_audit_events()
            continue

        if action == "audit_summary":
            display_audit_summary()
            continue

        if action == "reset":
            if state["agent_status"] == "ACTIVE":
                result = reset_agent(
                    active_agent_name
                )
                print(result["message"])
                continue

            if authenticate_admin():
                result = reset_agent(
                    active_agent_name
                )
                print(result["message"])

            else:
                print(
                    "Reset denied."
                )

            continue

        normalized_action = normalize_action(
            action
        )
        policy = permissions.get(
            normalized_action,
            "BLOCK",
        )
        approval = None

        if (
            policy == "ASK"
            and state["agent_status"]
            == "ACTIVE"
        ):
            approval = request_human_approval(
                normalized_action
            )

        result = evaluate_action(
            agent_name=active_agent_name,
            action=normalized_action,
            approval=approval,
        )

        display_action_result(result)


if __name__ == "__main__":
    run_cli()