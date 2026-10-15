"""P3 gateway nodes: enrollment, Ed25519-signed policy distribution, bounded offline use and
revocation - through the real routes, verified with the SDK's gateway module."""
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from fastapi.testclient import TestClient

from backend.app import api, entitlements, gateways, main
from backend.tests.test_org_lifecycle import install, tenant  # noqa: F401 - fixture reuse
from sdk.python.greyguard_sdk.gateway import BundleError, decide, verify_bundle


@pytest.fixture()
def fleet(install, monkeypatch):
    key = Ed25519PrivateKey.generate().private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    monkeypatch.setenv("GREYGUARD_DISTRIBUTION_SIGNING_KEY", gateways._b64(key))
    org = tenant(install, "Fleet")
    client = TestClient(api.app)
    admin = {"X-Admin-Pin": org["owner"]}
    return {**org, "client": client, "admin": admin}


def enroll(fleet, name="edge-1", offline=3600):
    created = fleet["client"].post("/gateways", headers=fleet["admin"], json={"name": name, "max_offline_seconds": offline})
    assert created.status_code == 201, created.text
    enrolled = fleet["client"].post("/gateways/enroll", json={"token": created.json()["enrollment_token"], "node_version": "1.0"})
    assert enrolled.status_code == 200, enrolled.text
    body = enrolled.json()
    return {"node_id": body["node_id"], "headers": {"X-Gateway-Node": body["node_id"], "X-Gateway-Key": body["node_credential"]},
            "public_key": body["verification_key"]["public_key"], "token": created.json()["enrollment_token"]}


def bundle(fleet, node):
    response = fleet["client"].get("/gateways/bundle", headers=node["headers"])
    assert response.status_code == 200, response.text
    return response.json()


def test_a_node_enrolls_once_and_enforces_a_verified_bundle(fleet):
    node = enroll(fleet)
    # The enrollment token is single-use.
    assert fleet["client"].post("/gateways/enroll", json={"token": node["token"]}).status_code == 401
    assert fleet["client"].get("/gateways/distribution-key").json()["public_key"] == node["public_key"]
    signed = bundle(fleet, node)
    document = verify_bundle(signed, node["public_key"], expected_node_id=node["node_id"])
    assert document["org_id"] == fleet["org_id"] and document["policy"]["permissions"]
    assert decide(document, "any_agent", "read_file") == "ALLOW"
    assert decide(document, "any_agent", "not_a_tool") == "BLOCK"
    # A tampered bundle, another node's bundle and a replayed older bundle are refused.
    tampered = {**signed, "document": {**signed["document"], "emergency": {**signed["document"]["emergency"], "global_deny": False},
                                       "revoked_agents": []}}
    tampered["document"]["policy"] = {**signed["document"]["policy"], "permissions": {"delete_everything": "ALLOW"}}
    for bad, kwargs in ((tampered, {}), (signed, {"expected_node_id": "gw_other"}),
                        (signed, {"last_issued_at": signed["document"]["issued_at"]})):
        with pytest.raises(BundleError):
            verify_bundle(bad, node["public_key"], **kwargs)


def test_bundles_expire_after_the_offline_allowance_and_then_deny_everything(fleet):
    node = enroll(fleet, offline=300)
    document = verify_bundle(bundle(fleet, node), node["public_key"])
    later = datetime.now(timezone.utc) + timedelta(seconds=301)
    assert decide(document, "agent", "read_file", now=later) == "BLOCK"
    with pytest.raises(BundleError, match="expired"):
        verify_bundle(bundle(fleet, node), node["public_key"], now=later)
    assert decide(None, "agent", "read_file") == "BLOCK"


