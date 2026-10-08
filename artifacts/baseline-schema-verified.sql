--
-- PostgreSQL database dump
--

\restrict Oin9bhwUwE1Vj22M9ozkOf0qB4uvxGqm968bEwRvbIM6uEBzps2AlUfYiEFQTys

-- Dumped from database version 17.11
-- Dumped by pg_dump version 17.11

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

-- *not* creating schema, since initdb creates it


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS '';


--
-- Name: citext; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA public;


--
-- Name: EXTENSION citext; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION citext IS 'data type for case-insensitive character strings';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: abuse_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.abuse_events (
    event_id text NOT NULL,
    "timestamp" text NOT NULL,
    category text NOT NULL,
    event_type text NOT NULL,
    severity text NOT NULL,
    identifier_hint text NOT NULL,
    request_count integer NOT NULL,
    detail text NOT NULL
);


--
-- Name: adapter_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.adapter_configs (
    adapter_id text NOT NULL,
    name text NOT NULL,
    protocol text NOT NULL,
    description text NOT NULL,
    enabled integer DEFAULT 0 NOT NULL,
    owner text,
    purpose text,
    allowed_actions_json text NOT NULL,
    updated_at text NOT NULL,
    updated_by text NOT NULL
);


--
-- Name: adapter_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.adapter_events (
    event_id bigint NOT NULL,
    adapter_id text NOT NULL,
    "timestamp" text NOT NULL,
    actor text NOT NULL,
    event_type text NOT NULL,
    detail text NOT NULL
);


--
-- Name: adapter_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.adapter_events_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: adapter_events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.adapter_events_event_id_seq OWNED BY public.adapter_events.event_id;


--
-- Name: administrator_refresh_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.administrator_refresh_tokens (
    refresh_id text NOT NULL,
    family_id text NOT NULL,
    session_id text NOT NULL,
    token_hash text NOT NULL,
    created_at text NOT NULL,
    expires_at text NOT NULL,
    used_at text,
    revoked_at text,
    replaced_by text
);


--
-- Name: administrator_security_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.administrator_security_events (
    event_id bigint NOT NULL,
    admin_id text NOT NULL,
    "timestamp" text NOT NULL,
    event_type text NOT NULL,
    detail text NOT NULL
);


--
-- Name: administrator_security_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.administrator_security_events_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: administrator_security_events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.administrator_security_events_event_id_seq OWNED BY public.administrator_security_events.event_id;


--
-- Name: administrator_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.administrator_sessions (
    session_id text NOT NULL,
    admin_id text NOT NULL,
    token_hash text NOT NULL,
    created_at text NOT NULL,
    expires_at text NOT NULL,
    revoked_at text,
    device_name text,
    ip_address text,
    last_seen_at text,
    elevated_until text
);


--
-- Name: administrators; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.administrators (
    admin_id text NOT NULL,
    email public.citext NOT NULL,
    display_name text NOT NULL,
    role text NOT NULL,
    password_salt text NOT NULL,
    password_hash text NOT NULL,
    status text DEFAULT 'ACTIVE'::text NOT NULL,
    created_at text NOT NULL,
    last_login_at text,
    mfa_secret text,
    mfa_enabled integer DEFAULT 0 NOT NULL,
    password_expires_at text,
    break_glass integer DEFAULT 0 NOT NULL,
    sso_provider_id text
);


--
-- Name: agent_credential_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_credential_events (
    id bigint NOT NULL,
    agent_name text NOT NULL,
    "timestamp" text NOT NULL,
    event_type text NOT NULL,
    actor text NOT NULL
);


--
-- Name: agent_credential_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.agent_credential_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: agent_credential_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.agent_credential_events_id_seq OWNED BY public.agent_credential_events.id;


--
-- Name: agent_identities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_identities (
    agent_name text NOT NULL,
    credential_salt text NOT NULL,
    credential_hash text NOT NULL,
    scopes_json text NOT NULL,
    credential_status text DEFAULT 'ACTIVE'::text NOT NULL,
    created_at text NOT NULL,
    rotated_at text,
    revoked_at text
);


--
-- Name: alert_notes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alert_notes (
    id bigint NOT NULL,
    alert_id text NOT NULL,
    "timestamp" text NOT NULL,
    actor text NOT NULL,
    note text NOT NULL
);


--
-- Name: alert_notes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.alert_notes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: alert_notes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.alert_notes_id_seq OWNED BY public.alert_notes.id;


--
-- Name: approval_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.approval_events (
    id bigint NOT NULL,
    request_id text NOT NULL,
    "timestamp" text NOT NULL,
    actor text NOT NULL,
    decision text NOT NULL,
    note text
);


--
-- Name: approval_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.approval_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: approval_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.approval_events_id_seq OWNED BY public.approval_events.id;


--
-- Name: audit_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_events (
    id bigint NOT NULL,
    agent_name text DEFAULT 'legacy_agent'::text NOT NULL,
    "timestamp" text NOT NULL,
    action text NOT NULL,
    decision text NOT NULL,
    approval text NOT NULL,
    risk_added integer NOT NULL,
    risk_score integer NOT NULL,
    risk_level text NOT NULL,
    agent_status text NOT NULL,
    blocked_attempts integer NOT NULL
);


--
-- Name: audit_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_events_id_seq OWNED BY public.audit_events.id;


--
-- Name: audit_integrity_chain; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_integrity_chain (
    sequence bigint NOT NULL,
    source_table text NOT NULL,
    source_id text NOT NULL,
    payload_hash text NOT NULL,
    previous_hash text NOT NULL,
    record_hash text NOT NULL,
    sealed_at text NOT NULL
);


--
-- Name: audit_integrity_chain_sequence_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_integrity_chain_sequence_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_integrity_chain_sequence_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_integrity_chain_sequence_seq OWNED BY public.audit_integrity_chain.sequence;


--
-- Name: audit_integrity_checks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_integrity_checks (
    check_id text NOT NULL,
    checked_at text NOT NULL,
    checked_by text NOT NULL,
    valid integer NOT NULL,
    records_checked integer NOT NULL,
    first_invalid_sequence integer
);


--
-- Name: audit_legal_holds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_legal_holds (
    hold_id text NOT NULL,
    name text NOT NULL,
    reason text NOT NULL,
    agent_name text,
    starts_at text,
    ends_at text,
    active integer NOT NULL,
    created_at text NOT NULL,
    created_by text NOT NULL,
    released_at text,
    released_by text
);


--
-- Name: audit_retention_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_retention_config (
    config_id integer NOT NULL,
    retention_days integer NOT NULL,
    immutable_enabled integer NOT NULL,
    updated_at text NOT NULL,
    updated_by text NOT NULL,
    CONSTRAINT audit_retention_config_config_id_check CHECK ((config_id = 1))
);


