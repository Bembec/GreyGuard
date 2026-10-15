"""P2.6 acceptance suite: cross-tenant isolation across the whole API, and safety under every
billing, licence and lifecycle failure.

Unlike the per-batch tenancy tests, this suite does not know which routes exist. It reads the
application's own route table and OpenAPI schema, so a route added later is swept automatically:

- Read sweep: an administrator of org B calls every GET route, with org A's real identifiers
  substituted into every path parameter. No response may carry any of org A's identifiers.
- Write sweep: the same administrator calls every POST/PUT/DELETE route, with request bodies
  generated from the OpenAPI schema and org A's identifiers in the path. Afterwards every row
  org A owns must be exactly as it was.
- Failure matrix: for every reason an org can be restricted, each mandatory protection still
  works over HTTP and new growth is refused.
"""
import hashlib
import itertools
import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.app import api, billing, entitlements, licensing, main, org_lifecycle, organizations
from backend.tests.test_org_lifecycle import install, populate, tenant  # noqa: F401 - fixture reuse

PROBE = "zqprobe"
# Routes the sweeps never call, each with the reason. Keep this list short and justified.
SKIPPED_ROUTES = {
    ("POST", "/billing/webhooks/{provider_name}"): "authenticates by provider signature, not by session; covered in test_billing_and_licensing",
    ("POST", "/auth/logout"): "would end the probing session mid-sweep",
    ("POST", "/auth/refresh"): "would rotate the probing session mid-sweep",
    ("GET", "/live-events"): "a never-ending event stream; it reads get_administrator_audit_events(org_id=...), the same query GET /audit-events serves in this sweep",
}


@pytest.fixture()
def tenants(install, monkeypatch):
    # The sweeps send thousands of requests from one test client; the rate limiter is not under test.
    monkeypatch.setattr(api, "check_rate_limit", lambda *_args, **_kwargs: {"allowed": True, "remaining": 1000, "retry_after": 0})
    # Signed policy bundles and report manifests need their keys, or those routes stop at a 503.
    monkeypatch.setenv("GREYGUARD_POLICY_SIGNING_KEY", "acceptance-suite-policy-signing-key-0123456789")
    monkeypatch.setenv("GREYGUARD_REPORT_SIGNING_KEY", "acceptance-suite-report-signing-key-0123456789")
    monkeypatch.setenv("GREYGUARD_DISTRIBUTION_SIGNING_KEY", "Qf3LkkbgYw3-hUQOP8WqvL4uRvcrB8tBbvHmLk3P2Ao")
    victim, attacker = tenant(install, "Victim"), tenant(install, "Attacker")
    populate(victim, "zqvictim")
    # The default org is a second victim: a route that forgets its org_id falls back to it.
    entitlements.assign_plan(organizations.DEFAULT_ORG_ID, "ENTERPRISE", "ACTIVE", "test")
    populate({"org_id": organizations.DEFAULT_ORG_ID, "owner": install["operator"]}, "zqdefault")
    issued = populate(attacker, "attacker")
    # Some catalogs (adapters, the threat register) are seeded into an org on first use. Visit
    # every parameter-free page as the attacker first, so a value every org shares is never
    # mistaken for the victims' own.
    client = TestClient(api.app)
    for _method, route in routes({"GET"}):
        if not route.param_convertors:
            client.get(route.path, headers={"X-Admin-Pin": attacker["owner"]})
    # The attacker probes with its administrator session and its own agent's credential, so
    # agent-authenticated routes reach their handlers too.
    attacker["headers"] = {"X-Admin-Pin": attacker["owner"], "X-Agent-Name": "attacker_agent",
                           "X-Agent-Key": issued["credential"]}
    return {"victim": victim, "attacker": attacker, **install}


def owned_rows(org_id):
    """Every row the org owns, in every org-scoped table, plus its org and membership rows."""
    with org_lifecycle.sqlite3.connect(org_lifecycle.database_path) as connection:
        connection.row_factory = org_lifecycle.sqlite3.Row
        rows = {table: sorted(json.dumps(dict(row), sort_keys=True, default=str) for row in connection.execute(
            f"SELECT * FROM {table} WHERE org_id = ?", (org_id,)).fetchall())
            for table in org_lifecycle._scoped_tables(connection)}
        rows["organizations"] = [json.dumps(dict(connection.execute(
            "SELECT * FROM organizations WHERE org_id = ?", (org_id,)).fetchone()), sort_keys=True)]
        rows["org_memberships"] = sorted(json.dumps(dict(row), sort_keys=True) for row in connection.execute(
            "SELECT * FROM org_memberships WHERE org_id = ?", (org_id,)).fetchall())
    return rows


