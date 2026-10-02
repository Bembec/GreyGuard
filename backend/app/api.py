"""
GreyGuard V10 FastAPI control plane.

Agent requests must authenticate with an agent name and credential.
Each authenticated identity must possess the requested action scope.

V10 adds persistent controlled-tool requests, sandbox execution,
human approval decisions, dry runs, replay protection, and evidence.
"""

from contextlib import asynccontextmanager

import hmac
import os
from typing import Literal

from fastapi import (
    Request,
    FastAPI,
    Header,
    HTTPException,
    Query,
)
from fastapi.responses import Response, StreamingResponse
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import main
from .admin_auth import (
    authenticate as authenticate_administrator,
    create_administrator,
    get_administrator,
    reset_administrator_password,
    revoke_administrator_sessions,
    update_administrator,
    has_permission,
    initialize_admin_auth,
    list_administrators,
    required_permission,
    revoke_session,
    validate_session,
)
from .database import (
    get_audit_summary,
    get_recent_authentication_events,
    get_recent_audit_events,
    get_tool_request_details,
    get_tool_requests,
)


from .policy_control import (
    approve_policy,
    create_policy_draft,
    create_rollback_draft,
    get_policy_history,
    get_policy_version,
    get_published_policy,
    initialize_policy_control,
    list_policy_versions,
    reject_policy,
    submit_policy,
    update_policy_draft,
)
from .live_events import stream_administrator_events
from .alerts import (
    add_alert_note,
    alert_summary,
    get_alert,
    get_alerts,
    initialize_alert_database,
    update_alert,
)
from .secret_manager import (
    create_secret, initialize_secret_manager, list_secrets,
    redact, revoke_secret, rotate_secret,
)
from .notifications import (
    initialize_notification_database,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    notification_summary,
)
from .service_accounts import (
    AVAILABLE_SCOPES,
    authenticate_service_key,
    create_service_account,
    initialize_service_accounts,
    list_service_accounts,
    revoke_service_account,
    rotate_service_account_key,
)
from .compliance_reports import (
    create_compliance_report,
    export_csv,
    export_json,
    get_compliance_report,
    initialize_compliance_reports,
    list_compliance_reports,
)
from .abuse_protection import (
    abuse_summary,
    check_rate_limit,
    clear_authentication_failures,
    initialize_abuse_protection,
    list_abuse_events,
    list_policies as list_rate_limit_policies,
    record_authentication_failure,
    update_policy as update_rate_limit_policy,
)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize GreyGuard for the API lifecycle."""

    main.initialize_greyguard()
    initialize_policy_control(
        permissions=main.permissions,
        risk_weights=main.risk_weights,
        max_blocked_attempts=(
            main.max_blocked_attempts
        ),
        max_risk_score=main.max_risk_score,
    )
    initialize_alert_database()
    initialize_secret_manager()
    initialize_notification_database()
    initialize_service_accounts()
    initialize_compliance_reports()
    initialize_abuse_protection()

    yield


app = FastAPI(
    lifespan=lifespan,
    title="GreyGuard Control Plane API",
    description=(
        "A multi-agent identity, scope, policy, "
        "risk, approval, controlled-tool, "
        "suspension, and audit control plane."
    ),
    version="10.0",
)


@app.middleware("http")
async def enforce_administrator_rbac(request: Request, call_next):
    """Enforce the signed-in operator's role before protected API execution."""
    path = request.url.path
    client_host = request.client.host if request.client else "unknown-client"
    if path == "/auth/login":
        rate_category = "ADMIN_AUTH"
        rate_identifier = client_host
    elif path == "/service-accounts/verify":
        rate_category = "SERVICE_ACCOUNT"
        rate_identifier = request.headers.get("x-service-key", client_host)
    elif path.startswith("/actions") or path.startswith("/tool-requests"):
        rate_category = "AGENT_ACTION"
        rate_identifier = request.headers.get("x-agent-name", client_host)
    else:
        rate_category = "GENERAL"
        rate_identifier = client_host
    rate_decision = check_rate_limit(rate_identifier, rate_category)
    if not rate_decision["allowed"]:
        return JSONResponse(
            status_code=429,
            content={"detail": "Request rate limit exceeded. Try again later."},
            headers={"Retry-After": str(rate_decision["retry_after"])},
        )
    credential = request.headers.get("x-admin-pin", "")
    if credential.startswith("gga_"):
        try:
            administrator = validate_session(credential)
        except ValueError as error:
            return JSONResponse(status_code=401, content={"detail": str(error)})
        request.state.administrator = administrator
        if request.url.path not in {"/auth/me", "/auth/logout"}:
            permission = required_permission(request.method, request.url.path)
            if not has_permission(administrator, permission):
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"Role {administrator['role']} lacks permission: {permission}"},
                )
    response = await call_next(request)
    response.headers["X-RateLimit-Remaining"] = str(rate_decision["remaining"])
    if path == "/auth/login":
        if response.status_code == 200:
            clear_authentication_failures(client_host, "ADMIN_AUTH")
        elif response.status_code == 401:
            record_authentication_failure(client_host, "ADMIN_AUTH")
    return response