--
-- Name: authentication_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.authentication_events (
    id bigint NOT NULL,
    "timestamp" text NOT NULL,
    claimed_agent_name text,
    authenticated_agent_name text,
    action text,
    outcome text NOT NULL,
    reason text NOT NULL
);


--
-- Name: authentication_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.authentication_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: authentication_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.authentication_events_id_seq OWNED BY public.authentication_events.id;


--
-- Name: break_glass_activations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.break_glass_activations (
    activation_id text NOT NULL,
    admin_id text NOT NULL,
    reason text NOT NULL,
    activated_at text NOT NULL,
    expires_at text NOT NULL,
    closed_at text
);


--
-- Name: browser_connectors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.browser_connectors (
    connector_id text NOT NULL,
    name text NOT NULL,
    owner text NOT NULL,
    purpose text NOT NULL,
    enabled integer NOT NULL,
    visible_indicator integer NOT NULL,
    domains_json text NOT NULL,
    consent_reference text NOT NULL,
    created_at text NOT NULL,
    disconnected_at text
);


--
-- Name: callback_evidence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.callback_evidence (
    callback_id text NOT NULL,
    record_id text NOT NULL,
    received_at text NOT NULL,
    signature_valid integer NOT NULL,
    payload_hash text NOT NULL,
    outcome text NOT NULL
);


--
-- Name: capability_removal_steps; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.capability_removal_steps (
    removal_id text NOT NULL,
    step_order integer NOT NULL,
    step_name text NOT NULL,
    status text NOT NULL,
    completed_by text,
    completed_at text,
    evidence text
);


--
-- Name: capability_removals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.capability_removals (
    removal_id text NOT NULL,
    capability text NOT NULL,
    reason text NOT NULL,
    status text NOT NULL,
    requested_by text NOT NULL,
    created_at text NOT NULL,
    completed_at text,
    emergency integer NOT NULL,
    evidence_json text NOT NULL
);


--
-- Name: compliance_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.compliance_reports (
    report_id text NOT NULL,
    title text NOT NULL,
    created_by text NOT NULL,
    created_at text NOT NULL,
    filters_json text NOT NULL,
    summary_json text NOT NULL,
    evidence_json text NOT NULL,
    evidence_hash text NOT NULL
);


--
-- Name: defensive_response_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.defensive_response_plans (
    response_id text NOT NULL,
    action text NOT NULL,
    target text NOT NULL,
    reason text NOT NULL,
    status text NOT NULL,
    requested_by text NOT NULL,
    approved_by text,
    created_at text NOT NULL,
    expires_at text NOT NULL,
    evidence_preserved integer NOT NULL,
    recovery_json text NOT NULL,
    completed_at text
);


--
-- Name: endpoint_collectors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.endpoint_collectors (
    collector_id text NOT NULL,
    name text NOT NULL,
    owner text NOT NULL,
    purpose text NOT NULL,
    enabled integer NOT NULL,
    visible_indicator integer NOT NULL,
    consent_reference text NOT NULL,
    permissions_json text NOT NULL,
    directories_json text NOT NULL,
    retention_days integer NOT NULL,
    public_key_fingerprint text NOT NULL,
    created_at text NOT NULL,
    disabled_at text
);


--
-- Name: endpoint_telemetry_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.endpoint_telemetry_events (
    event_id text NOT NULL,
    collector_id text NOT NULL,
    event_type text NOT NULL,
    observed_at text NOT NULL,
    metadata_json text NOT NULL,
    expires_at text NOT NULL
);


--
-- Name: enterprise_identity_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.enterprise_identity_events (
    event_id bigint NOT NULL,
    "timestamp" text NOT NULL,
    actor_id text NOT NULL,
    event_type text NOT NULL,
    detail text NOT NULL
);


--
-- Name: enterprise_identity_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.enterprise_identity_events_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: enterprise_identity_events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.enterprise_identity_events_event_id_seq OWNED BY public.enterprise_identity_events.event_id;


--
-- Name: execution_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.execution_events (
    id bigint NOT NULL,
    request_id text NOT NULL,
    "timestamp" text NOT NULL,
    execution_status text NOT NULL,
    result_json text NOT NULL
);


--
-- Name: execution_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.execution_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: execution_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.execution_events_id_seq OWNED BY public.execution_events.id;


--
-- Name: expiring_approval_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.expiring_approval_links (
    link_id text NOT NULL,
    request_id text NOT NULL,
    token_hash text NOT NULL,
    decision text NOT NULL,
    expires_at text NOT NULL,
    created_at text NOT NULL,
    created_by text NOT NULL,
    used_at text,
    used_by text,
    revoked_at text
);


--
-- Name: export_destinations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.export_destinations (
    destination_id text NOT NULL,
    name public.citext NOT NULL,
    destination_type text NOT NULL,
    endpoint text NOT NULL,
    enabled integer NOT NULL,
    signing_key_reference text,
    minimization_profile text NOT NULL,
    rate_limit_per_minute integer NOT NULL,
    max_attempts integer NOT NULL,
    created_at text NOT NULL,
    created_by text NOT NULL,
    last_success_at text,
    last_failure_at text,
    last_error text
);


--
-- Name: export_queue; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.export_queue (
    export_id text NOT NULL,
    destination_id text NOT NULL,
    created_at text NOT NULL,
    available_at text NOT NULL,
    status text NOT NULL,
    attempts integer NOT NULL,
    event_type text NOT NULL,
    payload_json text NOT NULL,
    signature text,
    delivered_at text,
    last_error text,
    claim_token text,
    claimed_at text
);


--
-- Name: external_incident_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.external_incident_records (
    record_id text NOT NULL,
    destination_id text NOT NULL,
    source_alert_id text NOT NULL,
    created_at text NOT NULL,
    status text NOT NULL,
    payload_json text NOT NULL,
    external_id text,
    delivered_at text,
    last_error text,
    attempts integer DEFAULT 0 NOT NULL,
    available_at text,
    claim_token text,
    claimed_at text
);


--
-- Name: identity_providers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.identity_providers (
    provider_id text NOT NULL,
    name text NOT NULL,
    issuer text NOT NULL,
    client_id text NOT NULL,
    discovery_url text NOT NULL,
    enabled integer NOT NULL,
    allowed_domains text NOT NULL,
    created_at text NOT NULL,
    updated_at text NOT NULL
);


--
-- Name: identity_role_mappings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.identity_role_mappings (
    mapping_id text NOT NULL,
    provider_id text NOT NULL,
    claim_name text NOT NULL,
    claim_value text NOT NULL,
    greyguard_role text NOT NULL,
    priority integer NOT NULL
);


--
-- Name: incident_destinations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.incident_destinations (
    destination_id text NOT NULL,
    name public.citext NOT NULL,
    system_type text NOT NULL,
    endpoint text NOT NULL,
    credential_reference text NOT NULL,
    project_or_table text NOT NULL,
    enabled integer NOT NULL,
    created_at text NOT NULL,
    created_by text NOT NULL,
    last_success_at text,
    last_failure_at text,
    last_error text,
    max_attempts integer DEFAULT 8 NOT NULL
);