def column_values(org_id):
    """column name -> every string value of that column in the org's own rows."""
    values = {}
    for table, rows in owned_rows(org_id).items():
        for row in rows:
            for column, value in json.loads(row).items():
                if isinstance(value, str) and value:
                    values.setdefault(column, set()).add(value)
    return values


def markers(victims, others):
    """The victims' identifiers that belong to nobody else: ids and names at least 8 characters long."""
    theirs = set().union(*(set().union(*column_values(org).values()) for org in others))
    ours = {}
    for victim in victims:
        for column, vals in column_values(victim).items():
            ours.setdefault(column, set()).update(vals)
    identifying = {column: {v for v in vals if len(v) >= 8 and v not in theirs and not v.startswith("20")}
                   for column, vals in ours.items()
                   if column.endswith("_id") or column in ("agent_name", "name", "title", "path", "subscription_ref")}
    found = set().union(*identifying.values()) | set(victims) - {organizations.DEFAULT_ORG_ID}
    return found, {column: vals for column, vals in identifying.items() if vals}


def routes(methods):
    for route in api.app.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods & methods):
                if (method, route.path) not in SKIPPED_ROUTES:
                    yield method, route


def substitutions(route, values, victim, own_values, own_org):
    """Paths for a route. Each path parameter is filled with org A's values for that name, and
    also with the prober's own, because a leak can surface inside the prober's own records (a
    report that embeds another org's people, say). A probe value stands in when neither has one."""
    names = list(route.param_convertors)
    choices = []
    for name in names:
        theirs = [victim] if name == "org_id" else sorted(values.get(name, set()))[:3]
        ours = [own_org] if name == "org_id" else sorted(own_values.get(name, set()))[:1]
        choices.append([(c, True) for c in theirs] + [(c, False) for c in ours] or [(PROBE + "-" + name, False)])
    for combo in itertools.islice(itertools.product(*choices), 8):
        path = route.path
        for name, (value, _) in zip(names, combo):
            path = path.replace("{" + name + "}", value)
        yield path, {value for value, is_victims in combo if is_victims}


# --- Request bodies from the OpenAPI schema ------------------------------------------------------

def _resolve(schema, spec):
    while "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].rsplit("/", 1)[1]]
    return schema


def sample(schema, spec, depth=0):
    schema = _resolve(schema, spec)
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema:
            options = [_resolve(option, spec) for option in schema[key]]
            options = [option for option in options if option.get("type") != "null"] or options
            return sample(options[0], spec, depth)
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    if "default" in schema and schema["default"] is not None:
        return schema["default"]
    kind = schema.get("type")
    if kind == "string":
        pattern = schema.get("pattern", "")
        if pattern:
            if r"\d{4}-\d{2}-\d{2}" in pattern:
                return "2026-01-01"
            digits = re.fullmatch(r"\^\\d\{(\d+)\}\$", pattern)
            if digits:
                return "0" * int(digits.group(1))
        if schema.get("format") == "email" or "email" in schema.get("title", "").lower():
            return "probe@zqprobe.example"
        if "date" in schema.get("format", "") or "_at" in schema.get("title", "").lower():
            return "2099-01-01T00:00:00+00:00"
        length = max(schema.get("minLength", 0), 12)
        return (PROBE + "-value-" + "x" * length)[: schema.get("maxLength", length + 20)]
    if kind == "integer":
        return max(schema.get("minimum", 1), min(1, schema.get("maximum", 1)))
    if kind == "number":
        return schema.get("minimum", 1)
    if kind == "boolean":
        return True
    if kind == "array":
        return [sample(schema.get("items", {}), spec, depth + 1) for _ in range(max(1, schema.get("minItems", 1)))] if depth < 4 else []
    if kind == "object" or "properties" in schema:
        if depth >= 4:
            return {}
        return {name: sample(prop, spec, depth + 1) for name, prop in schema.get("properties", {}).items()}
    return PROBE


def body_for(method, route, spec):
    operation = spec["paths"].get(route.path, {}).get(method.lower(), {})
    content = operation.get("requestBody", {}).get("content", {})
    if "application/json" in content:
        return sample(content["application/json"]["schema"], spec)
    return None


# --- The sweeps ------------------------------------------------------------------------------------