class AgentRegistration(BaseModel):
    """Information required to register an agent."""

    agent_name: str = Field(
        min_length=1,
        max_length=100,
        examples=["research_agent"],
    )

    scopes: list[str] = Field(
        min_length=1,
        examples=[
            [
                "list_files",
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
                "list_files",
                "read_file",
                "search_logs",
                "write_note",
                "view_audit",
            ]
        ],
    )


class AdministratorLogin(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class AdministratorCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=1, max_length=100)
    role: Literal["PLATFORM_ADMIN", "SECURITY_ANALYST", "AUDITOR"]
    password: str = Field(min_length=12, max_length=256)


class AdministratorUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: Literal["PLATFORM_ADMIN", "SECURITY_ANALYST", "AUDITOR"] | None = None
    status: Literal["ACTIVE", "DISABLED"] | None = None


class AdministratorPasswordReset(BaseModel):
    new_password: str = Field(min_length=12, max_length=256)


class PolicyDocumentRequest(BaseModel):
    """A complete editable GreyGuard policy document."""

    permissions: dict[str, Literal["ALLOW", "ASK", "BLOCK"]]
    risk_weights: dict[str, int]
    max_blocked_attempts: int = Field(ge=1, le=100)
    max_risk_score: int = Field(ge=1, le=10_000)
    change_summary: str = Field(min_length=1, max_length=1000)


class SecretCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    reference: str = Field(min_length=3, max_length=128)


class SecretRotateRequest(BaseModel):
    reference: str = Field(min_length=3, max_length=128)


class ServiceAccountCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    description: str = Field(default="", max_length=500)
    scopes: list[str] = Field(min_length=1)
    expires_in_days: int | None = Field(default=90, ge=1, le=365)


class ServiceAccountRotateRequest(BaseModel):
    expires_in_days: int | None = Field(default=90, ge=1, le=365)


class ComplianceReportRequest(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    date_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_to: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    severities: list[Literal["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]] = Field(default_factory=list)
    event_types: list[Literal["POLICY", "AUTHENTICATION", "APPROVAL", "EXECUTION"]] = Field(default_factory=list)


class RateLimitPolicyRequest(BaseModel):
    enabled: bool
    request_limit: int = Field(ge=1, le=10_000)
    window_seconds: int = Field(ge=1, le=86_400)
    block_seconds: int = Field(ge=1, le=86_400)
    max_failed_attempts: int = Field(ge=1, le=100)


class ActionRequest(BaseModel):
    """An action requested by an agent."""

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
            "Human decision for a legacy "
            "policy-evaluation request."
        ),
        examples=["APPROVED"],
    )


class ToolRequestCreate(BaseModel):
    """A controlled tool request."""

    action: str = Field(
        min_length=1,
        max_length=100,
        examples=["read_file"],
    )

    target: str = Field(
        default="",
        max_length=500,
        examples=["public_report.txt"],
    )

    payload: dict = Field(
        default_factory=dict,
        examples=[{}],
    )

    dry_run: bool = Field(
        default=False,
        description=(
            "Preview the operation without "
            "changing sandbox files."
        ),
    )


class AlertUpdateRequest(BaseModel):
    """Administrator alert workflow update."""

    status: Literal["OPEN", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "DISMISSED"]
    assigned_to: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=2000)