--
-- Name: incident_postmortems; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.incident_postmortems (
    postmortem_id text NOT NULL,
    incident_id text NOT NULL,
    title text NOT NULL,
    status text NOT NULL,
    template_json text NOT NULL,
    created_by text NOT NULL,
    created_at text NOT NULL,
    updated_at text NOT NULL
);


--
-- Name: isolated_workspaces; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.isolated_workspaces (
    workspace_id text NOT NULL,
    agent_name text NOT NULL,
    path text NOT NULL,
    created_at text NOT NULL,
    status text NOT NULL,
    destroyed_at text,
    destroyed_by text
);


--
-- Name: isolation_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.isolation_config (
    config_id integer NOT NULL,
    enabled integer NOT NULL,
    image text NOT NULL,
    cpu_limit real NOT NULL,
    memory_mb integer NOT NULL,
    pids_limit integer NOT NULL,
    timeout_seconds integer NOT NULL,
    updated_at text NOT NULL,
    updated_by text NOT NULL,
    CONSTRAINT isolation_config_config_id_check CHECK ((config_id = 1))
);


--
-- Name: isolation_executions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.isolation_executions (
    execution_id text NOT NULL,
    job_type text NOT NULL,
    created_at text NOT NULL,
    started_by text NOT NULL,
    status text NOT NULL,
    container_name text NOT NULL,
    finished_at text,
    result text,
    termination_reason text
);


--
-- Name: isolation_operations_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.isolation_operations_config (
    config_id integer NOT NULL,
    global_kill_switch integer NOT NULL,
    network_enabled integer NOT NULL,
    destination_allowlist_json text NOT NULL,
    dns_allowlist_json text NOT NULL,
    updated_at text NOT NULL,
    updated_by text NOT NULL,
    CONSTRAINT isolation_operations_config_config_id_check CHECK ((config_id = 1))
);


--
-- Name: notification_deliveries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification_deliveries (
    delivery_id text NOT NULL,
    destination_id text NOT NULL,
    dedupe_key text NOT NULL,
    created_at text NOT NULL,
    available_at text NOT NULL,
    status text NOT NULL,
    attempts integer NOT NULL,
    severity text NOT NULL,
    subject text NOT NULL,
    payload_json text NOT NULL,
    delivered_at text,
    last_error text,
    claim_token text,
    claimed_at text
);


--
-- Name: notification_destinations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification_destinations (
    destination_id text NOT NULL,
    name public.citext NOT NULL,
    channel text NOT NULL,
    endpoint_reference text NOT NULL,
    enabled integer NOT NULL,
    minimum_severity text NOT NULL,
    quiet_start_hour integer,
    quiet_end_hour integer,
    critical_bypass integer NOT NULL,
    escalation_minutes integer NOT NULL,
    created_at text NOT NULL,
    created_by text NOT NULL,
    max_attempts integer DEFAULT 8 NOT NULL
);


--
-- Name: notification_retention_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification_retention_events (
    id bigint NOT NULL,
    "timestamp" text NOT NULL,
    actor text NOT NULL,
    action text NOT NULL,
    retention_days integer NOT NULL,
    deleted_count integer DEFAULT 0 NOT NULL
);


--
-- Name: notification_retention_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.notification_retention_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: notification_retention_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.notification_retention_events_id_seq OWNED BY public.notification_retention_events.id;


--
-- Name: notification_retention_policy; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification_retention_policy (
    id integer NOT NULL,
    retention_days integer NOT NULL,
    updated_at text NOT NULL,
    updated_by text NOT NULL,
    CONSTRAINT notification_retention_policy_id_check CHECK ((id = 1))
);


--
-- Name: notification_retention_tombstones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification_retention_tombstones (
    source_alert_id text NOT NULL,
    expired_at text NOT NULL
);


--
-- Name: notification_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification_templates (
    template_id text NOT NULL,
    name text NOT NULL,
    event_type text NOT NULL,
    subject_template text NOT NULL,
    body_template text NOT NULL,
    created_at text NOT NULL,
    created_by text NOT NULL
);


--
-- Name: observability_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.observability_config (
    config_id integer NOT NULL,
    tracing_enabled integer NOT NULL,
    metrics_enabled integer NOT NULL,
    structured_logs_enabled integer NOT NULL,
    sample_rate real NOT NULL,
    retention_limit integer NOT NULL,
    updated_at text NOT NULL,
    updated_by text NOT NULL,
    CONSTRAINT observability_config_config_id_check CHECK ((config_id = 1))
);


--
-- Name: observability_correlations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.observability_correlations (
    request_id text NOT NULL,
    correlation_id text NOT NULL,
    created_at text NOT NULL
);


--
-- Name: observability_spans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.observability_spans (
    span_id text NOT NULL,
    trace_id text NOT NULL,
    correlation_id text NOT NULL,
    "timestamp" text NOT NULL,
    duration_ms real NOT NULL,
    method text NOT NULL,
    path text NOT NULL,
    status_code integer NOT NULL,
    sampled integer NOT NULL
);


--
-- Name: oidc_login_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.oidc_login_attempts (
    state text NOT NULL,
    provider_id text NOT NULL,
    nonce text NOT NULL,
    code_verifier text NOT NULL,
    redirect_uri text NOT NULL,
    created_at text NOT NULL,
    expires_at text NOT NULL,
    consumed_at text
);


--
-- Name: outbound_allowed_private_hosts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.outbound_allowed_private_hosts (
    host text NOT NULL,
    reason text NOT NULL,
    created_at text NOT NULL,
    created_by text NOT NULL
);


--
-- Name: outbound_delivery_evidence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.outbound_delivery_evidence (
    evidence_id text NOT NULL,
    subsystem text NOT NULL,
    record_id text NOT NULL,
    event text NOT NULL,
    attempt integer,
    occurred_at text NOT NULL,
    worker_id text,
    detail_json text
);


--
-- Name: policy_adapters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.policy_adapters (
    adapter_type text NOT NULL,
    enabled integer NOT NULL,
    endpoint text,
    owner text NOT NULL,
    purpose text NOT NULL,
    updated_by text NOT NULL,
    updated_at text NOT NULL
);


--
-- Name: policy_change_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.policy_change_events (
    event_id bigint NOT NULL,
    policy_id text NOT NULL,
    "timestamp" text NOT NULL,
    actor text NOT NULL,
    event_type text NOT NULL,
    note text
);


--
-- Name: policy_change_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.policy_change_events_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: policy_change_events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.policy_change_events_event_id_seq OWNED BY public.policy_change_events.event_id;


--
-- Name: policy_emergency_controls; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.policy_emergency_controls (
    control_id integer NOT NULL,
    global_deny integer NOT NULL,
    disabled_agents_json text NOT NULL,
    disabled_tools_json text NOT NULL,
    disabled_integrations_json text NOT NULL,
    updated_by text NOT NULL,
    updated_at text NOT NULL,
    CONSTRAINT policy_emergency_controls_control_id_check CHECK ((control_id = 1))
);