def test_no_route_returns_another_orgs_data(tenants):
    victim, attacker = tenants["victim"]["org_id"], tenants["attacker"]
    secret_markers, values = markers([victim, organizations.DEFAULT_ORG_ID], [attacker["org_id"]])
    assert len(secret_markers) >= 15, "the victim org was not populated enough for the sweep to mean anything"
    own_values = column_values(attacker["org_id"])
    client = TestClient(api.app)
    headers = attacker["headers"]
    leaks, calls = [], 0
    for method, route in routes({"GET"}):
        for path, substituted in substitutions(route, values, victim, own_values, attacker["org_id"]):
            response = client.get(path, headers=headers)
            calls += 1
            assert response.status_code < 500, f"GET {path} -> {response.status_code}: {response.text[:300]}"
            body = response.text
            # A marker inside a value the request itself supplied is an echo, not a leak.
            leaked = sorted(m for m in secret_markers - substituted
                            if m in body and not any(m in value for value in substituted))
            if leaked:
                leaks.append(f"GET {path} -> {response.status_code} leaks {leaked[:3]}")
            elif substituted and response.status_code < 300 and any(v in body for v in substituted):
                leaks.append(f"GET {path} -> {response.status_code} returns the victim's {sorted(substituted)}")
    assert calls > 100
    assert leaks == [], "\n".join(leaks)


def test_no_route_changes_another_orgs_data(tenants):
    victim, attacker = tenants["victim"]["org_id"], tenants["attacker"]
    _, values = markers([victim, organizations.DEFAULT_ORG_ID], [attacker["org_id"]])
    own_values = column_values(attacker["org_id"])
    before = {org: owned_rows(org) for org in (victim, organizations.DEFAULT_ORG_ID)}
    spec = api.app.openapi()
    client = TestClient(api.app)
    headers = attacker["headers"]
    calls, accepted, unvalidated = 0, 0, 0
    # Destructive org-level routes last, so the rest of the sweep still runs with a live session.
    ordered = sorted(routes({"POST", "PUT", "DELETE", "PATCH"}), key=lambda item: "offboarding" in item[1].path)
    for method, route in ordered:
        for path, _ in substitutions(route, values, victim, own_values, attacker["org_id"]):
            response = client.request(method, path, headers=headers, json=body_for(method, route, spec))
            calls += 1
            accepted += response.status_code < 300
            unvalidated += response.status_code == 422  # rejected before the handler ran
            assert response.status_code < 500, f"{method} {path} -> {response.status_code}: {response.text[:300]}"
    for org, rows in before.items():
        after = owned_rows(org)
        changed = {table: (len(rows[table]), len(after.get(table, []))) for table in rows if rows[table] != after.get(table)}
        assert changed == {}, f"The attacker org changed {org}'s data: {changed}"
    # The sweep really exercised the handlers, not just request validation.
    assert calls - unvalidated > 150 and accepted > 30, (calls, unvalidated, accepted)


# --- Failure safety matrix -----------------------------------------------------------------------

def _restrict(org, reason, monkeypatch):
    org_id = org["org_id"]
    if reason in ("PLAN_EXPIRED", "PLAN_SUSPENDED"):
        entitlements.assign_plan(org_id, "ENTERPRISE", "TRIAL" if reason == "PLAN_EXPIRED" else "SUSPENDED", "test",
                                 14 if reason == "PLAN_EXPIRED" else None)
        if reason == "PLAN_EXPIRED":
            with entitlements.sqlite3.connect(entitlements.database_path) as connection:
                connection.execute("UPDATE org_entitlements SET trial_ends_at = ? WHERE org_id = ?",
                                   ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), org_id))
    elif reason in ("PAYMENT_OVERDUE", "SUBSCRIPTION_CANCELED"):
        billing.link_account(org_id, "ENTERPRISE", "ap@example.com", "test")
        if reason == "SUBSCRIPTION_CANCELED":
            billing.cancel_account(org_id, "test")
        else:
            billing.simulate_event(org_id, "PAYMENT_FAILED")
            with billing.sqlite3.connect(billing.database_path) as connection:
                connection.execute("UPDATE billing_accounts SET grace_ends_at = ? WHERE org_id = ?",
                                   ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), org_id))
    elif reason in ("LICENSE_LAPSED", "LICENSE_MISSING"):
        key = Ed25519PrivateKey.generate()
        monkeypatch.setenv("GREYGUARD_LICENSE_PUBLIC_KEY", licensing._b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)))
        monkeypatch.setenv("GREYGUARD_LICENSE_REQUIRED", "true")
        if reason == "LICENSE_LAPSED":
            from cryptography.hazmat.primitives.serialization import NoEncryption, PrivateFormat
            private = licensing._b64encode(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))
            now = datetime.now(timezone.utc)
            licensing.install_lease(licensing.issue_lease(private, licensee="T", install=licensing.install_id(), plan="ENTERPRISE",
                                                          days=30, grace_days=1, issued_at=now - timedelta(days=30, hours=1)), "test")
            with licensing.sqlite3.connect(licensing.database_path) as connection:
                connection.execute("UPDATE license_install SET clock_high_water = ?", ((now + timedelta(days=2)).isoformat(),))
    elif reason == "ORG_OFFBOARDING":
        org_lifecycle.start_offboarding(org_id, "test", "Contract ended - testing safety", 30)
    else:
        raise AssertionError(f"No way to cause {reason}")