class AlertNoteRequest(BaseModel):
    """Administrator investigation note."""

    note: str = Field(min_length=1, max_length=2000)


class ToolApprovalDecision(BaseModel):
    """An administrator's approval decision."""

    decision: Literal[
        "APPROVED",
        "DENIED",
    ]

    note: str | None = Field(
        default=None,
        max_length=1000,
        examples=[
            "Approved after reviewing the target."
        ],
    )


def require_admin(x_admin_pin: str | None):
    """Authenticate a named administrator session or the temporary legacy PIN."""
    if not x_admin_pin:
        raise HTTPException(
            status_code=401,
            detail="Administrator authentication is required.",
        )
    if x_admin_pin.startswith("gga_"):
        try:
            return validate_session(x_admin_pin)
        except ValueError as error:
            raise HTTPException(status_code=401, detail=str(error)) from error
    configured_pin = os.getenv("GREYGUARD_ADMIN_PIN")
    if configured_pin and x_admin_pin and hmac.compare_digest(x_admin_pin, configured_pin):
        return {"admin_id": "legacy", "email": "legacy", "display_name": "Legacy Administrator", "role": "PLATFORM_ADMIN", "permissions": ["admin:manage", "approval:manage", "identity:manage", "incident:manage", "read"]}
    raise HTTPException(status_code=401, detail="Administrator authentication failed.")


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

    except (
        main.AgentAuthenticationError
    ) as error:
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
    """Authenticate an agent accessing its records."""

    authentication = authenticate_request(
        x_agent_name=x_agent_name,
        x_agent_key=x_agent_key,
        action=required_scope,
    )

    identity = authentication["identity"]

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

    return identity


@app.post("/auth/login")
def administrator_login(credentials: AdministratorLogin):
    try:
        return authenticate_administrator(credentials.email, credentials.password)
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


@app.get("/auth/me")
def current_administrator(x_admin_pin: str | None = Header(default=None)):
    return require_admin(x_admin_pin)


@app.post("/auth/logout")
def administrator_logout(x_admin_pin: str | None = Header(default=None)):
    administrator = require_admin(x_admin_pin)
    if x_admin_pin and x_admin_pin.startswith("gga_"):
        revoke_session(x_admin_pin)
    return {"logged_out": True, "administrator": administrator["email"]}


@app.get("/administrators")
def administrators(x_admin_pin: str | None = Header(default=None)):
    actor = require_admin(x_admin_pin)
    if not has_permission(actor, "admin:manage"):
        raise HTTPException(status_code=403, detail="Platform administrator role is required.")
    return {"administrators": list_administrators(), "count": len(list_administrators())}


@app.post("/administrators", status_code=201)
def register_administrator(registration: AdministratorCreate, x_admin_pin: str | None = Header(default=None)):
    actor = require_admin(x_admin_pin)
    if not has_permission(actor, "admin:manage"):
        raise HTTPException(status_code=403, detail="Platform administrator role is required.")
    try:
        return create_administrator(registration.email, registration.display_name, registration.role, registration.password)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.put("/administrators/{admin_id}")
def edit_administrator(admin_id: str, update: AdministratorUpdate, x_admin_pin: str | None = Header(default=None)):
    actor = require_admin(x_admin_pin)
    if not has_permission(actor, "admin:manage"):
        raise HTTPException(status_code=403, detail="Platform administrator role is required.")
    try:
        return update_administrator(admin_id, update.display_name, update.role, update.status)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/administrators/{admin_id}/password")