--
-- Name: policy_emergency_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.policy_emergency_events (
    event_id bigint NOT NULL,
    "timestamp" text NOT NULL,
    actor text NOT NULL,
    global_deny integer NOT NULL,
    detail text NOT NULL
);


--
-- Name: policy_emergency_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.policy_emergency_events_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: policy_emergency_events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.policy_emergency_events_event_id_seq OWNED BY public.policy_emergency_events.event_id;


--
-- Name: policy_integration_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.policy_integration_events (
    event_id bigint NOT NULL,
    "timestamp" text NOT NULL,
    actor text NOT NULL,
    event_type text NOT NULL,
    detail text NOT NULL
);


--
-- Name: policy_integration_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.policy_integration_events_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: policy_integration_events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.policy_integration_events_event_id_seq OWNED BY public.policy_integration_events.event_id;


--
-- Name: policy_rollouts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.policy_rollouts (
    rollout_id text NOT NULL,
    policy_id text NOT NULL,
    percentage integer NOT NULL,
    agent_allowlist_json text NOT NULL,
    status text NOT NULL,
    created_by text NOT NULL,
    created_at text NOT NULL,
    updated_at text NOT NULL
);


--
-- Name: policy_test_cases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.policy_test_cases (
    test_id text NOT NULL,
    policy_id text NOT NULL,
    name text NOT NULL,
    action text NOT NULL,
    expected_decision text NOT NULL,
    has_scope integer NOT NULL,
    suspended integer NOT NULL,
    created_at text NOT NULL
);


--
-- Name: policy_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.policy_versions (
    policy_id text NOT NULL,
    version_number integer NOT NULL,
    status text NOT NULL,
    permissions_json text NOT NULL,
    risk_weights_json text NOT NULL,
    max_blocked_attempts integer NOT NULL,
    max_risk_score integer NOT NULL,
    change_summary text NOT NULL,
    created_by text NOT NULL,
    created_at text NOT NULL,
    submitted_at text,
    approved_by text,
    approved_at text,
    published_at text,
    supersedes_policy_id text
);


--
-- Name: privilege_elevations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.privilege_elevations (
    elevation_id text NOT NULL,
    admin_id text NOT NULL,
    requested_role text NOT NULL,
    reason text NOT NULL,
    requested_at text NOT NULL,
    expires_at text NOT NULL,
    status text NOT NULL,
    decided_by text,
    decided_at text
);


--
-- Name: quarantined_artifacts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quarantined_artifacts (
    artifact_id text NOT NULL,
    workspace_id text NOT NULL,
    original_name text NOT NULL,
    sha256 text NOT NULL,
    size_bytes integer NOT NULL,
    quarantine_path text NOT NULL,
    status text NOT NULL,
    scan_engine text,
    scan_result text,
    created_at text NOT NULL,
    scanned_at text
);


--
-- Name: rate_limit_counters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rate_limit_counters (
    identifier_hash text NOT NULL,
    category text NOT NULL,
    window_started_at text NOT NULL,
    request_count integer DEFAULT 0 NOT NULL,
    failed_attempts integer DEFAULT 0 NOT NULL,
    blocked_until text,
    last_seen_at text NOT NULL,
    burst_recorded integer DEFAULT 0 NOT NULL
);


--
-- Name: rate_limit_policies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rate_limit_policies (
    category text NOT NULL,
    enabled integer DEFAULT 1 NOT NULL,
    request_limit integer NOT NULL,
    window_seconds integer NOT NULL,
    block_seconds integer NOT NULL,
    max_failed_attempts integer NOT NULL,
    updated_at text NOT NULL,
    updated_by text NOT NULL
);


--
-- Name: report_schedules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.report_schedules (
    schedule_id text NOT NULL,
    title text NOT NULL,
    frequency text NOT NULL,
    enabled integer NOT NULL,
    next_run_at text NOT NULL,
    created_by text NOT NULL,
    created_at text NOT NULL,
    disabled_at text,
    claim_token text,
    claimed_at text,
    last_run_at text,
    last_status text,
    last_error text,
    notify_destination_id text
);


--
-- Name: secret_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.secret_events (
    event_id bigint NOT NULL,
    secret_id text NOT NULL,
    "timestamp" text NOT NULL,
    actor text NOT NULL,
    event_type text NOT NULL,
    detail text
);


--
-- Name: secret_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.secret_events_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: secret_events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.secret_events_event_id_seq OWNED BY public.secret_events.event_id;


--
-- Name: secret_references; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.secret_references (
    secret_id text NOT NULL,
    name public.citext NOT NULL,
    provider text NOT NULL,
    reference text NOT NULL,
    status text NOT NULL,
    created_by text NOT NULL,
    created_at text NOT NULL,
    rotated_at text,
    revoked_at text,
    last_accessed_at text,
    access_count integer DEFAULT 0 NOT NULL,
    rotation_interval_days integer,
    next_rotation_at text
);


--
-- Name: security_alerts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.security_alerts (
    alert_id text NOT NULL,
    source_event_id text NOT NULL,
    created_at text NOT NULL,
    updated_at text NOT NULL,
    agent_name text,
    request_id text,
    event_type text NOT NULL,
    action text,
    outcome text NOT NULL,
    severity text NOT NULL,
    status text DEFAULT 'OPEN'::text NOT NULL,
    title text NOT NULL,
    summary text NOT NULL,
    assigned_to text,
    resolution_note text,
    evidence_json text NOT NULL
);


--
-- Name: security_notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.security_notifications (
    notification_id text NOT NULL,
    source_alert_id text NOT NULL,
    created_at text NOT NULL,
    severity text NOT NULL,
    title text NOT NULL,
    message text NOT NULL,
    resource_path text NOT NULL,
    is_read integer DEFAULT 0 NOT NULL,
    read_at text,
    read_by text
);


--
-- Name: service_account_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_account_events (
    event_id bigint NOT NULL,
    account_id text NOT NULL,
    key_id text,
    "timestamp" text NOT NULL,
    actor text NOT NULL,
    event_type text NOT NULL,
    detail text NOT NULL
);


--
-- Name: service_account_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.service_account_events_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: service_account_events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.service_account_events_event_id_seq OWNED BY public.service_account_events.event_id;


--
-- Name: service_account_keys; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_account_keys (
    key_id text NOT NULL,
    account_id text NOT NULL,
    key_prefix text NOT NULL,
    key_hash text NOT NULL,
    status text NOT NULL,
    created_at text NOT NULL,
    expires_at text,
    revoked_at text,
    last_used_at text,
    use_count integer DEFAULT 0 NOT NULL
);


