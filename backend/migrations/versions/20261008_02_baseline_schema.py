"""Baseline schema: every table GreyGuard creates (eagerly at startup, or lazily
on first use - e.g. admin_auth's tables, which the real startup lifespan never
calls `initialize_admin_auth()` for; this migration still creates them eagerly
so a fresh deployment does not depend on that lazy path).

Captured, not hand-transcribed: generated from `pg_dump --schema-only` against a
PostgreSQL database created by actually running every `initialize_*()` function
across backend/app (the same code path `db_compat.py` translates for
production) against a disposable rehearsal container (see
deployment/postgresql-rehearsal.yml), then verified three ways: (1) every
`CREATE TABLE IF NOT EXISTS` in the codebase has a matching table in the
capture and vice versa (80/80, zero missing either direction); (2) re-running
`alembic upgrade head` against an empty database and diffing the resulting
`pg_dump --schema-only` output against this original capture produces no
unexpected differences (only Alembic's own bookkeeping tables); (3) the core
backend test suite passes against a database created purely by this migration,
with no imperative initialization ever run. See docs/postgresql-migration.md
for the full procedure. Keep this process (capture, don't hand-write) for any
future rebaseline.
"""
from alembic import op

revision = "20261008_02"
down_revision = "20261005_01"
branch_labels = None
depends_on = None