def test_revocations_and_emergency_stops_reach_the_next_bundle(fleet):
    node = enroll(fleet)
    api.register_agent_identity(api.AgentRegistration(agent_name="edge_agent", scopes=["read_file"]), fleet["owner"])
    first = verify_bundle(bundle(fleet, node), node["public_key"])
    assert decide(first, "edge_agent", "read_file") == "ALLOW"
    fleet["client"].post("/agents/edge_agent/credential/revoke", headers=fleet["admin"])
    second = verify_bundle(bundle(fleet, node), node["public_key"], last_issued_at=first["issued_at"])
    assert "edge_agent" in second["revoked_agents"] and decide(second, "edge_agent", "read_file") == "BLOCK"
    fleet["client"].put("/policy-emergency-controls", headers=fleet["admin"], json={"global_deny": True})
    third = verify_bundle(bundle(fleet, node), node["public_key"])
    assert decide(third, "someone_else", "read_file") == "BLOCK"
    assert len({first["content_digest"], second["content_digest"], third["content_digest"]}) == 3


def test_fleet_view_tracks_sync_and_a_revoked_node_is_cut_off(fleet):
    node = enroll(fleet)
    nodes = lambda: {n["node_id"]: n for n in fleet["client"].get("/gateways", headers=fleet["admin"]).json()["nodes"]}
    assert nodes()[node["node_id"]]["health"] == "SILENT"
    document = verify_bundle(bundle(fleet, node), node["public_key"])
    beat = fleet["client"].post("/gateways/heartbeat", headers=node["headers"], json={"applied_digest": document["content_digest"]})
    assert beat.json()["refresh_required"] is False and nodes()[node["node_id"]]["health"] == "IN_SYNC"
    fleet["client"].put("/policy-emergency-controls", headers=fleet["admin"], json={"global_deny": True})
    assert nodes()[node["node_id"]]["health"] == "OUT_OF_DATE"
    revoked = fleet["client"].post(f"/gateways/{node['node_id']}/revoke", headers=fleet["admin"], json={"reason": "Host decommissioned"})
    assert revoked.json()["status"] == "REVOKED"
    assert fleet["client"].get("/gateways/bundle", headers=node["headers"]).status_code == 401
    assert fleet["client"].post("/gateways/heartbeat", headers=node["headers"], json={}).status_code == 401


def test_nodes_belong_to_one_org(fleet, install):
    node = enroll(fleet)
    other = tenant(install, "Other Fleet")
    other_admin = {"X-Admin-Pin": other["owner"]}
    assert fleet["client"].get("/gateways", headers=other_admin).json()["nodes"] == []
    assert fleet["client"].post(f"/gateways/{node['node_id']}/revoke", headers=other_admin, json={"reason": "Not yours"}).status_code == 404
    assert verify_bundle(bundle(fleet, node), node["public_key"])["org_id"] == fleet["org_id"]
    assert fleet["client"].get("/gateways/bundle", headers={**node["headers"], "X-Gateway-Key": "ggnode_wrong"}).status_code == 401


def test_gateways_are_an_enterprise_feature_and_offboarding_revokes_them(fleet):
    node = enroll(fleet)
    entitlements.assign_plan(fleet["org_id"], "FOUNDATION", "ACTIVE", "test")
    refused = fleet["client"].post("/gateways", headers=fleet["admin"], json={"name": "edge-2"})
    assert refused.status_code == 403 and refused.json()["reason"] == "ENTITLEMENT"
    entitlements.assign_plan(fleet["org_id"], "ENTERPRISE", "ACTIVE", "test")
    state = fleet["client"].post(f"/organizations/{fleet['org_id']}/offboarding", headers=fleet["admin"],
                                 json={"reason": "Contract ended for fleet", "retention_days": 30}).json()
    assert state["offboarding"]["actions"]["gateway_nodes_revoked"] == 1
    assert fleet["client"].get("/gateways/bundle", headers=node["headers"]).status_code == 401


def test_no_signing_key_is_a_clear_503(fleet, monkeypatch):
    monkeypatch.delenv("GREYGUARD_DISTRIBUTION_SIGNING_KEY")
    assert fleet["client"].get("/gateways/distribution-key").status_code == 503
