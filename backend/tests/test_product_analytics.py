"""P5 product analytics: counts only, fixed paths only, and switchable off per org or install."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.app import api, main, product_analytics
from backend.tests.test_org_lifecycle import install, populate, tenant  # noqa: F401 - fixture reuse


@pytest.fixture()
def org(install):
    org = tenant(install, "Adopter")
    populate(org, "adopter")
    return {**org, "client": TestClient(api.app), "headers": {"X-Admin-Pin": org["owner"]}}


def test_page_views_count_fixed_paths_only(org):
    client, headers = org["client"], org["headers"]
    for path in ("/agents", "/agents", "/live"):
        assert client.post("/analytics/page-view", headers=headers, json={"path": path}).status_code == 204
    for bad in ("/agents/adopter_agent_with_Secret", "/requests/3f2a?token=abc", "https://example.com/x", "/a b"):
        client.post("/analytics/page-view", headers=headers, json={"path": bad})
    pages = client.get(f"/organizations/{org['org_id']}/adoption", headers=headers).json()["page_views"]
    assert pages == [{"path": "/agents", "views": 2}, {"path": "/live", "views": 1}]


def test_adoption_is_counts_only_and_never_contents(org):
    main.submit_tool_request("adopter_agent", "read_file", "password=zqSecretValue in notes.txt")
    body = org["client"].get(f"/organizations/{org['org_id']}/adoption", headers=org["headers"])
    data = body.json()["metrics"]
    assert data["agents"] == 1 and data["active_agents"] == 1 and data["controlled_requests"] >= 2
    assert data["integrations"] == 2 and data["members"] == 1 and data["compliance_reports"] == 1
    text = body.text
    for content in ("zqSecretValue", "notes.txt", "a.txt", "adopter_agent", "SECOPS_EMAIL", "siem.example.com"):
        assert content not in text


def test_an_owner_can_turn_analytics_off_which_deletes_collected_counts(org):
    client, headers = org["client"], org["headers"]
    client.post("/analytics/page-view", headers=headers, json={"path": "/agents"})
    assert client.put(f"/organizations/{org['org_id']}/analytics", headers=headers, json={"enabled": False}).json()["enabled"] is False
    client.post("/analytics/page-view", headers=headers, json={"path": "/agents"})
    adoption = client.get(f"/organizations/{org['org_id']}/adoption", headers=headers).json()
    assert adoption["page_views"] == [] and adoption["analytics_enabled"] is False


def test_the_install_switch_turns_collection_off_everywhere(org, monkeypatch):
    monkeypatch.setenv("GREYGUARD_PRODUCT_ANALYTICS", "off")
    org["client"].post("/analytics/page-view", headers=org["headers"], json={"path": "/agents"})
    adoption = org["client"].get(f"/organizations/{org['org_id']}/adoption", headers=org["headers"]).json()
    assert adoption["page_views"] == [] and adoption["install_enabled"] is False


def test_adoption_is_for_owners_and_operators_only_and_page_paths_are_capped(org, install, monkeypatch):
    other = tenant(install, "Elsewhere")
    assert org["client"].get(f"/organizations/{org['org_id']}/adoption", headers={"X-Admin-Pin": other["owner"]}).status_code == 403
    assert org["client"].get(f"/organizations/{org['org_id']}/adoption", headers={"X-Admin-Pin": install["operator"]}).status_code == 200
    monkeypatch.setattr(product_analytics, "MAX_PATHS_PER_DAY", 2)
    recorded = [product_analytics.record_page_view(org["org_id"], f"/page-{n}") for n in range("abc".__len__())]
    assert recorded == [True, True, False]