--
-- Name: service_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_accounts (
    account_id text NOT NULL,
    name public.citext NOT NULL,
    description text NOT NULL,
    status text NOT NULL,
    scopes_json text NOT NULL,
    created_by text NOT NULL,
    created_at text NOT NULL,
    updated_at text NOT NULL,
    expires_at text,
    last_used_at text,
    use_count integer DEFAULT 0 NOT NULL
);


--
-- Name: simulation_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.simulation_config (
    config_id integer NOT NULL,
    enabled integer NOT NULL,
    updated_at text NOT NULL,
    updated_by text NOT NULL,
    CONSTRAINT simulation_config_config_id_check CHECK ((config_id = 1))
);


--
-- Name: simulation_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.simulation_runs (
    run_id text NOT NULL,
    scenario_id text NOT NULL,
    requested_by text NOT NULL,
    created_at text NOT NULL,
    result_json text NOT NULL,
    simulated integer NOT NULL,
    CONSTRAINT simulation_runs_simulated_check CHECK ((simulated = 1))
);


--
-- Name: threat_register; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.threat_register (
    threat_id text NOT NULL,
    title text NOT NULL,
    status text NOT NULL,
    severity text NOT NULL,
    asset text NOT NULL,
    threat_actor text NOT NULL,
    attack_path text NOT NULL,
    existing_controls_json text NOT NULL,
    residual_risk text NOT NULL,
    test_evidence_json text NOT NULL,
    incident_response text NOT NULL,
    owner text NOT NULL,
    review_date text,
    updated_at text NOT NULL,
    updated_by text NOT NULL
);


--
-- Name: threat_register_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.threat_register_history (
    history_id bigint NOT NULL,
    threat_id text NOT NULL,
    changed_at text NOT NULL,
    changed_by text NOT NULL,
    snapshot_json text NOT NULL
);


--
-- Name: threat_register_history_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.threat_register_history_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: threat_register_history_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.threat_register_history_history_id_seq OWNED BY public.threat_register_history.history_id;


--
-- Name: tool_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tool_requests (
    request_id text NOT NULL,
    agent_name text NOT NULL,
    "timestamp" text NOT NULL,
    updated_at text NOT NULL,
    action text NOT NULL,
    target text,
    payload_json text NOT NULL,
    dry_run integer DEFAULT 0 NOT NULL,
    policy_decision text NOT NULL,
    approval_status text NOT NULL,
    execution_status text NOT NULL,
    risk_added integer NOT NULL,
    risk_score integer NOT NULL,
    result_json text,
    executed_at text
);


--
-- Name: universal_capability_controls; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.universal_capability_controls (
    capability text NOT NULL,
    enabled integer NOT NULL,
    owner text NOT NULL,
    purpose text NOT NULL,
    permissions_json text NOT NULL,
    agents_json text NOT NULL,
    targets_json text NOT NULL,
    expires_at text,
    human_approval integer NOT NULL,
    dry_run integer NOT NULL,
    rate_limit integer NOT NULL,
    resource_limit integer NOT NULL,
    global_kill_switch integer NOT NULL,
    disabled_agents_json text NOT NULL,
    integration_kill_switch integer NOT NULL,
    updated_at text NOT NULL,
    updated_by text NOT NULL
);


--
-- Name: universal_control_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.universal_control_events (
    event_id text NOT NULL,
    capability text NOT NULL,
    event_type text NOT NULL,
    actor text NOT NULL,
    "timestamp" text NOT NULL,
    detail_json text NOT NULL
);


--
-- Name: workload_identities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workload_identities (
    workload_id text NOT NULL,
    name text NOT NULL,
    subject text NOT NULL,
    certificate_thumbprint text NOT NULL,
    scopes text NOT NULL,
    status text NOT NULL,
    created_at text NOT NULL,
    expires_at text NOT NULL,
    last_authenticated_at text,
    agent_name text,
    revoked_at text
);


--
-- Name: adapter_events event_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adapter_events ALTER COLUMN event_id SET DEFAULT nextval('public.adapter_events_event_id_seq'::regclass);


--
-- Name: administrator_security_events event_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administrator_security_events ALTER COLUMN event_id SET DEFAULT nextval('public.administrator_security_events_event_id_seq'::regclass);


--
-- Name: agent_credential_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_credential_events ALTER COLUMN id SET DEFAULT nextval('public.agent_credential_events_id_seq'::regclass);


--
-- Name: alert_notes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alert_notes ALTER COLUMN id SET DEFAULT nextval('public.alert_notes_id_seq'::regclass);


--
-- Name: approval_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approval_events ALTER COLUMN id SET DEFAULT nextval('public.approval_events_id_seq'::regclass);


--
-- Name: audit_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events ALTER COLUMN id SET DEFAULT nextval('public.audit_events_id_seq'::regclass);


--
-- Name: audit_integrity_chain sequence; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_integrity_chain ALTER COLUMN sequence SET DEFAULT nextval('public.audit_integrity_chain_sequence_seq'::regclass);


--
-- Name: authentication_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authentication_events ALTER COLUMN id SET DEFAULT nextval('public.authentication_events_id_seq'::regclass);


--
-- Name: enterprise_identity_events event_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.enterprise_identity_events ALTER COLUMN event_id SET DEFAULT nextval('public.enterprise_identity_events_event_id_seq'::regclass);


--
-- Name: execution_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_events ALTER COLUMN id SET DEFAULT nextval('public.execution_events_id_seq'::regclass);


--
-- Name: notification_retention_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_retention_events ALTER COLUMN id SET DEFAULT nextval('public.notification_retention_events_id_seq'::regclass);


--
-- Name: policy_change_events event_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policy_change_events ALTER COLUMN event_id SET DEFAULT nextval('public.policy_change_events_event_id_seq'::regclass);


--
-- Name: policy_emergency_events event_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policy_emergency_events ALTER COLUMN event_id SET DEFAULT nextval('public.policy_emergency_events_event_id_seq'::regclass);


--
-- Name: policy_integration_events event_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policy_integration_events ALTER COLUMN event_id SET DEFAULT nextval('public.policy_integration_events_event_id_seq'::regclass);


--
-- Name: secret_events event_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secret_events ALTER COLUMN event_id SET DEFAULT nextval('public.secret_events_event_id_seq'::regclass);


--
-- Name: service_account_events event_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_account_events ALTER COLUMN event_id SET DEFAULT nextval('public.service_account_events_event_id_seq'::regclass);


--
-- Name: threat_register_history history_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.threat_register_history ALTER COLUMN history_id SET DEFAULT nextval('public.threat_register_history_history_id_seq'::regclass);


--
-- Name: abuse_events abuse_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.abuse_events
    ADD CONSTRAINT abuse_events_pkey PRIMARY KEY (event_id);


--
-- Name: adapter_configs adapter_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adapter_configs
    ADD CONSTRAINT adapter_configs_pkey PRIMARY KEY (adapter_id);