STATEMENTS = [
    "COMMENT ON SCHEMA public IS ''",
    'CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA public',
    'CREATE TABLE public.abuse_events (\n    event_id text NOT NULL,\n    "timestamp" text NOT NULL,\n    category text NOT NULL,\n    event_type text NOT NULL,\n    severity text NOT NULL,\n    identifier_hint text NOT NULL,\n    request_count integer NOT NULL,\n    detail text NOT NULL\n)',
    'CREATE TABLE public.adapter_configs (\n    adapter_id text NOT NULL,\n    name text NOT NULL,\n    protocol text NOT NULL,\n    description text NOT NULL,\n    enabled integer DEFAULT 0 NOT NULL,\n    owner text,\n    purpose text,\n    allowed_actions_json text NOT NULL,\n    updated_at text NOT NULL,\n    updated_by text NOT NULL\n)',
    'CREATE TABLE public.adapter_events (\n    event_id bigint NOT NULL,\n    adapter_id text NOT NULL,\n    "timestamp" text NOT NULL,\n    actor text NOT NULL,\n    event_type text NOT NULL,\n    detail text NOT NULL\n)',
    'CREATE SEQUENCE public.adapter_events_event_id_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.adapter_events_event_id_seq OWNED BY public.adapter_events.event_id',
    'CREATE TABLE public.administrator_refresh_tokens (\n    refresh_id text NOT NULL,\n    family_id text NOT NULL,\n    session_id text NOT NULL,\n    token_hash text NOT NULL,\n    created_at text NOT NULL,\n    expires_at text NOT NULL,\n    used_at text,\n    revoked_at text,\n    replaced_by text\n)',
    'CREATE TABLE public.administrator_security_events (\n    event_id bigint NOT NULL,\n    admin_id text NOT NULL,\n    "timestamp" text NOT NULL,\n    event_type text NOT NULL,\n    detail text NOT NULL\n)',
    'CREATE SEQUENCE public.administrator_security_events_event_id_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.administrator_security_events_event_id_seq OWNED BY public.administrator_security_events.event_id',
    'CREATE TABLE public.administrator_sessions (\n    session_id text NOT NULL,\n    admin_id text NOT NULL,\n    token_hash text NOT NULL,\n    created_at text NOT NULL,\n    expires_at text NOT NULL,\n    revoked_at text,\n    device_name text,\n    ip_address text,\n    last_seen_at text,\n    elevated_until text\n)',
    "CREATE TABLE public.administrators (\n    admin_id text NOT NULL,\n    email public.citext NOT NULL,\n    display_name text NOT NULL,\n    role text NOT NULL,\n    password_salt text NOT NULL,\n    password_hash text NOT NULL,\n    status text DEFAULT 'ACTIVE'::text NOT NULL,\n    created_at text NOT NULL,\n    last_login_at text,\n    mfa_secret text,\n    mfa_enabled integer DEFAULT 0 NOT NULL,\n    password_expires_at text,\n    break_glass integer DEFAULT 0 NOT NULL,\n    sso_provider_id text\n)",
    'CREATE TABLE public.agent_credential_events (\n    id bigint NOT NULL,\n    agent_name text NOT NULL,\n    "timestamp" text NOT NULL,\n    event_type text NOT NULL,\n    actor text NOT NULL\n)',
    'CREATE SEQUENCE public.agent_credential_events_id_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.agent_credential_events_id_seq OWNED BY public.agent_credential_events.id',
    "CREATE TABLE public.agent_identities (\n    agent_name text NOT NULL,\n    credential_salt text NOT NULL,\n    credential_hash text NOT NULL,\n    scopes_json text NOT NULL,\n    credential_status text DEFAULT 'ACTIVE'::text NOT NULL,\n    created_at text NOT NULL,\n    rotated_at text,\n    revoked_at text\n)",
    'CREATE TABLE public.alert_notes (\n    id bigint NOT NULL,\n    alert_id text NOT NULL,\n    "timestamp" text NOT NULL,\n    actor text NOT NULL,\n    note text NOT NULL\n)',
    'CREATE SEQUENCE public.alert_notes_id_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.alert_notes_id_seq OWNED BY public.alert_notes.id',
    'CREATE TABLE public.approval_events (\n    id bigint NOT NULL,\n    request_id text NOT NULL,\n    "timestamp" text NOT NULL,\n    actor text NOT NULL,\n    decision text NOT NULL,\n    note text\n)',
    'CREATE SEQUENCE public.approval_events_id_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.approval_events_id_seq OWNED BY public.approval_events.id',
    'CREATE TABLE public.audit_events (\n    id bigint NOT NULL,\n    agent_name text DEFAULT \'legacy_agent\'::text NOT NULL,\n    "timestamp" text NOT NULL,\n    action text NOT NULL,\n    decision text NOT NULL,\n    approval text NOT NULL,\n    risk_added integer NOT NULL,\n    risk_score integer NOT NULL,\n    risk_level text NOT NULL,\n    agent_status text NOT NULL,\n    blocked_attempts integer NOT NULL\n)',
    'CREATE SEQUENCE public.audit_events_id_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.audit_events_id_seq OWNED BY public.audit_events.id',
    'CREATE TABLE public.audit_integrity_chain (\n    sequence bigint NOT NULL,\n    source_table text NOT NULL,\n    source_id text NOT NULL,\n    payload_hash text NOT NULL,\n    previous_hash text NOT NULL,\n    record_hash text NOT NULL,\n    sealed_at text NOT NULL\n)',
    'CREATE SEQUENCE public.audit_integrity_chain_sequence_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.audit_integrity_chain_sequence_seq OWNED BY public.audit_integrity_chain.sequence',
    'CREATE TABLE public.audit_integrity_checks (\n    check_id text NOT NULL,\n    checked_at text NOT NULL,\n    checked_by text NOT NULL,\n    valid integer NOT NULL,\n    records_checked integer NOT NULL,\n    first_invalid_sequence integer\n)',
    'CREATE TABLE public.audit_legal_holds (\n    hold_id text NOT NULL,\n    name text NOT NULL,\n    reason text NOT NULL,\n    agent_name text,\n    starts_at text,\n    ends_at text,\n    active integer NOT NULL,\n    created_at text NOT NULL,\n    created_by text NOT NULL,\n    released_at text,\n    released_by text\n)',
    'CREATE TABLE public.audit_retention_config (\n    config_id integer NOT NULL,\n    retention_days integer NOT NULL,\n    immutable_enabled integer NOT NULL,\n    updated_at text NOT NULL,\n    updated_by text NOT NULL,\n    CONSTRAINT audit_retention_config_config_id_check CHECK ((config_id = 1))\n)',
    'CREATE TABLE public.authentication_events (\n    id bigint NOT NULL,\n    "timestamp" text NOT NULL,\n    claimed_agent_name text,\n    authenticated_agent_name text,\n    action text,\n    outcome text NOT NULL,\n    reason text NOT NULL\n)',
    'CREATE SEQUENCE public.authentication_events_id_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.authentication_events_id_seq OWNED BY public.authentication_events.id',
    'CREATE TABLE public.break_glass_activations (\n    activation_id text NOT NULL,\n    admin_id text NOT NULL,\n    reason text NOT NULL,\n    activated_at text NOT NULL,\n    expires_at text NOT NULL,\n    closed_at text\n)',
    'CREATE TABLE public.browser_connectors (\n    connector_id text NOT NULL,\n    name text NOT NULL,\n    owner text NOT NULL,\n    purpose text NOT NULL,\n    enabled integer NOT NULL,\n    visible_indicator integer NOT NULL,\n    domains_json text NOT NULL,\n    consent_reference text NOT NULL,\n    created_at text NOT NULL,\n    disconnected_at text\n)',
    'CREATE TABLE public.callback_evidence (\n    callback_id text NOT NULL,\n    record_id text NOT NULL,\n    received_at text NOT NULL,\n    signature_valid integer NOT NULL,\n    payload_hash text NOT NULL,\n    outcome text NOT NULL\n)',
    'CREATE TABLE public.capability_removal_steps (\n    removal_id text NOT NULL,\n    step_order integer NOT NULL,\n    step_name text NOT NULL,\n    status text NOT NULL,\n    completed_by text,\n    completed_at text,\n    evidence text\n)',
    'CREATE TABLE public.capability_removals (\n    removal_id text NOT NULL,\n    capability text NOT NULL,\n    reason text NOT NULL,\n    status text NOT NULL,\n    requested_by text NOT NULL,\n    created_at text NOT NULL,\n    completed_at text,\n    emergency integer NOT NULL,\n    evidence_json text NOT NULL\n)',
    'CREATE TABLE public.compliance_reports (\n    report_id text NOT NULL,\n    title text NOT NULL,\n    created_by text NOT NULL,\n    created_at text NOT NULL,\n    filters_json text NOT NULL,\n    summary_json text NOT NULL,\n    evidence_json text NOT NULL,\n    evidence_hash text NOT NULL\n)',
    'CREATE TABLE public.defensive_response_plans (\n    response_id text NOT NULL,\n    action text NOT NULL,\n    target text NOT NULL,\n    reason text NOT NULL,\n    status text NOT NULL,\n    requested_by text NOT NULL,\n    approved_by text,\n    created_at text NOT NULL,\n    expires_at text NOT NULL,\n    evidence_preserved integer NOT NULL,\n    recovery_json text NOT NULL,\n    completed_at text\n)',
    'CREATE TABLE public.endpoint_collectors (\n    collector_id text NOT NULL,\n    name text NOT NULL,\n    owner text NOT NULL,\n    purpose text NOT NULL,\n    enabled integer NOT NULL,\n    visible_indicator integer NOT NULL,\n    consent_reference text NOT NULL,\n    permissions_json text NOT NULL,\n    directories_json text NOT NULL,\n    retention_days integer NOT NULL,\n    public_key_fingerprint text NOT NULL,\n    created_at text NOT NULL,\n    disabled_at text\n)',
    'CREATE TABLE public.endpoint_telemetry_events (\n    event_id text NOT NULL,\n    collector_id text NOT NULL,\n    event_type text NOT NULL,\n    observed_at text NOT NULL,\n    metadata_json text NOT NULL,\n    expires_at text NOT NULL\n)',
    'CREATE TABLE public.enterprise_identity_events (\n    event_id bigint NOT NULL,\n    "timestamp" text NOT NULL,\n    actor_id text NOT NULL,\n    event_type text NOT NULL,\n    detail text NOT NULL\n)',
    'CREATE SEQUENCE public.enterprise_identity_events_event_id_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.enterprise_identity_events_event_id_seq OWNED BY public.enterprise_identity_events.event_id',
    'CREATE TABLE public.execution_events (\n    id bigint NOT NULL,\n    request_id text NOT NULL,\n    "timestamp" text NOT NULL,\n    execution_status text NOT NULL,\n    result_json text NOT NULL\n)',
    'CREATE SEQUENCE public.execution_events_id_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.execution_events_id_seq OWNED BY public.execution_events.id',
    'CREATE TABLE public.expiring_approval_links (\n    link_id text NOT NULL,\n    request_id text NOT NULL,\n    token_hash text NOT NULL,\n    decision text NOT NULL,\n    expires_at text NOT NULL,\n    created_at text NOT NULL,\n    created_by text NOT NULL,\n    used_at text,\n    used_by text,\n    revoked_at text\n)',
    'CREATE TABLE public.export_destinations (\n    destination_id text NOT NULL,\n    name public.citext NOT NULL,\n    destination_type text NOT NULL,\n    endpoint text NOT NULL,\n    enabled integer NOT NULL,\n    signing_key_reference text,\n    minimization_profile text NOT NULL,\n    rate_limit_per_minute integer NOT NULL,\n    max_attempts integer NOT NULL,\n    created_at text NOT NULL,\n    created_by text NOT NULL,\n    last_success_at text,\n    last_failure_at text,\n    last_error text\n)',
    'CREATE TABLE public.export_queue (\n    export_id text NOT NULL,\n    destination_id text NOT NULL,\n    created_at text NOT NULL,\n    available_at text NOT NULL,\n    status text NOT NULL,\n    attempts integer NOT NULL,\n    event_type text NOT NULL,\n    payload_json text NOT NULL,\n    signature text,\n    delivered_at text,\n    last_error text,\n    claim_token text,\n    claimed_at text\n)',
    'CREATE TABLE public.external_incident_records (\n    record_id text NOT NULL,\n    destination_id text NOT NULL,\n    source_alert_id text NOT NULL,\n    created_at text NOT NULL,\n    status text NOT NULL,\n    payload_json text NOT NULL,\n    external_id text,\n    delivered_at text,\n    last_error text,\n    attempts integer DEFAULT 0 NOT NULL,\n    available_at text,\n    claim_token text,\n    claimed_at text\n)',
    'CREATE TABLE public.identity_providers (\n    provider_id text NOT NULL,\n    name text NOT NULL,\n    issuer text NOT NULL,\n    client_id text NOT NULL,\n    discovery_url text NOT NULL,\n    enabled integer NOT NULL,\n    allowed_domains text NOT NULL,\n    created_at text NOT NULL,\n    updated_at text NOT NULL\n)',
    'CREATE TABLE public.identity_role_mappings (\n    mapping_id text NOT NULL,\n    provider_id text NOT NULL,\n    claim_name text NOT NULL,\n    claim_value text NOT NULL,\n    greyguard_role text NOT NULL,\n    priority integer NOT NULL\n)',
    'CREATE TABLE public.incident_destinations (\n    destination_id text NOT NULL,\n    name public.citext NOT NULL,\n    system_type text NOT NULL,\n    endpoint text NOT NULL,\n    credential_reference text NOT NULL,\n    project_or_table text NOT NULL,\n    enabled integer NOT NULL,\n    created_at text NOT NULL,\n    created_by text NOT NULL,\n    last_success_at text,\n    last_failure_at text,\n    last_error text,\n    max_attempts integer DEFAULT 8 NOT NULL\n)',
    'CREATE TABLE public.incident_postmortems (\n    postmortem_id text NOT NULL,\n    incident_id text NOT NULL,\n    title text NOT NULL,\n    status text NOT NULL,\n    template_json text NOT NULL,\n    created_by text NOT NULL,\n    created_at text NOT NULL,\n    updated_at text NOT NULL\n)',
    'CREATE TABLE public.isolated_workspaces (\n    workspace_id text NOT NULL,\n    agent_name text NOT NULL,\n    path text NOT NULL,\n    created_at text NOT NULL,\n    status text NOT NULL,\n    destroyed_at text,\n    destroyed_by text\n)',
    'CREATE TABLE public.isolation_config (\n    config_id integer NOT NULL,\n    enabled integer NOT NULL,\n    image text NOT NULL,\n    cpu_limit real NOT NULL,\n    memory_mb integer NOT NULL,\n    pids_limit integer NOT NULL,\n    timeout_seconds integer NOT NULL,\n    updated_at text NOT NULL,\n    updated_by text NOT NULL,\n    CONSTRAINT isolation_config_config_id_check CHECK ((config_id = 1))\n)',
    'CREATE TABLE public.isolation_executions (\n    execution_id text NOT NULL,\n    job_type text NOT NULL,\n    created_at text NOT NULL,\n    started_by text NOT NULL,\n    status text NOT NULL,\n    container_name text NOT NULL,\n    finished_at text,\n    result text,\n    termination_reason text\n)',
    'CREATE TABLE public.isolation_operations_config (\n    config_id integer NOT NULL,\n    global_kill_switch integer NOT NULL,\n    network_enabled integer NOT NULL,\n    destination_allowlist_json text NOT NULL,\n    dns_allowlist_json text NOT NULL,\n    updated_at text NOT NULL,\n    updated_by text NOT NULL,\n    CONSTRAINT isolation_operations_config_config_id_check CHECK ((config_id = 1))\n)',
    'CREATE TABLE public.notification_deliveries (\n    delivery_id text NOT NULL,\n    destination_id text NOT NULL,\n    dedupe_key text NOT NULL,\n    created_at text NOT NULL,\n    available_at text NOT NULL,\n    status text NOT NULL,\n    attempts integer NOT NULL,\n    severity text NOT NULL,\n    subject text NOT NULL,\n    payload_json text NOT NULL,\n    delivered_at text,\n    last_error text,\n    claim_token text,\n    claimed_at text\n)',
    'CREATE TABLE public.notification_destinations (\n    destination_id text NOT NULL,\n    name public.citext NOT NULL,\n    channel text NOT NULL,\n    endpoint_reference text NOT NULL,\n    enabled integer NOT NULL,\n    minimum_severity text NOT NULL,\n    quiet_start_hour integer,\n    quiet_end_hour integer,\n    critical_bypass integer NOT NULL,\n    escalation_minutes integer NOT NULL,\n    created_at text NOT NULL,\n    created_by text NOT NULL,\n    max_attempts integer DEFAULT 8 NOT NULL\n)',
    'CREATE TABLE public.notification_retention_events (\n    id bigint NOT NULL,\n    "timestamp" text NOT NULL,\n    actor text NOT NULL,\n    action text NOT NULL,\n    retention_days integer NOT NULL,\n    deleted_count integer DEFAULT 0 NOT NULL\n)',
    'CREATE SEQUENCE public.notification_retention_events_id_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.notification_retention_events_id_seq OWNED BY public.notification_retention_events.id',
    'CREATE TABLE public.notification_retention_policy (\n    id integer NOT NULL,\n    retention_days integer NOT NULL,\n    updated_at text NOT NULL,\n    updated_by text NOT NULL,\n    CONSTRAINT notification_retention_policy_id_check CHECK ((id = 1))\n)',
    'CREATE TABLE public.notification_retention_tombstones (\n    source_alert_id text NOT NULL,\n    expired_at text NOT NULL\n)',
    'CREATE TABLE public.notification_templates (\n    template_id text NOT NULL,\n    name text NOT NULL,\n    event_type text NOT NULL,\n    subject_template text NOT NULL,\n    body_template text NOT NULL,\n    created_at text NOT NULL,\n    created_by text NOT NULL\n)',
    'CREATE TABLE public.observability_config (\n    config_id integer NOT NULL,\n    tracing_enabled integer NOT NULL,\n    metrics_enabled integer NOT NULL,\n    structured_logs_enabled integer NOT NULL,\n    sample_rate real NOT NULL,\n    retention_limit integer NOT NULL,\n    updated_at text NOT NULL,\n    updated_by text NOT NULL,\n    CONSTRAINT observability_config_config_id_check CHECK ((config_id = 1))\n)',
    'CREATE TABLE public.observability_correlations (\n    request_id text NOT NULL,\n    correlation_id text NOT NULL,\n    created_at text NOT NULL\n)',
    'CREATE TABLE public.observability_spans (\n    span_id text NOT NULL,\n    trace_id text NOT NULL,\n    correlation_id text NOT NULL,\n    "timestamp" text NOT NULL,\n    duration_ms real NOT NULL,\n    method text NOT NULL,\n    path text NOT NULL,\n    status_code integer NOT NULL,\n    sampled integer NOT NULL\n)',
    'CREATE TABLE public.oidc_login_attempts (\n    state text NOT NULL,\n    provider_id text NOT NULL,\n    nonce text NOT NULL,\n    code_verifier text NOT NULL,\n    redirect_uri text NOT NULL,\n    created_at text NOT NULL,\n    expires_at text NOT NULL,\n    consumed_at text\n)',
    'CREATE TABLE public.outbound_allowed_private_hosts (\n    host text NOT NULL,\n    reason text NOT NULL,\n    created_at text NOT NULL,\n    created_by text NOT NULL\n)',
    'CREATE TABLE public.outbound_delivery_evidence (\n    evidence_id text NOT NULL,\n    subsystem text NOT NULL,\n    record_id text NOT NULL,\n    event text NOT NULL,\n    attempt integer,\n    occurred_at text NOT NULL,\n    worker_id text,\n    detail_json text\n)',
    'CREATE TABLE public.policy_adapters (\n    adapter_type text NOT NULL,\n    enabled integer NOT NULL,\n    endpoint text,\n    owner text NOT NULL,\n    purpose text NOT NULL,\n    updated_by text NOT NULL,\n    updated_at text NOT NULL\n)',
    'CREATE TABLE public.policy_change_events (\n    event_id bigint NOT NULL,\n    policy_id text NOT NULL,\n    "timestamp" text NOT NULL,\n    actor text NOT NULL,\n    event_type text NOT NULL,\n    note text\n)',
    'CREATE SEQUENCE public.policy_change_events_event_id_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.policy_change_events_event_id_seq OWNED BY public.policy_change_events.event_id',
    'CREATE TABLE public.policy_emergency_controls (\n    control_id integer NOT NULL,\n    global_deny integer NOT NULL,\n    disabled_agents_json text NOT NULL,\n    disabled_tools_json text NOT NULL,\n    disabled_integrations_json text NOT NULL,\n    updated_by text NOT NULL,\n    updated_at text NOT NULL,\n    CONSTRAINT policy_emergency_controls_control_id_check CHECK ((control_id = 1))\n)',
    'CREATE TABLE public.policy_emergency_events (\n    event_id bigint NOT NULL,\n    "timestamp" text NOT NULL,\n    actor text NOT NULL,\n    global_deny integer NOT NULL,\n    detail text NOT NULL\n)',
    'CREATE SEQUENCE public.policy_emergency_events_event_id_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.policy_emergency_events_event_id_seq OWNED BY public.policy_emergency_events.event_id',
    'CREATE TABLE public.policy_integration_events (\n    event_id bigint NOT NULL,\n    "timestamp" text NOT NULL,\n    actor text NOT NULL,\n    event_type text NOT NULL,\n    detail text NOT NULL\n)',
    'CREATE SEQUENCE public.policy_integration_events_event_id_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.policy_integration_events_event_id_seq OWNED BY public.policy_integration_events.event_id',
    'CREATE TABLE public.policy_rollouts (\n    rollout_id text NOT NULL,\n    policy_id text NOT NULL,\n    percentage integer NOT NULL,\n    agent_allowlist_json text NOT NULL,\n    status text NOT NULL,\n    created_by text NOT NULL,\n    created_at text NOT NULL,\n    updated_at text NOT NULL\n)',
    'CREATE TABLE public.policy_test_cases (\n    test_id text NOT NULL,\n    policy_id text NOT NULL,\n    name text NOT NULL,\n    action text NOT NULL,\n    expected_decision text NOT NULL,\n    has_scope integer NOT NULL,\n    suspended integer NOT NULL,\n    created_at text NOT NULL\n)',
    'CREATE TABLE public.policy_versions (\n    policy_id text NOT NULL,\n    version_number integer NOT NULL,\n    status text NOT NULL,\n    permissions_json text NOT NULL,\n    risk_weights_json text NOT NULL,\n    max_blocked_attempts integer NOT NULL,\n    max_risk_score integer NOT NULL,\n    change_summary text NOT NULL,\n    created_by text NOT NULL,\n    created_at text NOT NULL,\n    submitted_at text,\n    approved_by text,\n    approved_at text,\n    published_at text,\n    supersedes_policy_id text\n)',
    'CREATE TABLE public.privilege_elevations (\n    elevation_id text NOT NULL,\n    admin_id text NOT NULL,\n    requested_role text NOT NULL,\n    reason text NOT NULL,\n    requested_at text NOT NULL,\n    expires_at text NOT NULL,\n    status text NOT NULL,\n    decided_by text,\n    decided_at text\n)',
    'CREATE TABLE public.quarantined_artifacts (\n    artifact_id text NOT NULL,\n    workspace_id text NOT NULL,\n    original_name text NOT NULL,\n    sha256 text NOT NULL,\n    size_bytes integer NOT NULL,\n    quarantine_path text NOT NULL,\n    status text NOT NULL,\n    scan_engine text,\n    scan_result text,\n    created_at text NOT NULL,\n    scanned_at text\n)',
    'CREATE TABLE public.rate_limit_counters (\n    identifier_hash text NOT NULL,\n    category text NOT NULL,\n    window_started_at text NOT NULL,\n    request_count integer DEFAULT 0 NOT NULL,\n    failed_attempts integer DEFAULT 0 NOT NULL,\n    blocked_until text,\n    last_seen_at text NOT NULL,\n    burst_recorded integer DEFAULT 0 NOT NULL\n)',
    'CREATE TABLE public.rate_limit_policies (\n    category text NOT NULL,\n    enabled integer DEFAULT 1 NOT NULL,\n    request_limit integer NOT NULL,\n    window_seconds integer NOT NULL,\n    block_seconds integer NOT NULL,\n    max_failed_attempts integer NOT NULL,\n    updated_at text NOT NULL,\n    updated_by text NOT NULL\n)',
    'CREATE TABLE public.report_schedules (\n    schedule_id text NOT NULL,\n    title text NOT NULL,\n    frequency text NOT NULL,\n    enabled integer NOT NULL,\n    next_run_at text NOT NULL,\n    created_by text NOT NULL,\n    created_at text NOT NULL,\n    disabled_at text,\n    claim_token text,\n    claimed_at text,\n    last_run_at text,\n    last_status text,\n    last_error text,\n    notify_destination_id text\n)',
    'CREATE TABLE public.secret_events (\n    event_id bigint NOT NULL,\n    secret_id text NOT NULL,\n    "timestamp" text NOT NULL,\n    actor text NOT NULL,\n    event_type text NOT NULL,\n    detail text\n)',
    'CREATE SEQUENCE public.secret_events_event_id_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.secret_events_event_id_seq OWNED BY public.secret_events.event_id',
    'CREATE TABLE public.secret_references (\n    secret_id text NOT NULL,\n    name public.citext NOT NULL,\n    provider text NOT NULL,\n    reference text NOT NULL,\n    status text NOT NULL,\n    created_by text NOT NULL,\n    created_at text NOT NULL,\n    rotated_at text,\n    revoked_at text,\n    last_accessed_at text,\n    access_count integer DEFAULT 0 NOT NULL,\n    rotation_interval_days integer,\n    next_rotation_at text\n)',
    "CREATE TABLE public.security_alerts (\n    alert_id text NOT NULL,\n    source_event_id text NOT NULL,\n    created_at text NOT NULL,\n    updated_at text NOT NULL,\n    agent_name text,\n    request_id text,\n    event_type text NOT NULL,\n    action text,\n    outcome text NOT NULL,\n    severity text NOT NULL,\n    status text DEFAULT 'OPEN'::text NOT NULL,\n    title text NOT NULL,\n    summary text NOT NULL,\n    assigned_to text,\n    resolution_note text,\n    evidence_json text NOT NULL\n)",
    'CREATE TABLE public.security_notifications (\n    notification_id text NOT NULL,\n    source_alert_id text NOT NULL,\n    created_at text NOT NULL,\n    severity text NOT NULL,\n    title text NOT NULL,\n    message text NOT NULL,\n    resource_path text NOT NULL,\n    is_read integer DEFAULT 0 NOT NULL,\n    read_at text,\n    read_by text\n)',
    'CREATE TABLE public.service_account_events (\n    event_id bigint NOT NULL,\n    account_id text NOT NULL,\n    key_id text,\n    "timestamp" text NOT NULL,\n    actor text NOT NULL,\n    event_type text NOT NULL,\n    detail text NOT NULL\n)',
    'CREATE SEQUENCE public.service_account_events_event_id_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.service_account_events_event_id_seq OWNED BY public.service_account_events.event_id',
    'CREATE TABLE public.service_account_keys (\n    key_id text NOT NULL,\n    account_id text NOT NULL,\n    key_prefix text NOT NULL,\n    key_hash text NOT NULL,\n    status text NOT NULL,\n    created_at text NOT NULL,\n    expires_at text,\n    revoked_at text,\n    last_used_at text,\n    use_count integer DEFAULT 0 NOT NULL\n)',
    'CREATE TABLE public.service_accounts (\n    account_id text NOT NULL,\n    name public.citext NOT NULL,\n    description text NOT NULL,\n    status text NOT NULL,\n    scopes_json text NOT NULL,\n    created_by text NOT NULL,\n    created_at text NOT NULL,\n    updated_at text NOT NULL,\n    expires_at text,\n    last_used_at text,\n    use_count integer DEFAULT 0 NOT NULL\n)',
    'CREATE TABLE public.simulation_config (\n    config_id integer NOT NULL,\n    enabled integer NOT NULL,\n    updated_at text NOT NULL,\n    updated_by text NOT NULL,\n    CONSTRAINT simulation_config_config_id_check CHECK ((config_id = 1))\n)',
    'CREATE TABLE public.simulation_runs (\n    run_id text NOT NULL,\n    scenario_id text NOT NULL,\n    requested_by text NOT NULL,\n    created_at text NOT NULL,\n    result_json text NOT NULL,\n    simulated integer NOT NULL,\n    CONSTRAINT simulation_runs_simulated_check CHECK ((simulated = 1))\n)',
    'CREATE TABLE public.threat_register (\n    threat_id text NOT NULL,\n    title text NOT NULL,\n    status text NOT NULL,\n    severity text NOT NULL,\n    asset text NOT NULL,\n    threat_actor text NOT NULL,\n    attack_path text NOT NULL,\n    existing_controls_json text NOT NULL,\n    residual_risk text NOT NULL,\n    test_evidence_json text NOT NULL,\n    incident_response text NOT NULL,\n    owner text NOT NULL,\n    review_date text,\n    updated_at text NOT NULL,\n    updated_by text NOT NULL\n)',
    'CREATE TABLE public.threat_register_history (\n    history_id bigint NOT NULL,\n    threat_id text NOT NULL,\n    changed_at text NOT NULL,\n    changed_by text NOT NULL,\n    snapshot_json text NOT NULL\n)',
    'CREATE SEQUENCE public.threat_register_history_history_id_seq\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1',
    'ALTER SEQUENCE public.threat_register_history_history_id_seq OWNED BY public.threat_register_history.history_id',
    'CREATE TABLE public.tool_requests (\n    request_id text NOT NULL,\n    agent_name text NOT NULL,\n    "timestamp" text NOT NULL,\n    updated_at text NOT NULL,\n    action text NOT NULL,\n    target text,\n    payload_json text NOT NULL,\n    dry_run integer DEFAULT 0 NOT NULL,\n    policy_decision text NOT NULL,\n    approval_status text NOT NULL,\n    execution_status text NOT NULL,\n    risk_added integer NOT NULL,\n    risk_score integer NOT NULL,\n    result_json text,\n    executed_at text\n)',
    'CREATE TABLE public.universal_capability_controls (\n    capability text NOT NULL,\n    enabled integer NOT NULL,\n    owner text NOT NULL,\n    purpose text NOT NULL,\n    permissions_json text NOT NULL,\n    agents_json text NOT NULL,\n    targets_json text NOT NULL,\n    expires_at text,\n    human_approval integer NOT NULL,\n    dry_run integer NOT NULL,\n    rate_limit integer NOT NULL,\n    resource_limit integer NOT NULL,\n    global_kill_switch integer NOT NULL,\n    disabled_agents_json text NOT NULL,\n    integration_kill_switch integer NOT NULL,\n    updated_at text NOT NULL,\n    updated_by text NOT NULL\n)',
    'CREATE TABLE public.universal_control_events (\n    event_id text NOT NULL,\n    capability text NOT NULL,\n    event_type text NOT NULL,\n    actor text NOT NULL,\n    "timestamp" text NOT NULL,\n    detail_json text NOT NULL\n)',
    'CREATE TABLE public.workload_identities (\n    workload_id text NOT NULL,\n    name text NOT NULL,\n    subject text NOT NULL,\n    certificate_thumbprint text NOT NULL,\n    scopes text NOT NULL,\n    status text NOT NULL,\n    created_at text NOT NULL,\n    expires_at text NOT NULL,\n    last_authenticated_at text,\n    agent_name text,\n    revoked_at text\n)',
    "ALTER TABLE ONLY public.adapter_events ALTER COLUMN event_id SET DEFAULT nextval('public.adapter_events_event_id_seq'::regclass)",
    "ALTER TABLE ONLY public.administrator_security_events ALTER COLUMN event_id SET DEFAULT nextval('public.administrator_security_events_event_id_seq'::regclass)",
    "ALTER TABLE ONLY public.agent_credential_events ALTER COLUMN id SET DEFAULT nextval('public.agent_credential_events_id_seq'::regclass)",
    "ALTER TABLE ONLY public.alert_notes ALTER COLUMN id SET DEFAULT nextval('public.alert_notes_id_seq'::regclass)",
    "ALTER TABLE ONLY public.approval_events ALTER COLUMN id SET DEFAULT nextval('public.approval_events_id_seq'::regclass)",
    "ALTER TABLE ONLY public.audit_events ALTER COLUMN id SET DEFAULT nextval('public.audit_events_id_seq'::regclass)",
    "ALTER TABLE ONLY public.audit_integrity_chain ALTER COLUMN sequence SET DEFAULT nextval('public.audit_integrity_chain_sequence_seq'::regclass)",
    "ALTER TABLE ONLY public.authentication_events ALTER COLUMN id SET DEFAULT nextval('public.authentication_events_id_seq'::regclass)",
    "ALTER TABLE ONLY public.enterprise_identity_events ALTER COLUMN event_id SET DEFAULT nextval('public.enterprise_identity_events_event_id_seq'::regclass)",
    "ALTER TABLE ONLY public.execution_events ALTER COLUMN id SET DEFAULT nextval('public.execution_events_id_seq'::regclass)",
    "ALTER TABLE ONLY public.notification_retention_events ALTER COLUMN id SET DEFAULT nextval('public.notification_retention_events_id_seq'::regclass)",
    "ALTER TABLE ONLY public.policy_change_events ALTER COLUMN event_id SET DEFAULT nextval('public.policy_change_events_event_id_seq'::regclass)",
    "ALTER TABLE ONLY public.policy_emergency_events ALTER COLUMN event_id SET DEFAULT nextval('public.policy_emergency_events_event_id_seq'::regclass)",
    "ALTER TABLE ONLY public.policy_integration_events ALTER COLUMN event_id SET DEFAULT nextval('public.policy_integration_events_event_id_seq'::regclass)",
    "ALTER TABLE ONLY public.secret_events ALTER COLUMN event_id SET DEFAULT nextval('public.secret_events_event_id_seq'::regclass)",
    "ALTER TABLE ONLY public.service_account_events ALTER COLUMN event_id SET DEFAULT nextval('public.service_account_events_event_id_seq'::regclass)",
    "ALTER TABLE ONLY public.threat_register_history ALTER COLUMN history_id SET DEFAULT nextval('public.threat_register_history_history_id_seq'::regclass)",
    'ALTER TABLE ONLY public.abuse_events\n    ADD CONSTRAINT abuse_events_pkey PRIMARY KEY (event_id)',
    'ALTER TABLE ONLY public.adapter_configs\n    ADD CONSTRAINT adapter_configs_pkey PRIMARY KEY (adapter_id)',
    'ALTER TABLE ONLY public.adapter_events\n    ADD CONSTRAINT adapter_events_pkey PRIMARY KEY (event_id)',
    'ALTER TABLE ONLY public.administrator_refresh_tokens\n    ADD CONSTRAINT administrator_refresh_tokens_pkey PRIMARY KEY (refresh_id)',
    'ALTER TABLE ONLY public.administrator_refresh_tokens\n    ADD CONSTRAINT administrator_refresh_tokens_token_hash_key UNIQUE (token_hash)',
    'ALTER TABLE ONLY public.administrator_security_events\n    ADD CONSTRAINT administrator_security_events_pkey PRIMARY KEY (event_id)',
    'ALTER TABLE ONLY public.administrator_sessions\n    ADD CONSTRAINT administrator_sessions_pkey PRIMARY KEY (session_id)',
    'ALTER TABLE ONLY public.administrator_sessions\n    ADD CONSTRAINT administrator_sessions_token_hash_key UNIQUE (token_hash)',
    'ALTER TABLE ONLY public.administrators\n    ADD CONSTRAINT administrators_email_key UNIQUE (email)',
    'ALTER TABLE ONLY public.administrators\n    ADD CONSTRAINT administrators_pkey PRIMARY KEY (admin_id)',
    'ALTER TABLE ONLY public.agent_credential_events\n    ADD CONSTRAINT agent_credential_events_pkey PRIMARY KEY (id)',
    'ALTER TABLE ONLY public.agent_identities\n    ADD CONSTRAINT agent_identities_pkey PRIMARY KEY (agent_name)',
    'ALTER TABLE ONLY public.alert_notes\n    ADD CONSTRAINT alert_notes_pkey PRIMARY KEY (id)',
    'ALTER TABLE ONLY public.approval_events\n    ADD CONSTRAINT approval_events_pkey PRIMARY KEY (id)',
    'ALTER TABLE ONLY public.audit_events\n    ADD CONSTRAINT audit_events_pkey PRIMARY KEY (id)',
    'ALTER TABLE ONLY public.audit_integrity_chain\n    ADD CONSTRAINT audit_integrity_chain_pkey PRIMARY KEY (sequence)',
    'ALTER TABLE ONLY public.audit_integrity_chain\n    ADD CONSTRAINT audit_integrity_chain_record_hash_key UNIQUE (record_hash)',
    'ALTER TABLE ONLY public.audit_integrity_chain\n    ADD CONSTRAINT audit_integrity_chain_source_table_source_id_key UNIQUE (source_table, source_id)',
    'ALTER TABLE ONLY public.audit_integrity_checks\n    ADD CONSTRAINT audit_integrity_checks_pkey PRIMARY KEY (check_id)',
    'ALTER TABLE ONLY public.audit_legal_holds\n    ADD CONSTRAINT audit_legal_holds_pkey PRIMARY KEY (hold_id)',
    'ALTER TABLE ONLY public.audit_retention_config\n    ADD CONSTRAINT audit_retention_config_pkey PRIMARY KEY (config_id)',
    'ALTER TABLE ONLY public.authentication_events\n    ADD CONSTRAINT authentication_events_pkey PRIMARY KEY (id)',
    'ALTER TABLE ONLY public.break_glass_activations\n    ADD CONSTRAINT break_glass_activations_pkey PRIMARY KEY (activation_id)',
    'ALTER TABLE ONLY public.browser_connectors\n    ADD CONSTRAINT browser_connectors_pkey PRIMARY KEY (connector_id)',
    'ALTER TABLE ONLY public.callback_evidence\n    ADD CONSTRAINT callback_evidence_pkey PRIMARY KEY (callback_id)',
    'ALTER TABLE ONLY public.capability_removal_steps\n    ADD CONSTRAINT capability_removal_steps_pkey PRIMARY KEY (removal_id, step_order)',
    'ALTER TABLE ONLY public.capability_removals\n    ADD CONSTRAINT capability_removals_pkey PRIMARY KEY (removal_id)',
    'ALTER TABLE ONLY public.compliance_reports\n    ADD CONSTRAINT compliance_reports_pkey PRIMARY KEY (report_id)',
    'ALTER TABLE ONLY public.defensive_response_plans\n    ADD CONSTRAINT defensive_response_plans_pkey PRIMARY KEY (response_id)',
    'ALTER TABLE ONLY public.endpoint_collectors\n    ADD CONSTRAINT endpoint_collectors_pkey PRIMARY KEY (collector_id)',
    'ALTER TABLE ONLY public.endpoint_telemetry_events\n    ADD CONSTRAINT endpoint_telemetry_events_pkey PRIMARY KEY (event_id)',
    'ALTER TABLE ONLY public.enterprise_identity_events\n    ADD CONSTRAINT enterprise_identity_events_pkey PRIMARY KEY (event_id)',
    'ALTER TABLE ONLY public.execution_events\n    ADD CONSTRAINT execution_events_pkey PRIMARY KEY (id)',
    'ALTER TABLE ONLY public.expiring_approval_links\n    ADD CONSTRAINT expiring_approval_links_pkey PRIMARY KEY (link_id)',
    'ALTER TABLE ONLY public.expiring_approval_links\n    ADD CONSTRAINT expiring_approval_links_token_hash_key UNIQUE (token_hash)',
    'ALTER TABLE ONLY public.export_destinations\n    ADD CONSTRAINT export_destinations_name_key UNIQUE (name)',
    'ALTER TABLE ONLY public.export_destinations\n    ADD CONSTRAINT export_destinations_pkey PRIMARY KEY (destination_id)',
    'ALTER TABLE ONLY public.export_queue\n    ADD CONSTRAINT export_queue_pkey PRIMARY KEY (export_id)',
    'ALTER TABLE ONLY public.external_incident_records\n    ADD CONSTRAINT external_incident_records_destination_id_source_alert_id_key UNIQUE (destination_id, source_alert_id)',
    'ALTER TABLE ONLY public.external_incident_records\n    ADD CONSTRAINT external_incident_records_pkey PRIMARY KEY (record_id)',
    'ALTER TABLE ONLY public.identity_providers\n    ADD CONSTRAINT identity_providers_issuer_key UNIQUE (issuer)',
    'ALTER TABLE ONLY public.identity_providers\n    ADD CONSTRAINT identity_providers_pkey PRIMARY KEY (provider_id)',
    'ALTER TABLE ONLY public.identity_role_mappings\n    ADD CONSTRAINT identity_role_mappings_pkey PRIMARY KEY (mapping_id)',
    'ALTER TABLE ONLY public.incident_destinations\n    ADD CONSTRAINT incident_destinations_name_key UNIQUE (name)',
    'ALTER TABLE ONLY public.incident_destinations\n    ADD CONSTRAINT incident_destinations_pkey PRIMARY KEY (destination_id)',
    'ALTER TABLE ONLY public.incident_postmortems\n    ADD CONSTRAINT incident_postmortems_pkey PRIMARY KEY (postmortem_id)',
    'ALTER TABLE ONLY public.isolated_workspaces\n    ADD CONSTRAINT isolated_workspaces_agent_name_key UNIQUE (agent_name)',
    'ALTER TABLE ONLY public.isolated_workspaces\n    ADD CONSTRAINT isolated_workspaces_pkey PRIMARY KEY (workspace_id)',
    'ALTER TABLE ONLY public.isolation_config\n    ADD CONSTRAINT isolation_config_pkey PRIMARY KEY (config_id)',
    'ALTER TABLE ONLY public.isolation_executions\n    ADD CONSTRAINT isolation_executions_pkey PRIMARY KEY (execution_id)',
    'ALTER TABLE ONLY public.isolation_operations_config\n    ADD CONSTRAINT isolation_operations_config_pkey PRIMARY KEY (config_id)',
    'ALTER TABLE ONLY public.notification_deliveries\n    ADD CONSTRAINT notification_deliveries_destination_id_dedupe_key_key UNIQUE (destination_id, dedupe_key)',
    'ALTER TABLE ONLY public.notification_deliveries\n    ADD CONSTRAINT notification_deliveries_pkey PRIMARY KEY (delivery_id)',
    'ALTER TABLE ONLY public.notification_destinations\n    ADD CONSTRAINT notification_destinations_name_key UNIQUE (name)',
    'ALTER TABLE ONLY public.notification_destinations\n    ADD CONSTRAINT notification_destinations_pkey PRIMARY KEY (destination_id)',
    'ALTER TABLE ONLY public.notification_retention_events\n    ADD CONSTRAINT notification_retention_events_pkey PRIMARY KEY (id)',
    'ALTER TABLE ONLY public.notification_retention_policy\n    ADD CONSTRAINT notification_retention_policy_pkey PRIMARY KEY (id)',
    'ALTER TABLE ONLY public.notification_retention_tombstones\n    ADD CONSTRAINT notification_retention_tombstones_pkey PRIMARY KEY (source_alert_id)',
    'ALTER TABLE ONLY public.notification_templates\n    ADD CONSTRAINT notification_templates_name_key UNIQUE (name)',
    'ALTER TABLE ONLY public.notification_templates\n    ADD CONSTRAINT notification_templates_pkey PRIMARY KEY (template_id)',
    'ALTER TABLE ONLY public.observability_config\n    ADD CONSTRAINT observability_config_pkey PRIMARY KEY (config_id)',
    'ALTER TABLE ONLY public.observability_correlations\n    ADD CONSTRAINT observability_correlations_pkey PRIMARY KEY (request_id)',
    'ALTER TABLE ONLY public.observability_spans\n    ADD CONSTRAINT observability_spans_pkey PRIMARY KEY (span_id)',
    'ALTER TABLE ONLY public.oidc_login_attempts\n    ADD CONSTRAINT oidc_login_attempts_pkey PRIMARY KEY (state)',
    'ALTER TABLE ONLY public.outbound_allowed_private_hosts\n    ADD CONSTRAINT outbound_allowed_private_hosts_pkey PRIMARY KEY (host)',
    'ALTER TABLE ONLY public.outbound_delivery_evidence\n    ADD CONSTRAINT outbound_delivery_evidence_pkey PRIMARY KEY (evidence_id)',
    'ALTER TABLE ONLY public.policy_adapters\n    ADD CONSTRAINT policy_adapters_pkey PRIMARY KEY (adapter_type)',
    'ALTER TABLE ONLY public.policy_change_events\n    ADD CONSTRAINT policy_change_events_pkey PRIMARY KEY (event_id)',
    'ALTER TABLE ONLY public.policy_emergency_controls\n    ADD CONSTRAINT policy_emergency_controls_pkey PRIMARY KEY (control_id)',
    'ALTER TABLE ONLY public.policy_emergency_events\n    ADD CONSTRAINT policy_emergency_events_pkey PRIMARY KEY (event_id)',
    'ALTER TABLE ONLY public.policy_integration_events\n    ADD CONSTRAINT policy_integration_events_pkey PRIMARY KEY (event_id)',
    'ALTER TABLE ONLY public.policy_rollouts\n    ADD CONSTRAINT policy_rollouts_pkey PRIMARY KEY (rollout_id)',
    'ALTER TABLE ONLY public.policy_test_cases\n    ADD CONSTRAINT policy_test_cases_pkey PRIMARY KEY (test_id)',
    'ALTER TABLE ONLY public.policy_versions\n    ADD CONSTRAINT policy_versions_pkey PRIMARY KEY (policy_id)',
    'ALTER TABLE ONLY public.policy_versions\n    ADD CONSTRAINT policy_versions_version_number_key UNIQUE (version_number)',
    'ALTER TABLE ONLY public.privilege_elevations\n    ADD CONSTRAINT privilege_elevations_pkey PRIMARY KEY (elevation_id)',
    'ALTER TABLE ONLY public.quarantined_artifacts\n    ADD CONSTRAINT quarantined_artifacts_pkey PRIMARY KEY (artifact_id)',
    'ALTER TABLE ONLY public.rate_limit_counters\n    ADD CONSTRAINT rate_limit_counters_pkey PRIMARY KEY (identifier_hash, category)',
    'ALTER TABLE ONLY public.rate_limit_policies\n    ADD CONSTRAINT rate_limit_policies_pkey PRIMARY KEY (category)',
    'ALTER TABLE ONLY public.report_schedules\n    ADD CONSTRAINT report_schedules_pkey PRIMARY KEY (schedule_id)',
    'ALTER TABLE ONLY public.secret_events\n    ADD CONSTRAINT secret_events_pkey PRIMARY KEY (event_id)',
    'ALTER TABLE ONLY public.secret_references\n    ADD CONSTRAINT secret_references_name_key UNIQUE (name)',
    'ALTER TABLE ONLY public.secret_references\n    ADD CONSTRAINT secret_references_pkey PRIMARY KEY (secret_id)',
    'ALTER TABLE ONLY public.security_alerts\n    ADD CONSTRAINT security_alerts_pkey PRIMARY KEY (alert_id)',
    'ALTER TABLE ONLY public.security_alerts\n    ADD CONSTRAINT security_alerts_source_event_id_key UNIQUE (source_event_id)',
    'ALTER TABLE ONLY public.security_notifications\n    ADD CONSTRAINT security_notifications_pkey PRIMARY KEY (notification_id)',
    'ALTER TABLE ONLY public.security_notifications\n    ADD CONSTRAINT security_notifications_source_alert_id_key UNIQUE (source_alert_id)',
    'ALTER TABLE ONLY public.service_account_events\n    ADD CONSTRAINT service_account_events_pkey PRIMARY KEY (event_id)',
    'ALTER TABLE ONLY public.service_account_keys\n    ADD CONSTRAINT service_account_keys_key_prefix_key UNIQUE (key_prefix)',
    'ALTER TABLE ONLY public.service_account_keys\n    ADD CONSTRAINT service_account_keys_pkey PRIMARY KEY (key_id)',
    'ALTER TABLE ONLY public.service_accounts\n    ADD CONSTRAINT service_accounts_name_key UNIQUE (name)',
    'ALTER TABLE ONLY public.service_accounts\n    ADD CONSTRAINT service_accounts_pkey PRIMARY KEY (account_id)',
    'ALTER TABLE ONLY public.simulation_config\n    ADD CONSTRAINT simulation_config_pkey PRIMARY KEY (config_id)',
    'ALTER TABLE ONLY public.simulation_runs\n    ADD CONSTRAINT simulation_runs_pkey PRIMARY KEY (run_id)',
    'ALTER TABLE ONLY public.threat_register_history\n    ADD CONSTRAINT threat_register_history_pkey PRIMARY KEY (history_id)',
    'ALTER TABLE ONLY public.threat_register\n    ADD CONSTRAINT threat_register_pkey PRIMARY KEY (threat_id)',
    'ALTER TABLE ONLY public.tool_requests\n    ADD CONSTRAINT tool_requests_pkey PRIMARY KEY (request_id)',
    'ALTER TABLE ONLY public.universal_capability_controls\n    ADD CONSTRAINT universal_capability_controls_pkey PRIMARY KEY (capability)',
    'ALTER TABLE ONLY public.universal_control_events\n    ADD CONSTRAINT universal_control_events_pkey PRIMARY KEY (event_id)',
    'ALTER TABLE ONLY public.workload_identities\n    ADD CONSTRAINT workload_identities_certificate_thumbprint_key UNIQUE (certificate_thumbprint)',
    'ALTER TABLE ONLY public.workload_identities\n    ADD CONSTRAINT workload_identities_name_key UNIQUE (name)',
    'ALTER TABLE ONLY public.workload_identities\n    ADD CONSTRAINT workload_identities_pkey PRIMARY KEY (workload_id)',
    'ALTER TABLE ONLY public.workload_identities\n    ADD CONSTRAINT workload_identities_subject_key UNIQUE (subject)',
    'CREATE INDEX idx_admin_sessions_token ON public.administrator_sessions USING btree (token_hash)',
    'CREATE INDEX idx_agent_credential_events_agent ON public.agent_credential_events USING btree (agent_name, id)',
    'CREATE INDEX idx_alert_severity ON public.security_alerts USING btree (severity)',
    'CREATE INDEX idx_alert_status ON public.security_alerts USING btree (status)',
    'CREATE INDEX idx_approval_events_request ON public.approval_events USING btree (request_id, id)',
    'CREATE INDEX idx_audit_events_agent ON public.audit_events USING btree (agent_name, id)',
    'CREATE INDEX idx_authentication_events_agent ON public.authentication_events USING btree (claimed_agent_name, id)',
    'CREATE INDEX idx_execution_events_request ON public.execution_events USING btree (request_id, id)',
    'CREATE INDEX idx_notification_unread ON public.security_notifications USING btree (is_read, created_at)',
    'CREATE INDEX idx_policy_change_events_policy ON public.policy_change_events USING btree (policy_id, event_id)',
    'CREATE INDEX idx_policy_versions_status ON public.policy_versions USING btree (status, version_number)',
    'CREATE INDEX idx_tool_requests_agent ON public.tool_requests USING btree (agent_name, "timestamp")',
    'CREATE INDEX idx_tool_requests_approval ON public.tool_requests USING btree (approval_status, "timestamp")',
    'CREATE INDEX idx_tool_requests_execution ON public.tool_requests USING btree (execution_status, "timestamp")',
    'ALTER TABLE ONLY public.administrator_refresh_tokens\n    ADD CONSTRAINT administrator_refresh_tokens_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.administrator_sessions(session_id)',
    'ALTER TABLE ONLY public.administrator_sessions\n    ADD CONSTRAINT administrator_sessions_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.administrators(admin_id)',
    'ALTER TABLE ONLY public.alert_notes\n    ADD CONSTRAINT alert_notes_alert_id_fkey FOREIGN KEY (alert_id) REFERENCES public.security_alerts(alert_id)',
    'ALTER TABLE ONLY public.approval_events\n    ADD CONSTRAINT approval_events_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.tool_requests(request_id)',
    'ALTER TABLE ONLY public.execution_events\n    ADD CONSTRAINT execution_events_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.tool_requests(request_id)',
    'ALTER TABLE ONLY public.export_queue\n    ADD CONSTRAINT export_queue_destination_id_fkey FOREIGN KEY (destination_id) REFERENCES public.export_destinations(destination_id)',
    'ALTER TABLE ONLY public.identity_role_mappings\n    ADD CONSTRAINT identity_role_mappings_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.identity_providers(provider_id)',
    'ALTER TABLE ONLY public.policy_change_events\n    ADD CONSTRAINT policy_change_events_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.policy_versions(policy_id)',
    'ALTER TABLE ONLY public.policy_test_cases\n    ADD CONSTRAINT policy_test_cases_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.policy_versions(policy_id)',
    'ALTER TABLE ONLY public.policy_versions\n    ADD CONSTRAINT policy_versions_supersedes_policy_id_fkey FOREIGN KEY (supersedes_policy_id) REFERENCES public.policy_versions(policy_id)',
    'ALTER TABLE ONLY public.secret_events\n    ADD CONSTRAINT secret_events_secret_id_fkey FOREIGN KEY (secret_id) REFERENCES public.secret_references(secret_id)',
    'ALTER TABLE ONLY public.service_account_keys\n    ADD CONSTRAINT service_account_keys_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.service_accounts(account_id)',
]


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    op.execute("DROP TABLE IF EXISTS public.workload_identities CASCADE")
    op.execute("DROP TABLE IF EXISTS public.universal_control_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.universal_capability_controls CASCADE")
    op.execute("DROP TABLE IF EXISTS public.tool_requests CASCADE")
    op.execute("DROP TABLE IF EXISTS public.threat_register_history CASCADE")
    op.execute("DROP TABLE IF EXISTS public.threat_register CASCADE")
    op.execute("DROP TABLE IF EXISTS public.simulation_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS public.simulation_config CASCADE")
    op.execute("DROP TABLE IF EXISTS public.service_accounts CASCADE")
    op.execute("DROP TABLE IF EXISTS public.service_account_keys CASCADE")
    op.execute("DROP TABLE IF EXISTS public.service_account_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.security_notifications CASCADE")
    op.execute("DROP TABLE IF EXISTS public.security_alerts CASCADE")
    op.execute("DROP TABLE IF EXISTS public.secret_references CASCADE")
    op.execute("DROP TABLE IF EXISTS public.secret_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.report_schedules CASCADE")
    op.execute("DROP TABLE IF EXISTS public.rate_limit_policies CASCADE")
    op.execute("DROP TABLE IF EXISTS public.rate_limit_counters CASCADE")
    op.execute("DROP TABLE IF EXISTS public.quarantined_artifacts CASCADE")
    op.execute("DROP TABLE IF EXISTS public.privilege_elevations CASCADE")
    op.execute("DROP TABLE IF EXISTS public.policy_versions CASCADE")
    op.execute("DROP TABLE IF EXISTS public.policy_test_cases CASCADE")
    op.execute("DROP TABLE IF EXISTS public.policy_rollouts CASCADE")
    op.execute("DROP TABLE IF EXISTS public.policy_integration_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.policy_emergency_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.policy_emergency_controls CASCADE")
    op.execute("DROP TABLE IF EXISTS public.policy_change_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.policy_adapters CASCADE")
    op.execute("DROP TABLE IF EXISTS public.outbound_delivery_evidence CASCADE")
    op.execute("DROP TABLE IF EXISTS public.outbound_allowed_private_hosts CASCADE")
    op.execute("DROP TABLE IF EXISTS public.oidc_login_attempts CASCADE")
    op.execute("DROP TABLE IF EXISTS public.observability_spans CASCADE")
    op.execute("DROP TABLE IF EXISTS public.observability_correlations CASCADE")
    op.execute("DROP TABLE IF EXISTS public.observability_config CASCADE")
    op.execute("DROP TABLE IF EXISTS public.notification_templates CASCADE")
    op.execute("DROP TABLE IF EXISTS public.notification_retention_tombstones CASCADE")
    op.execute("DROP TABLE IF EXISTS public.notification_retention_policy CASCADE")
    op.execute("DROP TABLE IF EXISTS public.notification_retention_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.notification_destinations CASCADE")
    op.execute("DROP TABLE IF EXISTS public.notification_deliveries CASCADE")
    op.execute("DROP TABLE IF EXISTS public.isolation_operations_config CASCADE")
    op.execute("DROP TABLE IF EXISTS public.isolation_executions CASCADE")
    op.execute("DROP TABLE IF EXISTS public.isolation_config CASCADE")
    op.execute("DROP TABLE IF EXISTS public.isolated_workspaces CASCADE")
    op.execute("DROP TABLE IF EXISTS public.incident_postmortems CASCADE")
    op.execute("DROP TABLE IF EXISTS public.incident_destinations CASCADE")
    op.execute("DROP TABLE IF EXISTS public.identity_role_mappings CASCADE")
    op.execute("DROP TABLE IF EXISTS public.identity_providers CASCADE")
    op.execute("DROP TABLE IF EXISTS public.external_incident_records CASCADE")
    op.execute("DROP TABLE IF EXISTS public.export_queue CASCADE")
    op.execute("DROP TABLE IF EXISTS public.export_destinations CASCADE")
    op.execute("DROP TABLE IF EXISTS public.expiring_approval_links CASCADE")
    op.execute("DROP TABLE IF EXISTS public.execution_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.enterprise_identity_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.endpoint_telemetry_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.endpoint_collectors CASCADE")
    op.execute("DROP TABLE IF EXISTS public.defensive_response_plans CASCADE")
    op.execute("DROP TABLE IF EXISTS public.compliance_reports CASCADE")
    op.execute("DROP TABLE IF EXISTS public.capability_removals CASCADE")
    op.execute("DROP TABLE IF EXISTS public.capability_removal_steps CASCADE")
    op.execute("DROP TABLE IF EXISTS public.callback_evidence CASCADE")
    op.execute("DROP TABLE IF EXISTS public.browser_connectors CASCADE")
    op.execute("DROP TABLE IF EXISTS public.break_glass_activations CASCADE")
    op.execute("DROP TABLE IF EXISTS public.authentication_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.audit_retention_config CASCADE")
    op.execute("DROP TABLE IF EXISTS public.audit_legal_holds CASCADE")
    op.execute("DROP TABLE IF EXISTS public.audit_integrity_checks CASCADE")
    op.execute("DROP TABLE IF EXISTS public.audit_integrity_chain CASCADE")
    op.execute("DROP TABLE IF EXISTS public.audit_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.approval_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.alert_notes CASCADE")
    op.execute("DROP TABLE IF EXISTS public.agent_identities CASCADE")
    op.execute("DROP TABLE IF EXISTS public.agent_credential_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.administrators CASCADE")
    op.execute("DROP TABLE IF EXISTS public.administrator_sessions CASCADE")
    op.execute("DROP TABLE IF EXISTS public.administrator_security_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.administrator_refresh_tokens CASCADE")
    op.execute("DROP TABLE IF EXISTS public.adapter_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.adapter_configs CASCADE")
    op.execute("DROP TABLE IF EXISTS public.abuse_events CASCADE")
    op.execute("DROP EXTENSION IF EXISTS citext CASCADE")
