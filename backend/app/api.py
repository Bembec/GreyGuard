"""
GreyGuard V10 FastAPI control plane.

Agent requests must authenticate with an agent name and credential.
Each authenticated identity must possess the requested action scope.

V10 adds persistent controlled-tool requests, sandbox execution,
human approval decisions, dry runs, replay protection, and evidence.
"""

from contextlib import asynccontextmanager

import hashlib
import hmac
import os
import sqlite3
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
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

from . import main
from .admin_auth import (
    authenticate as authenticate_administrator,
    begin_mfa_enrollment,
    confirm_mfa,
    create_administrator,
    get_administrator,
    reset_administrator_password,
    revoke_administrator_sessions,
    update_administrator,
    has_permission,
    initialize_admin_auth,
    list_administrators,
    list_sessions,
    refresh_access_token,
    required_permission,
    revoke_session,
    revoke_session_by_id,
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
    add_policy_test_case,
    approve_policy,
    create_policy_draft,
    create_rollback_draft,
    detect_policy_conflicts,
    get_emergency_controls,
    get_policy_history,
    get_policy_version,
    get_published_policy,
    initialize_policy_control,
    list_policy_versions,
    reject_policy,
    run_policy_tests,
    simulate_policy,
    submit_policy,
    update_emergency_controls,
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
from .policy_integrations import (
    configure_policy_adapter,
    create_rollout,
    export_signed_policy_bundle,
    initialize_policy_integrations,
    list_policy_adapters,
    list_rollouts,
    update_rollout,
    verify_signed_policy_bundle,
)
from .secret_manager import (
    SecretRedactionMiddleware, create_secret, emergency_revoke_all,
    initialize_secret_manager, list_secrets, redact, revoke_secret,
    rotate_secret, secret_events,
)
from .secret_providers import provider_status
from .notifications import (
    cleanup_expired_notifications,
    get_retention_policy,
    initialize_notification_database,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    notification_summary,
    retention_history,
    update_retention_policy,
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
from .adapter_control import (
    configure_adapter,
    extract_action,
    initialize_adapter_control,
    list_adapters,
    test_adapter,
    translate_request,
)
from .observability import (
    bind_request,
    current_correlation_id,
    finish_request,
    get_config as get_observability_config,
    initialize_observability,
    otlp_export,
    prometheus_metrics,
    start_request,
    update_config as update_observability_config,
)
from .enterprise_identity import (
    activate_break_glass,
    add_role_mapping,
    create_workload_identity,
    decide_elevation,
    identity_summary,
    initialize_enterprise_identity,
    list_elevations,
    list_providers,
    list_role_mappings,
    list_workload_identities,
    request_elevation,
    save_provider,
)
from .production_config import load_production_config
from .runtime_security import RuntimeSecurityMiddleware, readiness
from .security_exports import (
    DESTINATION_TYPES,
    MINIMIZATION_PROFILES,
    enqueue_export,
    export_summary,
    initialize_security_exports,
    list_destinations,
    save_destination,
)
from .global_search import search_control_plane
from .agent_investigation import build_agent_investigation
from .request_investigation import build_request_investigation

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize GreyGuard for the API lifecycle."""

    load_production_config()
    main.initialize_greyguard()
    initialize_policy_control(
        permissions=main.permissions,
        risk_weights=main.risk_weights,
        max_blocked_attempts=(
            main.max_blocked_attempts
        ),
        max_risk_score=main.max_risk_score,
    )
    initialize_policy_integrations()
    initialize_alert_database()
    initialize_secret_manager()
    initialize_notification_database()
    initialize_service_accounts()
    initialize_compliance_reports()
    initialize_abuse_protection()
    initialize_adapter_control(main.permissions.keys())
    initialize_observability()
    initialize_enterprise_identity()
    initialize_security_exports()

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

runtime_config = load_production_config()
app.add_middleware(RuntimeSecurityMiddleware, production=runtime_config.environment == "production")
app.add_middleware(SecretRedactionMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(runtime_config.trusted_hosts))
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(runtime_config.allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Admin-Pin", "X-Agent-Name", "X-Agent-Key", "X-Correlation-ID"],
)


@app.middleware("http")
async def observe_request(request: Request, call_next):
    context = start_request(
        request.method, request.url.path,
        request.headers.get("x-correlation-id"),
        request.headers.get("traceparent"),
    )
    try:
        response = await call_next(request)
    except Exception:
        finish_request(context, 500)
        raise
    finish_request(context, response.status_code)
    response.headers["X-Correlation-ID"] = context["correlation_id"]
    sampled = "01" if context["sampled"] else "00"
    response.headers["traceparent"] = f'00-{context["trace_id"]}-{context["span_id"]}-{sampled}'
    return response


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
    elif path.startswith("/actions") or path.startswith("/tool-requests") or path.startswith("/adapter-requests"):
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
    mfa_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    device_name: str = Field(default="Browser", max_length=100)


class AdministratorRefresh(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=256)
    device_name: str = Field(default="Browser", max_length=100)


class MfaConfirmation(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


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


class PolicySimulationRequest(BaseModel):
    action: str = Field(min_length=1, max_length=100)
    has_scope: bool = True
    suspended: bool = False
    current_risk: int = Field(default=0, ge=0, le=10_000)


class PolicyTestCaseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=100)
    expected_decision: Literal["ALLOW", "ASK", "BLOCK", "REFUSED"]
    has_scope: bool = True
    suspended: bool = False


class PolicyEmergencyRequest(BaseModel):
    global_deny: bool = False
    disabled_agents: list[str] = Field(default_factory=list)
    disabled_tools: list[str] = Field(default_factory=list)
    disabled_integrations: list[str] = Field(default_factory=list)


class PolicyAdapterRequest(BaseModel):
    enabled: bool = False
    endpoint: str | None = Field(default=None, max_length=500)
    owner: str = Field(default="", max_length=100)
    purpose: str = Field(default="", max_length=500)


class PolicyRolloutCreateRequest(BaseModel):
    policy_id: str
    percentage: int = Field(ge=0, le=100)
    agent_allowlist: list[str] = Field(default_factory=list)


class PolicyRolloutUpdateRequest(BaseModel):
    status: Literal["ACTIVE", "PAUSED", "COMPLETED", "CANCELLED"]
    percentage: int = Field(ge=0, le=100)


class SignedPolicyBundleRequest(BaseModel):
    document: dict
    algorithm: str
    signature: str


class SecretCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: Literal["ENVIRONMENT", "HASHICORP_VAULT", "AWS", "AZURE", "GCP"] = "ENVIRONMENT"
    reference: str = Field(min_length=3, max_length=512)
    rotation_interval_days: int | None = Field(default=None, ge=1, le=365)


class SecretRotateRequest(BaseModel):
    reference: str = Field(min_length=3, max_length=512)


class EmergencySecretRevocationRequest(BaseModel):
    provider: Literal["HASHICORP_VAULT", "AWS", "AZURE", "GCP", "ENVIRONMENT"] | None = None


class ServiceAccountCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    description: str = Field(default="", max_length=500)
    scopes: list[str] = Field(min_length=1)
    expires_in_days: int | None = Field(default=90, ge=1, le=365)


class AdapterConfigurationRequest(BaseModel):
    enabled: bool
    owner: str = Field(default="", max_length=100)
    purpose: str = Field(default="", max_length=500)
    allowed_actions: list[str] = Field(min_length=1)


class IdentityProviderRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    issuer: str = Field(min_length=8, max_length=500)
    client_id: str = Field(min_length=1, max_length=250)
    allowed_domains: list[str] = Field(default_factory=list)
    enabled: bool = True


class IdentityRoleMappingRequest(BaseModel):
    provider_id: str
    claim_name: str = Field(min_length=1, max_length=100)
    claim_value: str = Field(min_length=1, max_length=250)
    role: Literal["PLATFORM_ADMIN", "SECURITY_ANALYST", "AUDITOR"]
    priority: int = Field(default=100, ge=1, le=1000)


class WorkloadIdentityRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    subject: str = Field(min_length=2, max_length=250)
    certificate_pem: str = Field(min_length=32, max_length=20_000)
    scopes: list[str] = Field(min_length=1)
    expires_in_days: int = Field(default=90, ge=1, le=365)


class ElevationRequest(BaseModel):
    role: Literal["PLATFORM_ADMIN", "SECURITY_ANALYST", "AUDITOR"]
    reason: str = Field(min_length=8, max_length=1000)
    minutes: int = Field(default=30, ge=5, le=120)


class ElevationDecisionRequest(BaseModel):
    approved: bool


class BreakGlassRequest(BaseModel):
    reason: str = Field(min_length=12, max_length=1000)
    minutes: int = Field(default=30, ge=5, le=60)


class ObservabilityConfigurationRequest(BaseModel):
    tracing_enabled: bool
    metrics_enabled: bool
    structured_logs_enabled: bool
    sample_rate: float = Field(ge=0, le=1)
    retention_limit: int = Field(ge=100, le=100_000)


class ExportDestinationRequest(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    destination_type: Literal["SIGNED_WEBHOOK", "SPLUNK", "MICROSOFT_SENTINEL", "ELASTIC", "GRAFANA_LOKI", "SYSLOG", "STIX_TAXII"]
    endpoint: str = Field(min_length=8, max_length=500)
    enabled: bool = False
    signing_key_reference: str | None = Field(default=None, max_length=128)
    minimization_profile: Literal["MINIMAL", "STANDARD", "FORENSIC"] = "STANDARD"
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10_000)
    max_attempts: int = Field(default=5, ge=1, le=20)


class SecurityExportRequest(BaseModel):
    destination_id: str
    event: dict


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


class NotificationRetentionUpdate(BaseModel):
    retention_days: int = Field(ge=7, le=3650)


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
def administrator_login(credentials: AdministratorLogin, request: Request):
    try:
        return authenticate_administrator(
            credentials.email, credentials.password, credentials.mfa_code,
            credentials.device_name, request.client.host if request.client else "",
        )
    except PermissionError as error:
        raise HTTPException(status_code=428, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


@app.post("/auth/refresh")
def administrator_refresh(credentials: AdministratorRefresh, request: Request):
    try:
        return refresh_access_token(
            credentials.refresh_token, credentials.device_name,
            request.client.host if request.client else "",
        )
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


@app.post("/auth/mfa/enroll")
def administrator_mfa_enroll(x_admin_pin: str | None = Header(default=None)):
    administrator = require_admin(x_admin_pin)
    return begin_mfa_enrollment(administrator["admin_id"])


@app.post("/auth/mfa/confirm")
def administrator_mfa_confirm(payload: MfaConfirmation, x_admin_pin: str | None = Header(default=None)):
    administrator = require_admin(x_admin_pin)
    try:
        return confirm_mfa(administrator["admin_id"], payload.code)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/auth/sessions")
def administrator_sessions(x_admin_pin: str | None = Header(default=None)):
    administrator = require_admin(x_admin_pin)
    return {"sessions": list_sessions(administrator["admin_id"])}


@app.delete("/auth/sessions/{session_id}")
def administrator_revoke_session(session_id: str, x_admin_pin: str | None = Header(default=None)):
    administrator = require_admin(x_admin_pin)
    try:
        revoke_session_by_id(administrator["admin_id"], session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"revoked": True, "session_id": session_id}


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


@app.post("/policy-versions/{policy_id}/simulate")
def simulate_policy_version(policy_id: str, payload: PolicySimulationRequest, x_admin_pin: str | None = Header(default=None)):
    """Safely preview a decision with no enforcement side effects."""
    require_admin(x_admin_pin)
    try:
        return simulate_policy(policy_id, payload.action, payload.has_scope, payload.suspended, payload.current_risk)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/policy-versions/{policy_id}/conflicts")
def policy_version_conflicts(policy_id: str, x_admin_pin: str | None = Header(default=None)):
    require_admin(x_admin_pin)
    try:
        return detect_policy_conflicts(policy_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/policy-versions/{policy_id}/tests", status_code=201)
def create_policy_test(policy_id: str, payload: PolicyTestCaseRequest, x_admin_pin: str | None = Header(default=None)):
    administrator = require_policy_editor(x_admin_pin)
    try:
        return add_policy_test_case(policy_id, payload.name, payload.action, payload.expected_decision, payload.has_scope, payload.suspended)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/policy-versions/{policy_id}/tests/run")
def execute_policy_tests(policy_id: str, x_admin_pin: str | None = Header(default=None)):
    require_admin(x_admin_pin)
    try:
        return run_policy_tests(policy_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/policy-emergency-controls")
def policy_emergency_control_state(x_admin_pin: str | None = Header(default=None)):
    require_admin(x_admin_pin)
    return get_emergency_controls()


@app.put("/policy-emergency-controls")
def configure_policy_emergency_controls(payload: PolicyEmergencyRequest, x_admin_pin: str | None = Header(default=None)):
    administrator = require_platform_admin(x_admin_pin)
    return update_emergency_controls(payload.global_deny, payload.disabled_agents, payload.disabled_tools, payload.disabled_integrations, policy_actor(administrator))


@app.get("/policy-adapters")
def policy_adapters(x_admin_pin: str | None = Header(default=None)):
    require_admin(x_admin_pin)
    return {"adapters": list_policy_adapters(), "network_authority_automatic": False}


@app.put("/policy-adapters/{adapter_type}")
def update_policy_adapter(adapter_type: str, payload: PolicyAdapterRequest, x_admin_pin: str | None = Header(default=None)):
    administrator = require_platform_admin(x_admin_pin)
    try:
        return configure_policy_adapter(adapter_type, payload.enabled, payload.endpoint, payload.owner, payload.purpose, policy_actor(administrator))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/policy-rollouts")
def policy_rollouts(x_admin_pin: str | None = Header(default=None)):
    require_admin(x_admin_pin)
    return {"rollouts": list_rollouts()}


@app.post("/policy-rollouts", status_code=201)
def create_policy_rollout(payload: PolicyRolloutCreateRequest, x_admin_pin: str | None = Header(default=None)):
    administrator = require_platform_admin(x_admin_pin)
    try:
        return create_rollout(payload.policy_id, payload.percentage, payload.agent_allowlist, policy_actor(administrator))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.put("/policy-rollouts/{rollout_id}")
def change_policy_rollout(rollout_id: str, payload: PolicyRolloutUpdateRequest, x_admin_pin: str | None = Header(default=None)):
    administrator = require_platform_admin(x_admin_pin)
    try:
        return update_rollout(rollout_id, payload.status, payload.percentage, policy_actor(administrator))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/policy-versions/{policy_id}/bundle")
def signed_policy_bundle(policy_id: str, x_admin_pin: str | None = Header(default=None)):
    require_platform_admin(x_admin_pin)
    try:
        return export_signed_policy_bundle(policy_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/policy-bundles/verify")
def verify_policy_bundle(payload: SignedPolicyBundleRequest, x_admin_pin: str | None = Header(default=None)):
    require_admin(x_admin_pin)
    try:
        return verify_signed_policy_bundle(payload.model_dump())
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


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
    return {"secrets": list_secrets(), "providers": provider_status(), "values_exposed": False}


@app.post("/secrets", status_code=201)
def create_secret_reference(payload: SecretCreateRequest, x_admin_pin: str | None = Header(default=None)):
    administrator=require_platform_admin(x_admin_pin)
    try: return create_secret(payload.name,payload.reference,policy_actor(administrator),payload.provider,payload.rotation_interval_days)
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


@app.get("/secret-events")
def secret_access_evidence(secret_id: str | None = Query(default=None), x_admin_pin: str | None = Header(default=None)):
    require_admin(x_admin_pin)
    return {"events": secret_events(secret_id), "values_exposed": False}


@app.post("/secrets/emergency-revoke")
def emergency_secret_revocation(payload: EmergencySecretRevocationRequest, x_admin_pin: str | None = Header(default=None)):
    administrator=require_platform_admin(x_admin_pin)
    return emergency_revoke_all(policy_actor(administrator),payload.provider)


@app.get("/service-accounts")
def administrator_service_accounts(x_admin_pin: str | None = Header(default=None)):
    """Return machine identities without plaintext API keys."""
    require_platform_admin(x_admin_pin)
    return {
        "service_accounts": list_service_accounts(),
        "available_scopes": sorted(AVAILABLE_SCOPES),
        "plaintext_keys_stored": False,
    }


@app.get("/health/live", include_in_schema=False)
def liveness():
    return {"status": "alive"}


@app.get("/health/ready", include_in_schema=False)
def readiness_probe():
    result = readiness()
    if result["status"] != "ready":
        return JSONResponse(status_code=503, content=result)
    return result


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


@app.get("/adapters")
def administrator_adapters(x_admin_pin: str | None = Header(default=None)):
    require_platform_admin(x_admin_pin)
    return {
        "adapters": list_adapters(),
        "disabled_by_default": True,
        "network_egress": False,
    }


@app.put("/adapters/{adapter_id}")
def administrator_configure_adapter(
    adapter_id: str,
    payload: AdapterConfigurationRequest,
    x_admin_pin: str | None = Header(default=None),
):
    administrator = require_platform_admin(x_admin_pin)
    try:
        return configure_adapter(
            adapter_id, payload.enabled, payload.owner, payload.purpose,
            payload.allowed_actions, policy_actor(administrator),
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/adapters/{adapter_id}/test")
def administrator_test_adapter(
    adapter_id: str,
    x_admin_pin: str | None = Header(default=None),
):
    require_platform_admin(x_admin_pin)
    try:
        return test_adapter(adapter_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/adapter-requests/{adapter_id}", status_code=201)
def create_adapter_request(
    adapter_id: str,
    payload: dict,
    x_agent_name: str | None = Header(default=None),
    x_agent_key: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    candidate_action = extract_action(adapter_id, payload)
    authentication = authenticate_request(
        x_agent_name=x_agent_name,
        x_agent_key=x_agent_key,
        action=candidate_action,
    )
    try:
        translated = translate_request(adapter_id, payload)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if idempotency_key is not None and not 8 <= len(idempotency_key) <= 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key must be between 8 and 128 characters.")
    stable_request_id = None
    if idempotency_key:
        agent_name = authentication["identity"]["agent_name"]
        digest = hashlib.sha256(f"{agent_name}:{adapter_id}:{idempotency_key}".encode()).hexdigest()
        stable_request_id = f"idem_{digest[:32]}"
    result = main.submit_tool_request(
        agent_name=authentication["identity"]["agent_name"],
        action=translated["action"], target=translated["target"],
        payload=translated["payload"], dry_run=translated["dry_run"],
        request_id=stable_request_id,
    )
    bind_request(result.get("request_id"), current_correlation_id.get())
    return result


@app.get("/observability/config")
def observability_configuration(x_admin_pin: str | None = Header(default=None)):
    require_platform_admin(x_admin_pin)
    return get_observability_config()


@app.put("/observability/config")
def configure_observability(
    payload: ObservabilityConfigurationRequest,
    x_admin_pin: str | None = Header(default=None),
):
    administrator = require_platform_admin(x_admin_pin)
    return update_observability_config(
        payload.tracing_enabled, payload.metrics_enabled,
        payload.structured_logs_enabled, payload.sample_rate,
        payload.retention_limit, policy_actor(administrator),
    )


@app.get("/observability/metrics")
def observability_metrics(x_admin_pin: str | None = Header(default=None)):
    require_platform_admin(x_admin_pin)
    return Response(content=prometheus_metrics(), media_type="text/plain; version=0.0.4")


@app.get("/observability/traces")
def observability_traces(
    limit: int = Query(default=200, ge=1, le=1000),
    x_admin_pin: str | None = Header(default=None),
):
    require_platform_admin(x_admin_pin)
    return otlp_export(limit)


@app.get("/security-exports")
def security_export_control(x_admin_pin: str | None = Header(default=None)):
    require_platform_admin(x_admin_pin)
    return {
        "destinations": list_destinations(),
        "summary": export_summary(),
        "destination_types": sorted(DESTINATION_TYPES),
        "minimization_profiles": sorted(MINIMIZATION_PROFILES),
    }


@app.post("/security-exports/destinations", status_code=201)
def configure_security_export_destination(
    payload: ExportDestinationRequest,
    x_admin_pin: str | None = Header(default=None),
):
    administrator = require_platform_admin(x_admin_pin)
    try:
        return save_destination(
            payload.name, payload.destination_type, payload.endpoint, payload.enabled,
            payload.signing_key_reference, payload.minimization_profile,
            payload.rate_limit_per_minute, payload.max_attempts, policy_actor(administrator),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/security-exports/queue", status_code=202)
def queue_security_export(
    payload: SecurityExportRequest,
    x_admin_pin: str | None = Header(default=None),
):
    administrator = require_platform_admin(x_admin_pin)
    try:
        return enqueue_export(payload.destination_id, payload.event, policy_actor(administrator))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


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


@app.get("/agent-investigations/{agent_name}")
def agent_investigation(
    agent_name: str,
    limit: int = Query(default=100, ge=1, le=200),
    x_admin_pin: str | None = Header(default=None),
):
    """Return a redacted, administrator-scoped agent investigation view."""
    require_admin(x_admin_pin)
    try:
        return build_agent_investigation(agent_name, limit)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Agent not found.") from error


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
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
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

    stable_request_id = None
    if idempotency_key is not None:
        if not 8 <= len(idempotency_key) <= 128:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Idempotency-Key must be between "
                    "8 and 128 characters."
                ),
            )

        digest = hashlib.sha256(
            f"{authenticated_name}:{idempotency_key}".encode(
                "utf-8"
            )
        ).hexdigest()
        stable_request_id = f"idem_{digest[:32]}"

    try:
        result = main.submit_tool_request(
            agent_name=authenticated_name,
            action=authentication["action"],
            target=request.target,
            payload=request.payload,
            dry_run=request.dry_run,
            request_id=stable_request_id,
        )
        bind_request(result.get("request_id"), current_correlation_id.get())
        return result

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
    last_event_id: str | None = Query(default=None, max_length=200),
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
        last_event_id=last_event_id,
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


@app.get("/notifications/retention")
def administrator_notification_retention(x_admin_pin: str | None = Header(default=None)):
    """Return retention configuration and recent retention evidence."""
    require_admin(x_admin_pin)
    return {"policy": get_retention_policy(), "history": retention_history()}


@app.put("/notifications/retention")
def administrator_update_notification_retention(
    update: NotificationRetentionUpdate,
    x_admin_pin: str | None = Header(default=None),
):
    """Update notification retention as a platform administrator."""
    administrator = require_admin(x_admin_pin)
    if not has_permission(administrator, "admin:manage"):
        raise HTTPException(status_code=403, detail="Platform Administrator permission is required.")
    return update_retention_policy(update.retention_days, administrator.get("email", "administrator"))


@app.post("/notifications/retention/cleanup")
def administrator_cleanup_notifications(x_admin_pin: str | None = Header(default=None)):
    """Delete expired notification rows and preserve retention evidence."""
    administrator = require_admin(x_admin_pin)
    if not has_permission(administrator, "admin:manage"):
        raise HTTPException(status_code=403, detail="Platform Administrator permission is required.")
    return cleanup_expired_notifications(administrator.get("email", "administrator"))


@app.put("/notifications/read-all")
def administrator_read_all_notifications(x_admin_pin: str | None = Header(default=None)):
    """Mark every unread notification as reviewed."""
    administrator = require_admin(x_admin_pin)
    return {
        "updated": mark_all_notifications_read(administrator.get("email", "administrator"))
    }


@app.get("/request-investigations/{request_id}")
def request_investigation(
    request_id: str,
    x_admin_pin: str | None = Header(default=None),
):
    """Return a redacted request lifecycle investigation bundle."""
    require_admin(x_admin_pin)
    result = build_request_investigation(request_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Tool request not found.")
    return result


@app.get("/search")
def global_search(
    q: str = Query(min_length=2, max_length=120),
    limit: int = Query(default=30, ge=1, le=50),
    x_admin_pin: str | None = Header(default=None),
):
    """Search permission-filtered control-plane records."""
    administrator = require_admin(x_admin_pin)
    return search_control_plane(q, administrator.get("permissions", []), limit)


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


def _platform_admin(token):
    actor = require_admin(token)
    if not has_permission(actor, "admin:manage"):
        raise HTTPException(status_code=403, detail="Platform administrator role is required.")
    return actor


@app.get("/enterprise-identity")
def enterprise_identity_overview(x_admin_pin: str | None = Header(default=None)):
    _platform_admin(x_admin_pin)
    return {"summary": identity_summary(), "providers": list_providers(),
            "mappings": list_role_mappings(), "workloads": list_workload_identities(),
            "elevations": list_elevations()}


@app.post("/enterprise-identity/providers", status_code=201)
def configure_identity_provider(payload: IdentityProviderRequest, x_admin_pin: str | None = Header(default=None)):
    actor = _platform_admin(x_admin_pin)
    try:
        return save_provider(actor["admin_id"], payload.name, payload.issuer, payload.client_id,
                             payload.allowed_domains, payload.enabled)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/enterprise-identity/mappings", status_code=201)
def configure_identity_mapping(payload: IdentityRoleMappingRequest, x_admin_pin: str | None = Header(default=None)):
    actor = _platform_admin(x_admin_pin)
    try:
        return add_role_mapping(actor["admin_id"], payload.provider_id, payload.claim_name,
                                payload.claim_value, payload.role, payload.priority)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/enterprise-identity/workloads", status_code=201)
def register_workload_identity(payload: WorkloadIdentityRequest, x_admin_pin: str | None = Header(default=None)):
    actor = _platform_admin(x_admin_pin)
    try:
        return create_workload_identity(actor["admin_id"], payload.name, payload.subject,
                                        payload.certificate_pem, payload.scopes, payload.expires_in_days)
    except (ValueError, sqlite3.IntegrityError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/enterprise-identity/elevations", status_code=201)
def create_elevation_request(payload: ElevationRequest, x_admin_pin: str | None = Header(default=None)):
    actor = require_admin(x_admin_pin)
    try:
        return request_elevation(actor["admin_id"], payload.role, payload.reason, payload.minutes)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/enterprise-identity/elevations/{elevation_id}/decision")
def review_elevation_request(elevation_id: str, payload: ElevationDecisionRequest,
                             x_admin_pin: str | None = Header(default=None)):
    actor = _platform_admin(x_admin_pin)
    try:
        return decide_elevation(actor["admin_id"], elevation_id, payload.approved)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/enterprise-identity/break-glass", status_code=201)
def emergency_identity_activation(payload: BreakGlassRequest, x_admin_pin: str | None = Header(default=None)):
    actor = require_admin(x_admin_pin)
    try:
        return activate_break_glass(actor["admin_id"], payload.reason, payload.minutes)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