# Every mandatory protection, and how the matrix proves it still works. A test below requires
# this to cover MANDATORY_PROTECTIONS exactly, so a new protection needs a new check.
PROTECTION_CHECKS = {
    "agent_identity": "an agent registered before the restriction still authenticates",
    "authorization": "an out-of-scope action by that agent is still blocked",
    "redaction": "a secret in an agent's request never appears in the evidence an administrator reads",
    "evidence": "the audit log stays readable",
    "emergency_stop": "the emergency global deny can still be switched on",
    "basic_recovery": "a suspended agent can still be reset",
    "evidence_export": "compliance reports can be generated and exported, and the whole org exported",
    "offboarding": "the org can still be offboarded",
}


def test_every_mandatory_protection_has_a_check():
    assert set(PROTECTION_CHECKS) == entitlements.MANDATORY_PROTECTIONS


@pytest.mark.parametrize("reason", sorted(set(entitlements.RESTRICTION_REASONS) - {"ORG_DELETED"}))
def test_every_restriction_keeps_every_protection(install, monkeypatch, reason):
    """ORG_DELETED is excluded: a deleted org has no members, agents or data left to protect."""
    monkeypatch.setenv("GREYGUARD_BILLING_PROVIDER", "mock")
    monkeypatch.setattr(api, "check_rate_limit", lambda *_args, **_kwargs: {"allowed": True, "remaining": 1000, "retry_after": 0})
    org = tenant(install, f"Safety {reason.title().replace('_', ' ')}")
    agent = f"safety_{reason.lower()}"
    issued = api.register_agent_identity(api.AgentRegistration(agent_name=agent, scopes=["read_file"]), org["owner"])
    if reason != "ORG_OFFBOARDING":
        _restrict(org, reason, monkeypatch)
        credential = issued["credential"]
    else:
        credential = None  # offboarding revokes credentials by design; covered below
        _restrict(org, reason, monkeypatch)
    client = TestClient(api.app)
    headers = {"X-Admin-Pin": org["owner"]}
    current = client.get("/entitlements", headers=headers).json()
    assert reason in current["restriction_reasons"]

    # New growth is refused.
    refused = client.post("/agents", headers=headers, json={"agent_name": f"{agent}_new", "scopes": ["read_file"]})
    assert refused.status_code == 403 and refused.json()["reason"] in ("ENTITLEMENT", "OFFBOARDING")

    # agent_identity, authorization, redaction: existing agents keep being enforced exactly as before.
    if credential:
        assert main.authenticate_agent(agent, credential, "read_file")["agent_name"] == agent
    assert main.submit_tool_request(agent, "delete_file", "x.txt")["policy_decision"] != "ALLOW"
    main.submit_tool_request(agent, "read_file", "notes password=zqHunter2Secret")
    # evidence
    evidence = client.get("/audit-events", headers=headers)
    assert evidence.status_code == 200 and agent in evidence.text
    assert "zqHunter2Secret" not in client.get("/tool-requests", headers=headers).text + evidence.text
    # emergency_stop
    stop = client.put("/policy-emergency-controls", headers=headers, json={"global_deny": True})
    assert stop.status_code == 200 and stop.json()["global_deny"] is True
    # basic_recovery
    recovered = client.post(f"/agents/{agent}/reset", headers=headers)
    assert recovered.status_code == 200, recovered.text
    # evidence_export
    report = client.post("/compliance-reports", headers=headers, json={"title": "Safety evidence"})
    assert report.status_code in (200, 201), report.text
    assert client.get(f"/compliance-reports/{report.json()['report_id']}/export?format=json", headers=headers).status_code == 200
    exported = client.post(f"/organizations/{org['org_id']}/export", headers=headers)
    assert exported.status_code == 200 and exported.json()["organization"]["org_id"] == org["org_id"]
    # offboarding
    if reason == "ORG_OFFBOARDING":
        assert client.get(f"/organizations/{org['org_id']}/lifecycle", headers=headers).json()["status"] == "OFFBOARDING"
    else:
        offboarded = client.post(f"/organizations/{org['org_id']}/offboarding", headers=headers,
                                 json={"reason": "Leaving while restricted", "retention_days": 30})
        assert offboarded.status_code == 200 and offboarded.json()["status"] == "OFFBOARDING", offboarded.text