--
-- Name: adapter_events adapter_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adapter_events
    ADD CONSTRAINT adapter_events_pkey PRIMARY KEY (event_id);


--
-- Name: administrator_refresh_tokens administrator_refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administrator_refresh_tokens
    ADD CONSTRAINT administrator_refresh_tokens_pkey PRIMARY KEY (refresh_id);


--
-- Name: administrator_refresh_tokens administrator_refresh_tokens_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administrator_refresh_tokens
    ADD CONSTRAINT administrator_refresh_tokens_token_hash_key UNIQUE (token_hash);


--
-- Name: administrator_security_events administrator_security_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administrator_security_events
    ADD CONSTRAINT administrator_security_events_pkey PRIMARY KEY (event_id);


--
-- Name: administrator_sessions administrator_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administrator_sessions
    ADD CONSTRAINT administrator_sessions_pkey PRIMARY KEY (session_id);


--
-- Name: administrator_sessions administrator_sessions_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administrator_sessions
    ADD CONSTRAINT administrator_sessions_token_hash_key UNIQUE (token_hash);


--
-- Name: administrators administrators_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administrators
    ADD CONSTRAINT administrators_email_key UNIQUE (email);


--
-- Name: administrators administrators_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administrators
    ADD CONSTRAINT administrators_pkey PRIMARY KEY (admin_id);


--
-- Name: agent_credential_events agent_credential_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_credential_events
    ADD CONSTRAINT agent_credential_events_pkey PRIMARY KEY (id);


--
-- Name: agent_identities agent_identities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_identities
    ADD CONSTRAINT agent_identities_pkey PRIMARY KEY (agent_name);


--
-- Name: alert_notes alert_notes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alert_notes
    ADD CONSTRAINT alert_notes_pkey PRIMARY KEY (id);


--
-- Name: approval_events approval_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approval_events
    ADD CONSTRAINT approval_events_pkey PRIMARY KEY (id);


--
-- Name: audit_events audit_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_pkey PRIMARY KEY (id);


--
-- Name: audit_integrity_chain audit_integrity_chain_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_integrity_chain
    ADD CONSTRAINT audit_integrity_chain_pkey PRIMARY KEY (sequence);


--
-- Name: audit_integrity_chain audit_integrity_chain_record_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_integrity_chain
    ADD CONSTRAINT audit_integrity_chain_record_hash_key UNIQUE (record_hash);


--
-- Name: audit_integrity_chain audit_integrity_chain_source_table_source_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_integrity_chain
    ADD CONSTRAINT audit_integrity_chain_source_table_source_id_key UNIQUE (source_table, source_id);


--
-- Name: audit_integrity_checks audit_integrity_checks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_integrity_checks
    ADD CONSTRAINT audit_integrity_checks_pkey PRIMARY KEY (check_id);


--
-- Name: audit_legal_holds audit_legal_holds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_legal_holds
    ADD CONSTRAINT audit_legal_holds_pkey PRIMARY KEY (hold_id);


--
-- Name: audit_retention_config audit_retention_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_retention_config
    ADD CONSTRAINT audit_retention_config_pkey PRIMARY KEY (config_id);


--
-- Name: authentication_events authentication_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authentication_events
    ADD CONSTRAINT authentication_events_pkey PRIMARY KEY (id);


--
-- Name: break_glass_activations break_glass_activations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.break_glass_activations
    ADD CONSTRAINT break_glass_activations_pkey PRIMARY KEY (activation_id);


--
-- Name: browser_connectors browser_connectors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.browser_connectors
    ADD CONSTRAINT browser_connectors_pkey PRIMARY KEY (connector_id);


--
-- Name: callback_evidence callback_evidence_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.callback_evidence
    ADD CONSTRAINT callback_evidence_pkey PRIMARY KEY (callback_id);


--
-- Name: capability_removal_steps capability_removal_steps_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_removal_steps
    ADD CONSTRAINT capability_removal_steps_pkey PRIMARY KEY (removal_id, step_order);


--
-- Name: capability_removals capability_removals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_removals
    ADD CONSTRAINT capability_removals_pkey PRIMARY KEY (removal_id);


--
-- Name: compliance_reports compliance_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compliance_reports
    ADD CONSTRAINT compliance_reports_pkey PRIMARY KEY (report_id);


--
-- Name: defensive_response_plans defensive_response_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.defensive_response_plans
    ADD CONSTRAINT defensive_response_plans_pkey PRIMARY KEY (response_id);


--
-- Name: endpoint_collectors endpoint_collectors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.endpoint_collectors
    ADD CONSTRAINT endpoint_collectors_pkey PRIMARY KEY (collector_id);


--
-- Name: endpoint_telemetry_events endpoint_telemetry_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.endpoint_telemetry_events
    ADD CONSTRAINT endpoint_telemetry_events_pkey PRIMARY KEY (event_id);


--
-- Name: enterprise_identity_events enterprise_identity_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.enterprise_identity_events
    ADD CONSTRAINT enterprise_identity_events_pkey PRIMARY KEY (event_id);


--
-- Name: execution_events execution_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_events
    ADD CONSTRAINT execution_events_pkey PRIMARY KEY (id);


--
-- Name: expiring_approval_links expiring_approval_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expiring_approval_links
    ADD CONSTRAINT expiring_approval_links_pkey PRIMARY KEY (link_id);


--
-- Name: expiring_approval_links expiring_approval_links_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expiring_approval_links
    ADD CONSTRAINT expiring_approval_links_token_hash_key UNIQUE (token_hash);


--
-- Name: export_destinations export_destinations_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.export_destinations
    ADD CONSTRAINT export_destinations_name_key UNIQUE (name);


--
-- Name: export_destinations export_destinations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.export_destinations
    ADD CONSTRAINT export_destinations_pkey PRIMARY KEY (destination_id);


--
-- Name: export_queue export_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.export_queue
    ADD CONSTRAINT export_queue_pkey PRIMARY KEY (export_id);


--
-- Name: external_incident_records external_incident_records_destination_id_source_alert_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_incident_records
    ADD CONSTRAINT external_incident_records_destination_id_source_alert_id_key UNIQUE (destination_id, source_alert_id);


--
-- Name: external_incident_records external_incident_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_incident_records
    ADD CONSTRAINT external_incident_records_pkey PRIMARY KEY (record_id);


--
-- Name: identity_providers identity_providers_issuer_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.identity_providers
    ADD CONSTRAINT identity_providers_issuer_key UNIQUE (issuer);


--
-- Name: identity_providers identity_providers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.identity_providers
    ADD CONSTRAINT identity_providers_pkey PRIMARY KEY (provider_id);


--
-- Name: identity_role_mappings identity_role_mappings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.identity_role_mappings
    ADD CONSTRAINT identity_role_mappings_pkey PRIMARY KEY (mapping_id);


--
-- Name: incident_destinations incident_destinations_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_destinations
    ADD CONSTRAINT incident_destinations_name_key UNIQUE (name);


