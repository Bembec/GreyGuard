"""
GreyGuard V9 FastAPI control plane.

Agent requests must authenticate with an agent name and credential.
Authenticated identities must also possess the requested action scope.
"""

import hmac
import os
from typing import Literal

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Query,
)
from pydantic import BaseModel, Field

import main
from database import (
    get_audit_summary,
    get_recent_audit_events,
    get_recent_authentication_events,
)


app = FastAPI(
    title="GreyGuard Control Plane API",
    description=(
        "A multi-agent identity, scope, "
        "permission, risk, suspension, "
        "and audit control plane."
    ),
    version="9.0",
)


class AgentRegistration(BaseModel):
    """Information required to register an identity."""

    agent_name: str = Field(
        min_length=1,
        max_length=100,
        examples=["research_agent"],
    )

    scopes: list[str] = Field(
        min_length=1,
        examples=[
            [
                "read_file",
                "search_logs",
            ]
        ],
    )


class ScopeUpdate(BaseModel):
    """Replacement scopes for an agent."""

    scopes: list[str] = Field(
        min_length=1,
        examples=[
            [
                "read_file",
                "search_logs",
                "view_audit",
            ]
        ],
    )


class ActionRequest(BaseModel):
    """An action requested by an authenticated agent."""

    action: str = Field(
        min_length=1,
        max_length=100,
        examples=["read_file"],
    )

    approval: Literal[
        "APPROVED",
        "DENIED",
    ] | None = Field(
        default=None,
        description=(
            "Human decision for an action "
            "whose policy is ASK."
        ),
        examples=["APPROVED"],
    )


@app.on_event("startup")
def startup_event():
    """Initialize GreyGuard when the API starts."""

    main.initialize_greyguard()


def require_admin(
    x_admin_pin: str | None,
):
    """Verify the administrative API PIN."""

    configured_pin = os.getenv(
        "GREYGUARD_ADMIN_PIN"
    )

    if not configured_pin:
        raise HTTPException(
            status_code=503,
            detail=(
                "Administrator PIN is not "
                "configured."
            ),
        )

    if not x_admin_pin:
        raise HTTPException(
            status_code=401,
            detail=(
                "Administrator authentication "
                "is required."
            ),
        )

    if not hmac.compare_digest(
        x_admin_pin,
        configured_pin,
    ):
        raise HTTPException(
            status_code=401,
            detail=(
                "Administrator authentication "
                "failed."
            ),
        )


def serialize_agent(
    agent_name,
    state,
):
    """Convert an agent state into API data."""

    identity = None

    try:
        identity = (
            main.get_public_agent_identity(
                agent_name
            )
        )
    except KeyError:
        identity = None

    return {
        "agent_name": agent_name,
        "agent_status": state[
            "agent_status"
        ],
        "risk_score": state["risk_score"],
        "risk_level": main.get_risk_level(
            state["risk_score"]
        ),
        "blocked_attempts": state[
            "blocked_attempts"
        ],
        "identity": identity,
    }


def authenticate_request(
    x_agent_name,
    x_agent_key,
    action,
):
    """Authenticate an agent and enforce scope."""

    try:
        return (
            main.authenticate_and_authorize_agent(
                agent_name=x_agent_name,
                credential=x_agent_key,
                action=action,
            )
        )

    except main.AgentAuthenticationError as error:
        raise HTTPException(
            status_code=401,
            detail=str(error),
            headers={
                "WWW-Authenticate": (
                    "AgentCredential"
                )
            },
        ) from error

    except main.AgentScopeError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error


def authenticate_agent_owner(
    requested_agent_name,
    x_agent_name,
    x_agent_key,
    required_scope,
):
    """Authenticate an agent accessing its own data."""

    try:
        identity = main.authenticate_agent(
            agent_name=x_agent_name,
            credential=x_agent_key,
            action=required_scope,
        )

    except main.AgentAuthenticationError as error:
        raise HTTPException(
            status_code=401,
            detail=str(error),
            headers={
                "WWW-Authenticate": (
                    "AgentCredential"
                )
            },
        ) from error

    normalized_requested_name = (
        main.normalize_agent_name(
            requested_agent_name
        )
    )

    if (
        identity["agent_name"]
        != normalized_requested_name
    ):
        main.record_authentication_event(
            claimed_agent_name=(
                identity["agent_name"]
            ),
            authenticated_agent_name=(
                identity["agent_name"]
            ),
            action=required_scope,
            outcome="RESOURCE_DENIED",
            reason=(
                "Agent attempted to access "
                "another agent's records."
            ),
        )

        raise HTTPException(
            status_code=403,
            detail=(
                "Authenticated agent cannot "
                "access another agent's records."
            ),
        )

    try:
        main.enforce_agent_scope(
            identity,
            required_scope,
        )

    except main.AgentScopeError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error

    return identity


@app.get("/")
def home():
    """Return basic GreyGuard information."""

    return {
        "application": "GreyGuard",
        "version": "9.0",
        "status": "running",
        "purpose": (
            "Multi-agent identity, permission, "
            "and security control plane"
        ),
        "documentation": "/docs",
    }


@app.get("/health")
def health():
    """Return API health information."""

    return {
        "status": "healthy",
        "version": "9.0",
        "registered_agents": len(
            main.agent_states
        ),
        "registered_identities": len(
            main.list_public_agent_identities()
        ),
    }


@app.get("/permissions")
def permissions():
    """Return the available action policy."""

    return {
        "permissions": main.permissions,
        "risk_weights": main.risk_weights,
        "available_scopes": sorted(
            main.permissions.keys()
        ),
        "max_blocked_attempts": (
            main.max_blocked_attempts
        ),
        "max_risk_score": (
            main.max_risk_score
        ),
    }