def reset_admin_password(admin_id: str, reset: AdministratorPasswordReset, x_admin_pin: str | None = Header(default=None)):
    actor = require_admin(x_admin_pin)
    if not has_permission(actor, "admin:manage"):
        raise HTTPException(status_code=403, detail="Platform administrator role is required.")
    try:
        return reset_administrator_password(admin_id, reset.new_password)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/administrators/{admin_id}/sessions/revoke")
def revoke_admin_sessions(admin_id: str, x_admin_pin: str | None = Header(default=None)):
    actor = require_admin(x_admin_pin)
    if not has_permission(actor, "admin:manage"):
        raise HTTPException(status_code=403, detail="Platform administrator role is required.")
    try:
        return {"admin_id": admin_id, "revoked_sessions": revoke_administrator_sessions(admin_id)}
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/")
def home():
    """Return basic GreyGuard information."""

    return {
        "application": "GreyGuard",
        "version": "10.0",
        "status": "running",
        "purpose": (
            "Multi-agent identity, permission, "
            "and controlled-tool security"
        ),
        "documentation": "/docs",
    }


@app.get("/health")
def health():
    """Return API health information."""

    return {
        "status": "healthy",
        "version": "10.0",
        "registered_agents": len(
            main.agent_states
        ),
        "registered_identities": len(
            main.list_public_agent_identities()
        ),
        "controlled_tools": len(
            main.get_supported_tools()
        ),
        "sandbox_initialized": True,
    }


def require_policy_editor(x_admin_pin):
    """Allow Platform Admins and Security Analysts to edit drafts."""

    administrator = require_admin(x_admin_pin)

    if administrator["role"] not in {
        "PLATFORM_ADMIN",
        "SECURITY_ANALYST",
    }:
        raise HTTPException(
            status_code=403,
            detail="This role cannot modify policy drafts.",
        )

    return administrator


def policy_actor(administrator):
    """Return a stable administrator audit identity."""

    return administrator.get("admin_id") or administrator["email"]


@app.post("/policy-versions/drafts", status_code=201)
def create_policy_version_draft(
    payload: PolicyDocumentRequest,
    x_admin_pin: str | None = Header(default=None),
):
    """Create an isolated policy draft."""

    administrator = require_policy_editor(x_admin_pin)

    try:
        return create_policy_draft(
            permissions=payload.permissions,
            risk_weights=payload.risk_weights,
            max_blocked_attempts=payload.max_blocked_attempts,
            max_risk_score=payload.max_risk_score,
            change_summary=payload.change_summary,
            created_by=policy_actor(administrator),
        )
    except (ValueError, RuntimeError) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@app.put("/policy-versions/{policy_id}/draft")