--
-- Name: incident_destinations incident_destinations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_destinations
    ADD CONSTRAINT incident_destinations_pkey PRIMARY KEY (destination_id);


--
-- Name: incident_postmortems incident_postmortems_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_postmortems
    ADD CONSTRAINT incident_postmortems_pkey PRIMARY KEY (postmortem_id);


--
-- Name: isolated_workspaces isolated_workspaces_agent_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.isolated_workspaces
    ADD CONSTRAINT isolated_workspaces_agent_name_key UNIQUE (agent_name);


--
-- Name: isolated_workspaces isolated_workspaces_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.isolated_workspaces
    ADD CONSTRAINT isolated_workspaces_pkey PRIMARY KEY (workspace_id);


--
-- Name: isolation_config isolation_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.isolation_config
    ADD CONSTRAINT isolation_config_pkey PRIMARY KEY (config_id);


--
-- Name: isolation_executions isolation_executions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.isolation_executions
    ADD CONSTRAINT isolation_executions_pkey PRIMARY KEY (execution_id);


--
-- Name: isolation_operations_config isolation_operations_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.isolation_operations_config
    ADD CONSTRAINT isolation_operations_config_pkey PRIMARY KEY (config_id);


--
-- Name: notification_deliveries notification_deliveries_destination_id_dedupe_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_deliveries
    ADD CONSTRAINT notification_deliveries_destination_id_dedupe_key_key UNIQUE (destination_id, dedupe_key);


--
-- Name: notification_deliveries notification_deliveries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_deliveries
    ADD CONSTRAINT notification_deliveries_pkey PRIMARY KEY (delivery_id);


--
-- Name: notification_destinations notification_destinations_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_destinations
    ADD CONSTRAINT notification_destinations_name_key UNIQUE (name);


--
-- Name: notification_destinations notification_destinations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_destinations
    ADD CONSTRAINT notification_destinations_pkey PRIMARY KEY (destination_id);


--
-- Name: notification_retention_events notification_retention_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_retention_events
    ADD CONSTRAINT notification_retention_events_pkey PRIMARY KEY (id);


--
-- Name: notification_retention_policy notification_retention_policy_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_retention_policy
    ADD CONSTRAINT notification_retention_policy_pkey PRIMARY KEY (id);


--
-- Name: notification_retention_tombstones notification_retention_tombstones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_retention_tombstones
    ADD CONSTRAINT notification_retention_tombstones_pkey PRIMARY KEY (source_alert_id);


--
-- Name: notification_templates notification_templates_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_templates
    ADD CONSTRAINT notification_templates_name_key UNIQUE (name);


--
-- Name: notification_templates notification_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_templates
    ADD CONSTRAINT notification_templates_pkey PRIMARY KEY (template_id);


--
-- Name: observability_config observability_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.observability_config
    ADD CONSTRAINT observability_config_pkey PRIMARY KEY (config_id);


--
-- Name: observability_correlations observability_correlations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.observability_correlations
    ADD CONSTRAINT observability_correlations_pkey PRIMARY KEY (request_id);


--
-- Name: observability_spans observability_spans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.observability_spans
    ADD CONSTRAINT observability_spans_pkey PRIMARY KEY (span_id);


--
-- Name: oidc_login_attempts oidc_login_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oidc_login_attempts
    ADD CONSTRAINT oidc_login_attempts_pkey PRIMARY KEY (state);


--
-- Name: outbound_allowed_private_hosts outbound_allowed_private_hosts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outbound_allowed_private_hosts
    ADD CONSTRAINT outbound_allowed_private_hosts_pkey PRIMARY KEY (host);


--
-- Name: outbound_delivery_evidence outbound_delivery_evidence_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outbound_delivery_evidence
    ADD CONSTRAINT outbound_delivery_evidence_pkey PRIMARY KEY (evidence_id);


--
-- Name: policy_adapters policy_adapters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policy_adapters
    ADD CONSTRAINT policy_adapters_pkey PRIMARY KEY (adapter_type);


--
-- Name: policy_change_events policy_change_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policy_change_events
    ADD CONSTRAINT policy_change_events_pkey PRIMARY KEY (event_id);


--
-- Name: policy_emergency_controls policy_emergency_controls_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policy_emergency_controls
    ADD CONSTRAINT policy_emergency_controls_pkey PRIMARY KEY (control_id);


--
-- Name: policy_emergency_events policy_emergency_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policy_emergency_events
    ADD CONSTRAINT policy_emergency_events_pkey PRIMARY KEY (event_id);


--
-- Name: policy_integration_events policy_integration_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policy_integration_events
    ADD CONSTRAINT policy_integration_events_pkey PRIMARY KEY (event_id);


--
-- Name: policy_rollouts policy_rollouts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policy_rollouts
    ADD CONSTRAINT policy_rollouts_pkey PRIMARY KEY (rollout_id);


--
-- Name: policy_test_cases policy_test_cases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policy_test_cases
    ADD CONSTRAINT policy_test_cases_pkey PRIMARY KEY (test_id);


--
-- Name: policy_versions policy_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policy_versions
    ADD CONSTRAINT policy_versions_pkey PRIMARY KEY (policy_id);


--
-- Name: policy_versions policy_versions_version_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policy_versions
    ADD CONSTRAINT policy_versions_version_number_key UNIQUE (version_number);


--
-- Name: privilege_elevations privilege_elevations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.privilege_elevations
    ADD CONSTRAINT privilege_elevations_pkey PRIMARY KEY (elevation_id);


--
-- Name: quarantined_artifacts quarantined_artifacts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quarantined_artifacts
    ADD CONSTRAINT quarantined_artifacts_pkey PRIMARY KEY (artifact_id);


--
-- Name: rate_limit_counters rate_limit_counters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rate_limit_counters
    ADD CONSTRAINT rate_limit_counters_pkey PRIMARY KEY (identifier_hash, category);


--
-- Name: rate_limit_policies rate_limit_policies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rate_limit_policies
    ADD CONSTRAINT rate_limit_policies_pkey PRIMARY KEY (category);


--
-- Name: report_schedules report_schedules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_schedules
    ADD CONSTRAINT report_schedules_pkey PRIMARY KEY (schedule_id);


--
-- Name: secret_events secret_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secret_events
    ADD CONSTRAINT secret_events_pkey PRIMARY KEY (event_id);


--
-- Name: secret_references secret_references_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secret_references
    ADD CONSTRAINT secret_references_name_key UNIQUE (name);


--
-- Name: secret_references secret_references_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secret_references
    ADD CONSTRAINT secret_references_pkey PRIMARY KEY (secret_id);


--
-- Name: security_alerts security_alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_alerts
    ADD CONSTRAINT security_alerts_pkey PRIMARY KEY (alert_id);


--
-- Name: security_alerts security_alerts_source_event_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_alerts
    ADD CONSTRAINT security_alerts_source_event_id_key UNIQUE (source_event_id);