@app.get("/agents")
def list_agents(
    x_admin_pin: str | None = Header(
        default=None,
    ),
):
    """Return every agent to an administrator."""

    require_admin(x_admin_pin)

    return [
        serialize_agent(
            agent_name,
            state,
        )
        for agent_name, state in sorted(
            main.agent_states.items()
        )
    ]


@app.post(
    "/agents",
    status_code=201,
)
def register_agent_identity(
    registration: AgentRegistration,
    x_admin_pin: str | None = Header(
        default=None,
    ),
):
    """Register an agent and issue its credential."""

    require_admin(x_admin_pin)

    try:
        return main.issue_agent_credential(
            agent_name=(
                registration.agent_name
            ),
            scopes=registration.scopes,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@app.get("/agents/{agent_name}")
def get_agent(
    agent_name: str,
    x_admin_pin: str | None = Header(
        default=None,
    ),
):
    """Return one agent to an administrator."""

    require_admin(x_admin_pin)

    normalized_name = (
        main.normalize_agent_name(agent_name)
    )

    try:
        state = main.get_agent_state(
            normalized_name
        )

    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    return serialize_agent(
        normalized_name,
        state,
    )


@app.put("/agents/{agent_name}/scopes")
def update_agent_scopes(
    agent_name: str,
    update: ScopeUpdate,
    x_admin_pin: str | None = Header(
        default=None,
    ),
):
    """Replace an agent's permission scopes."""

    require_admin(x_admin_pin)

    try:
        identity = main.set_agent_scopes(
            agent_name=agent_name,
            scopes=update.scopes,
        )

    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return {
        "updated": True,
        "identity": identity,
    }


@app.post(
    "/agents/{agent_name}/credential/rotate"
)
def rotate_credential(
    agent_name: str,
    x_admin_pin: str | None = Header(
        default=None,
    ),
):
    """Rotate an agent credential."""

    require_admin(x_admin_pin)

    try:
        return main.rotate_agent_credential(
            agent_name
        )

    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error


@app.post(
    "/agents/{agent_name}/credential/revoke"
)
def revoke_credential(
    agent_name: str,
    x_admin_pin: str | None = Header(
        default=None,
    ),
):
    """Revoke an agent credential."""

    require_admin(x_admin_pin)

    try:
        return main.revoke_agent_credential(
            agent_name
        )

    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error


@app.post("/actions/evaluate")
def evaluate_action(
    request: ActionRequest,
    x_agent_name: str | None = Header(
        default=None,
    ),
    x_agent_key: str | None = Header(
        default=None,
    ),
):
    """Authenticate and evaluate an agent action."""

    authentication = authenticate_request(
        x_agent_name=x_agent_name,
        x_agent_key=x_agent_key,
        action=request.action,
    )

    authenticated_name = (
        authentication["identity"][
            "agent_name"
        ]
    )

    try:
        result = main.evaluate_action(
            agent_name=authenticated_name,
            action=authentication["action"],
            approval=request.approval,
        )

    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    return {
        "identity_authenticated": True,
        "scope_authorized": True,
        **result,
    }


@app.get("/agents/{agent_name}/audit")
def recent_audit_events(
    agent_name: str,
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    x_agent_name: str | None = Header(
        default=None,
    ),
    x_agent_key: str | None = Header(
        default=None,
    ),
):
    """Return an authenticated agent's audit events."""

    authenticate_agent_owner(
        requested_agent_name=agent_name,
        x_agent_name=x_agent_name,
        x_agent_key=x_agent_key,
        required_scope="view_audit",
    )

    events = get_recent_audit_events(
        main.normalize_agent_name(
            agent_name
        ),
        limit=limit,
    )

    return [
        {
            "agent_name": event[0],
            "timestamp": event[1],
            "action": event[2],
            "decision": event[3],
            "approval": event[4],
            "risk_score": event[5],
            "risk_level": event[6],
            "agent_status": event[7],
        }
        for event in events
    ]


@app.get("/agents/{agent_name}/summary")
def audit_summary(
    agent_name: str,
    x_agent_name: str | None = Header(
        default=None,
    ),
    x_agent_key: str | None = Header(
        default=None,
    ),
):
    """Return an authenticated agent's summary."""

    authenticate_agent_owner(
        requested_agent_name=agent_name,
        x_agent_name=x_agent_name,
        x_agent_key=x_agent_key,
        required_scope="audit_summary",
    )

    normalized_name = (
        main.normalize_agent_name(agent_name)
    )

    summary = get_audit_summary(
        normalized_name
    )

    return {
        "agent_name": normalized_name,
        **summary,
    }


@app.get(
    "/agents/{agent_name}/authentication-events"
)
def authentication_events(
    agent_name: str,
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    x_admin_pin: str | None = Header(
        default=None,
    ),
):
    """Return authentication events to an admin."""

    require_admin(x_admin_pin)

    normalized_name = (
        main.normalize_agent_name(agent_name)
    )

    return get_recent_authentication_events(
        normalized_name,
        limit=limit,
    )


@app.post("/agents/{agent_name}/reset")
def reset_agent(
    agent_name: str,
    x_admin_pin: str | None = Header(
        default=None,
    ),
):
    """Administratively reset one agent."""

    require_admin(x_admin_pin)

    normalized_name = (
        main.normalize_agent_name(agent_name)
    )

    try:
        result = main.reset_agent(
            normalized_name
        )

    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    return {
        "agent_name": result["agent_name"],
        "reset": result["reset"],
        "message": result["message"],
        "state": serialize_agent(
            result["agent_name"],
            result["state"],
        ),
    }