def update_policy_version_draft(
    policy_id: str,
    payload: PolicyDocumentRequest,
    x_admin_pin: str | None = Header(default=None),
):
    """Update an isolated policy draft."""

    administrator = require_policy_editor(x_admin_pin)

    try:
        return update_policy_draft(
            policy_id=policy_id,
            permissions=payload.permissions,
            risk_weights=payload.risk_weights,
            max_blocked_attempts=payload.max_blocked_attempts,
            max_risk_score=payload.max_risk_score,
            change_summary=payload.change_summary,
            actor=policy_actor(administrator),
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


def require_platform_admin(x_admin_pin):
    administrator = require_admin(x_admin_pin)
    if administrator["role"] != "PLATFORM_ADMIN":
        raise HTTPException(status_code=403, detail="Platform Admin approval is required.")
    return administrator


@app.post("/policy-versions/{policy_id}/submit")
def submit_policy_version(policy_id: str, x_admin_pin: str | None = Header(default=None)):
    administrator = require_policy_editor(x_admin_pin)
    try:
        return submit_policy(policy_id, policy_actor(administrator))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/policy-versions/{policy_id}/approve")
def approve_policy_version(policy_id: str, x_admin_pin: str | None = Header(default=None)):
    administrator = require_platform_admin(x_admin_pin)
    try:
        policy = approve_policy(policy_id, policy_actor(administrator))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    main.permissions.clear()
    main.permissions.update(policy["permissions"])
    main.risk_weights.clear()
    main.risk_weights.update(policy["risk_weights"])
    main.max_blocked_attempts = policy["max_blocked_attempts"]
    main.max_risk_score = policy["max_risk_score"]
    return policy


@app.post("/policy-versions/{policy_id}/reject")
def reject_policy_version(policy_id: str, note: str = Query(default="Policy change rejected."), x_admin_pin: str | None = Header(default=None)):
    administrator = require_platform_admin(x_admin_pin)
    try:
        return reject_policy(policy_id, policy_actor(administrator), note)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/policy-versions/{policy_id}/rollback", status_code=201)
def rollback_policy_version(policy_id: str, x_admin_pin: str | None = Header(default=None)):
    administrator = require_platform_admin(x_admin_pin)
    try:
        return create_rollback_draft(policy_id, policy_actor(administrator))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/policy-versions")
def policy_versions(
    x_admin_pin: str | None = Header(default=None),
):
    """Return all policy versions, newest first."""

    require_admin(x_admin_pin)

    return {
        "versions": list_policy_versions(),
        "published": get_published_policy(),
    }


@app.get("/policy-versions/{policy_id}")
def policy_version(
    policy_id: str,
    x_admin_pin: str | None = Header(default=None),
):
    """Return one stored policy version."""

    require_admin(x_admin_pin)

    try:
        return get_policy_version(policy_id)
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error


@app.get("/policy-versions/{policy_id}/history")
def policy_version_history(
    policy_id: str,
    x_admin_pin: str | None = Header(default=None),
):
    """Return the immutable history of one policy."""

    require_admin(x_admin_pin)

    try:
        return {
            "policy_id": policy_id,
            "events": get_policy_history(policy_id),
        }
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error


@app.get("/secrets")
def secret_references(x_admin_pin: str | None = Header(default=None)):
    require_admin(x_admin_pin)
    return {"secrets": list_secrets(), "values_exposed": False}


@app.post("/secrets", status_code=201)
def create_secret_reference(payload: SecretCreateRequest, x_admin_pin: str | None = Header(default=None)):
    administrator=require_platform_admin(x_admin_pin)
    try: return create_secret(payload.name,payload.reference,policy_actor(administrator))
    except ValueError as error: raise HTTPException(status_code=400,detail=redact(error)) from error


@app.post("/secrets/{secret_id}/rotate")
def rotate_secret_reference(secret_id: str,payload: SecretRotateRequest,x_admin_pin: str | None = Header(default=None)):
    administrator=require_platform_admin(x_admin_pin)
    try: return rotate_secret(secret_id,payload.reference,policy_actor(administrator))
    except KeyError as error: raise HTTPException(status_code=404,detail=str(error)) from error
    except ValueError as error: raise HTTPException(status_code=400,detail=redact(error)) from error


@app.post("/secrets/{secret_id}/revoke")
def revoke_secret_reference(secret_id: str,x_admin_pin: str | None = Header(default=None)):
    administrator=require_platform_admin(x_admin_pin)
    try: return revoke_secret(secret_id,policy_actor(administrator))
    except KeyError as error: raise HTTPException(status_code=404,detail=str(error)) from error


@app.get("/service-accounts")
def administrator_service_accounts(x_admin_pin: str | None = Header(default=None)):
    """Return machine identities without plaintext API keys."""
    require_platform_admin(x_admin_pin)
    return {
        "service_accounts": list_service_accounts(),
        "available_scopes": sorted(AVAILABLE_SCOPES),
        "plaintext_keys_stored": False,
    }


@app.post("/service-accounts", status_code=201)
def administrator_create_service_account(
    payload: ServiceAccountCreateRequest,
    x_admin_pin: str | None = Header(default=None),
):
    administrator = require_platform_admin(x_admin_pin)
    try:
        return create_service_account(
            payload.name, payload.description, payload.scopes,
            payload.expires_in_days, policy_actor(administrator),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/service-accounts/{account_id}/rotate")
def administrator_rotate_service_account_key(
    account_id: str,
    payload: ServiceAccountRotateRequest,
    x_admin_pin: str | None = Header(default=None),
):
    administrator = require_platform_admin(x_admin_pin)
    try:
        return rotate_service_account_key(
            account_id, payload.expires_in_days, policy_actor(administrator)
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/service-accounts/{account_id}/revoke")
def administrator_revoke_service_account(
    account_id: str,
    x_admin_pin: str | None = Header(default=None),
):
    administrator = require_platform_admin(x_admin_pin)
    try:
        return revoke_service_account(account_id, policy_actor(administrator))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/service-accounts/verify")
def verify_service_account_key(
    required_scope: str | None = Query(default=None),
    x_service_key: str | None = Header(default=None),
):
    """Authenticate a machine identity and record key usage."""
    try:
        return authenticate_service_key(x_service_key or "", required_scope)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


@app.get("/compliance-reports")
def compliance_report_history(x_admin_pin: str | None = Header(default=None)):
    """Return immutable compliance-report history."""
    require_admin(x_admin_pin)
    return {"reports": list_compliance_reports()}


@app.post("/compliance-reports", status_code=201)
def generate_compliance_report(
    payload: ComplianceReportRequest,
    x_admin_pin: str | None = Header(default=None),
):
    """Capture a point-in-time security evidence snapshot."""
    administrator = require_admin(x_admin_pin)
    try:
        return create_compliance_report(
            payload.title,
            {
                "date_from": payload.date_from,
                "date_to": payload.date_to,
                "severities": payload.severities,
                "event_types": payload.event_types,
            },
            policy_actor(administrator),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/compliance-reports/{report_id}")
def compliance_report_details(
    report_id: str,
    x_admin_pin: str | None = Header(default=None),
):
    require_admin(x_admin_pin)
    try:
        return get_compliance_report(report_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/compliance-reports/{report_id}/export")
def export_compliance_report(
    report_id: str,
    format: Literal["json", "csv"] = Query(default="json"),
    x_admin_pin: str | None = Header(default=None),
):
    require_admin(x_admin_pin)
    try:
        if format == "csv":
            content = export_csv(report_id)
            media_type = "text/csv; charset=utf-8"
        else:
            content = export_json(report_id)
            media_type = "application/json"
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{report_id}.{format}"'},
    )


@app.get("/abuse-protection")
def abuse_protection_overview(x_admin_pin: str | None = Header(default=None)):
    """Return throttling policy, block metrics, and recent defensive evidence."""
    require_platform_admin(x_admin_pin)
    return {
        "summary": abuse_summary(),
        "policies": list_rate_limit_policies(),
        "events": list_abuse_events(limit=100),
    }


@app.put("/abuse-protection/policies/{category}")
def administrator_update_rate_limit_policy(
    category: str,
    payload: RateLimitPolicyRequest,
    x_admin_pin: str | None = Header(default=None),
):
    administrator = require_platform_admin(x_admin_pin)
    try:
        return update_rate_limit_policy(
            category,
            payload.model_dump(),
            policy_actor(administrator),
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/permissions")
def permissions():
    """Return GreyGuard's action policy."""

    published_policy = get_published_policy()

    return {
        "policy_id": published_policy["policy_id"] if published_policy else None,
        "version_number": published_policy["version_number"] if published_policy else None,
        "permissions": main.permissions,
        "risk_weights": main.risk_weights,
        "available_scopes": sorted(
            main.permissions.keys()
        ),
        "controlled_tools": (
            main.get_supported_tools()
        ),
        "max_blocked_attempts": (
            main.max_blocked_attempts
        ),
        "max_risk_score": (
            main.max_risk_score
        ),
    }


@app.get("/tools")
def tools():
    """Return controlled gateway information."""

    return {
        "tools": main.get_supported_tools(),
        "sandbox_only": True,
        "network_access": False,
        "arbitrary_command_execution": False,
        "absolute_paths_allowed": False,
        "path_escape_allowed": False,
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
    """Register an agent and issue a credential."""

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
        main.normalize_agent_name(
            agent_name
        )
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
    """Replace an agent's scopes."""

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
    """Authenticate and evaluate an action."""

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


@app.post(
    "/tool-requests",
    status_code=201,
)
def create_tool_request(
    request: ToolRequestCreate,
    x_agent_name: str | None = Header(
        default=None,
    ),
    x_agent_key: str | None = Header(
        default=None,
    ),
):
    """Submit a controlled tool request."""

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
        return main.submit_tool_request(
            agent_name=authenticated_name,
            action=authentication["action"],
            target=request.target,
            payload=request.payload,
            dry_run=request.dry_run,
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



@app.get("/tool-requests")
def list_tool_requests(
    agent_name: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    approval_status: str | None = Query(
        default=None,
    ),
    execution_status: str | None = Query(
        default=None,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    x_admin_pin: str | None = Header(
        default=None,
    ),
):
    """Return tool requests for administrators."""

    require_admin(x_admin_pin)

    requests = get_tool_requests(
        agent_name=agent_name,
        approval_status=approval_status,
        execution_status=execution_status,
        limit=limit,
    )

    return {
        "requests": requests,
        "count": len(requests),
        "filters": {
            "agent_name": agent_name,
            "approval_status": approval_status,
            "execution_status": execution_status,
            "limit": limit,
        },
    }


@app.get("/tool-requests/{request_id}")
def get_tool_request(
    request_id: str,
    x_agent_name: str | None = Header(
        default=None,
    ),
    x_agent_key: str | None = Header(
        default=None,
    ),
):
    """Return an agent's tool-request evidence."""

    details = get_tool_request_details(
        request_id
    )

    if details is None:
        raise HTTPException(
            status_code=404,
            detail="Tool request not found.",
        )

    request_data = details["request"]

    authentication = authenticate_request(
        x_agent_name=x_agent_name,
        x_agent_key=x_agent_key,
        action=request_data["action"],
    )

    identity = authentication["identity"]

    if (
        identity["agent_name"]
        != request_data["agent_name"]
    ):
        main.record_authentication_event(
            claimed_agent_name=(
                identity["agent_name"]
            ),
            authenticated_agent_name=(
                identity["agent_name"]
            ),
            action=request_data["action"],
            outcome="RESOURCE_DENIED",
            reason=(
                "Agent attempted to access "
                "another agent's tool request."
            ),
        )

        raise HTTPException(
            status_code=403,
            detail=(
                "Authenticated agent cannot "
                "access another agent's "
                "tool request."
            ),
        )

    return details


@app.post(
    "/tool-requests/{request_id}/decision"
)
def review_tool_request(
    request_id: str,
    review: ToolApprovalDecision,
    x_admin_pin: str | None = Header(
        default=None,
    ),
):
    """Approve or deny a pending tool request."""

    require_admin(x_admin_pin)

    try:
        return main.review_tool_request(
            request_id=request_id,
            actor="administrator",
            decision=review.decision,
            note=review.note,
        )

    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error


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
    """Return an agent's audit events."""

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
    """Return an agent's audit summary."""

    authenticate_agent_owner(
        requested_agent_name=agent_name,
        x_agent_name=x_agent_name,
        x_agent_key=x_agent_key,
        required_scope="audit_summary",
    )

    normalized_name = (
        main.normalize_agent_name(
            agent_name
        )
    )

    return {
        "agent_name": normalized_name,
        **get_audit_summary(
            normalized_name
        ),
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
        main.normalize_agent_name(
            agent_name
        )
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
        main.normalize_agent_name(
            agent_name
        )
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


@app.get("/audit-events")
def administrator_audit_events(
    event_type: str | None = Query(
        default=None,
    ),
    agent_name: str | None = Query(
        default=None,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    x_admin_pin: str | None = Header(
        default=None,
    ),
):
    """Return unified audit evidence to an administrator."""

    require_admin(x_admin_pin)

    from .database import (
        get_administrator_audit_events,
    )

    return get_administrator_audit_events(
        event_type=event_type,
        agent_name=agent_name,
        limit=limit,
    )


@app.get("/live-events")
def live_administrator_events(
    request: Request,
    event_type: str | None = Query(
        default=None,
    ),
    agent_name: str | None = Query(
        default=None,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    include_history: bool = Query(
        default=True,
    ),
    poll_interval: float = Query(
        default=1.0,
        ge=0.5,
        le=10.0,
    ),
    x_admin_pin: str | None = Header(
        default=None,
    ),
):
    """Stream live unified security evidence."""

    require_admin(x_admin_pin)

    event_stream = stream_administrator_events(
        request=request,
        event_type=event_type,
        agent_name=agent_name,
        limit=limit,
        include_history=include_history,
        poll_interval=poll_interval,
    )

    return StreamingResponse(
        event_stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/alerts/summary")
def administrator_alert_summary(x_admin_pin: str | None = Header(default=None)):
    """Return administrator alert metrics."""
    require_admin(x_admin_pin)
    return alert_summary()


@app.get("/notifications/summary")
def administrator_notification_summary(x_admin_pin: str | None = Header(default=None)):
    """Return unread administrator notification counts."""
    require_admin(x_admin_pin)
    return notification_summary()


@app.get("/notifications")
def administrator_notifications(
    unread_only: bool = Query(default=False),
    severity: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    x_admin_pin: str | None = Header(default=None),
):
    """Return the persistent in-app security notification inbox."""
    require_admin(x_admin_pin)
    return list_notifications(unread_only, severity, limit)


@app.put("/notifications/read-all")
def administrator_read_all_notifications(x_admin_pin: str | None = Header(default=None)):
    """Mark every unread notification as reviewed."""
    administrator = require_admin(x_admin_pin)
    return {
        "updated": mark_all_notifications_read(administrator.get("email", "administrator"))
    }


@app.put("/notifications/{notification_id}/read")
def administrator_read_notification(
    notification_id: str,
    x_admin_pin: str | None = Header(default=None),
):
    """Mark one notification as reviewed."""
    administrator = require_admin(x_admin_pin)
    try:
        return mark_notification_read(
            notification_id, administrator.get("email", "administrator")
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Notification not found.") from error


@app.get("/alerts")
def administrator_alerts(
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    agent_name: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    x_admin_pin: str | None = Header(default=None),
):
    """Return filtered security alerts."""
    require_admin(x_admin_pin)
    return get_alerts(status, severity, agent_name, limit)


@app.get("/alerts/{alert_id}")
def administrator_alert(alert_id: str, x_admin_pin: str | None = Header(default=None)):
    """Return one alert and its evidence."""
    require_admin(x_admin_pin)
    result = get_alert(alert_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return result


@app.put("/alerts/{alert_id}")
def administrator_update_alert(
    alert_id: str,
    update: AlertUpdateRequest,
    x_admin_pin: str | None = Header(default=None),
):
    """Update alert workflow state."""
    require_admin(x_admin_pin)
    try:
        return update_alert(
            alert_id, update.status, "administrator", update.assigned_to, update.note
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Alert not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/alerts/{alert_id}/notes", status_code=201)
def administrator_add_alert_note(
    alert_id: str,
    request: AlertNoteRequest,
    x_admin_pin: str | None = Header(default=None),
):
    """Append investigation evidence."""
    require_admin(x_admin_pin)
    try:
        return add_alert_note(alert_id, "administrator", request.note)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Alert not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/sandbox/resources")
def sandbox_resources(
    x_admin_pin: str | None = Header(
        default=None,
    ),
):
    """Return safe sandbox metadata to an administrator."""

    require_admin(x_admin_pin)

    from .tool_gateway import (
        initialize_sandbox,
        list_files,
    )

    initialization = initialize_sandbox()
    listing = list_files("")

    return {
        "initialized": True,
        "sandbox_name": "GreyGuard controlled sandbox",
        "controls": {
            "sandbox_only": True,
            "network_access": False,
            "arbitrary_command_execution": False,
            "absolute_paths_allowed": False,
            "path_escape_allowed": False,
        },
        "initialization": initialization,
        "resources": listing,
    }