--
-- Name: security_notifications security_notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_notifications
    ADD CONSTRAINT security_notifications_pkey PRIMARY KEY (notification_id);


--
-- Name: security_notifications security_notifications_source_alert_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_notifications
    ADD CONSTRAINT security_notifications_source_alert_id_key UNIQUE (source_alert_id);


--
-- Name: service_account_events service_account_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_account_events
    ADD CONSTRAINT service_account_events_pkey PRIMARY KEY (event_id);


--
-- Name: service_account_keys service_account_keys_key_prefix_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_account_keys
    ADD CONSTRAINT service_account_keys_key_prefix_key UNIQUE (key_prefix);


--
-- Name: service_account_keys service_account_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_account_keys
    ADD CONSTRAINT service_account_keys_pkey PRIMARY KEY (key_id);


--
-- Name: service_accounts service_accounts_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_accounts
    ADD CONSTRAINT service_accounts_name_key UNIQUE (name);


--
-- Name: service_accounts service_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_accounts
    ADD CONSTRAINT service_accounts_pkey PRIMARY KEY (account_id);


--
-- Name: simulation_config simulation_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.simulation_config
    ADD CONSTRAINT simulation_config_pkey PRIMARY KEY (config_id);


--
-- Name: simulation_runs simulation_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.simulation_runs
    ADD CONSTRAINT simulation_runs_pkey PRIMARY KEY (run_id);


--
-- Name: threat_register_history threat_register_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.threat_register_history
    ADD CONSTRAINT threat_register_history_pkey PRIMARY KEY (history_id);


--
-- Name: threat_register threat_register_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.threat_register
    ADD CONSTRAINT threat_register_pkey PRIMARY KEY (threat_id);


--
-- Name: tool_requests tool_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tool_requests
    ADD CONSTRAINT tool_requests_pkey PRIMARY KEY (request_id);


--
-- Name: universal_capability_controls universal_capability_controls_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.universal_capability_controls
    ADD CONSTRAINT universal_capability_controls_pkey PRIMARY KEY (capability);


--
-- Name: universal_control_events universal_control_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.universal_control_events
    ADD CONSTRAINT universal_control_events_pkey PRIMARY KEY (event_id);


--
-- Name: workload_identities workload_identities_certificate_thumbprint_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workload_identities
    ADD CONSTRAINT workload_identities_certificate_thumbprint_key UNIQUE (certificate_thumbprint);


--
-- Name: workload_identities workload_identities_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workload_identities
    ADD CONSTRAINT workload_identities_name_key UNIQUE (name);


--
-- Name: workload_identities workload_identities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workload_identities
    ADD CONSTRAINT workload_identities_pkey PRIMARY KEY (workload_id);


--
-- Name: workload_identities workload_identities_subject_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workload_identities
    ADD CONSTRAINT workload_identities_subject_key UNIQUE (subject);


--
-- Name: idx_admin_sessions_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_admin_sessions_token ON public.administrator_sessions USING btree (token_hash);


--
-- Name: idx_agent_credential_events_agent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_agent_credential_events_agent ON public.agent_credential_events USING btree (agent_name, id);


--
-- Name: idx_alert_severity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_alert_severity ON public.security_alerts USING btree (severity);


--
-- Name: idx_alert_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_alert_status ON public.security_alerts USING btree (status);


--
-- Name: idx_approval_events_request; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_approval_events_request ON public.approval_events USING btree (request_id, id);


--
-- Name: idx_audit_events_agent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_events_agent ON public.audit_events USING btree (agent_name, id);


--
-- Name: idx_authentication_events_agent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_authentication_events_agent ON public.authentication_events USING btree (claimed_agent_name, id);


--
-- Name: idx_execution_events_request; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_execution_events_request ON public.execution_events USING btree (request_id, id);


--
-- Name: idx_notification_unread; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notification_unread ON public.security_notifications USING btree (is_read, created_at);


--
-- Name: idx_policy_change_events_policy; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_policy_change_events_policy ON public.policy_change_events USING btree (policy_id, event_id);


--
-- Name: idx_policy_versions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_policy_versions_status ON public.policy_versions USING btree (status, version_number);


--
-- Name: idx_tool_requests_agent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tool_requests_agent ON public.tool_requests USING btree (agent_name, "timestamp");


--
-- Name: idx_tool_requests_approval; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tool_requests_approval ON public.tool_requests USING btree (approval_status, "timestamp");


--
-- Name: idx_tool_requests_execution; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tool_requests_execution ON public.tool_requests USING btree (execution_status, "timestamp");


--
-- Name: administrator_refresh_tokens administrator_refresh_tokens_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administrator_refresh_tokens
    ADD CONSTRAINT administrator_refresh_tokens_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.administrator_sessions(session_id);


--
-- Name: administrator_sessions administrator_sessions_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administrator_sessions
    ADD CONSTRAINT administrator_sessions_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.administrators(admin_id);


--
-- Name: alert_notes alert_notes_alert_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alert_notes
    ADD CONSTRAINT alert_notes_alert_id_fkey FOREIGN KEY (alert_id) REFERENCES public.security_alerts(alert_id);


--
-- Name: approval_events approval_events_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approval_events
    ADD CONSTRAINT approval_events_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.tool_requests(request_id);


--
-- Name: execution_events execution_events_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_events
    ADD CONSTRAINT execution_events_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.tool_requests(request_id);


--
-- Name: export_queue export_queue_destination_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.export_queue
    ADD CONSTRAINT export_queue_destination_id_fkey FOREIGN KEY (destination_id) REFERENCES public.export_destinations(destination_id);


--
-- Name: identity_role_mappings identity_role_mappings_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.identity_role_mappings
    ADD CONSTRAINT identity_role_mappings_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.identity_providers(provider_id);


--
-- Name: policy_change_events policy_change_events_policy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policy_change_events
    ADD CONSTRAINT policy_change_events_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.policy_versions(policy_id);


--
-- Name: policy_test_cases policy_test_cases_policy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policy_test_cases
    ADD CONSTRAINT policy_test_cases_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.policy_versions(policy_id);


--
-- Name: policy_versions policy_versions_supersedes_policy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policy_versions
    ADD CONSTRAINT policy_versions_supersedes_policy_id_fkey FOREIGN KEY (supersedes_policy_id) REFERENCES public.policy_versions(policy_id);


--
-- Name: secret_events secret_events_secret_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secret_events
    ADD CONSTRAINT secret_events_secret_id_fkey FOREIGN KEY (secret_id) REFERENCES public.secret_references(secret_id);


--
-- Name: service_account_keys service_account_keys_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_account_keys
    ADD CONSTRAINT service_account_keys_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.service_accounts(account_id);


--
-- PostgreSQL database dump complete
--

\unrestrict Oin9bhwUwE1Vj22M9ozkOf0qB4uvxGqm968bEwRvbIM6uEBzps2AlUfYiEFQTys

