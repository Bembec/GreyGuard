"""The deferred-decision registry: open decisions never break development, always block production,
and nothing pending can be mistaken for approved."""
import copy
import json

import pytest

from scripts import decisions

FULL_ENV = {
    "GREYGUARD_SITE_URL": "https://greyguard.example",
    "GREYGUARD_BOOTSTRAP_EMAIL": "x", "GREYGUARD_BOOTSTRAP_PASSWORD": "x", "GREYGUARD_ALLOWED_ORIGINS": "x",
    "GREYGUARD_TRUSTED_HOSTS": "x", "GREYGUARD_DATABASE_URL": "x",
}


@pytest.fixture()
def registry():
    return decisions.load(decisions.REGISTRY)


def decide_everything(registry):
    """A copy of the registry with every decision made, as a launch-ready owner would leave it."""
    values = {"string": "Decided", "text": "Decided", "status": "Cleared", "approval": "Counsel approval 2027-01-01",
              "list": ["Decided"], "boolean": True, "email": "security@greyguard.example",
              "https_url": "https://greyguard.example", "url_or_mailto": "mailto:sales@greyguard.example", "assets": "final"}
    ready = copy.deepcopy(registry)
    for item in ready["decisions"]:
        if item["value_type"] in decisions.COMPUTED or item["status"] == "decided":
            continue
        item.update(status="decided", value=values[item["value_type"]], decided_on="2027-01-01", evidence="Owner decision record")
    return ready


def test_the_registry_in_the_repository_is_valid(registry):
    assert decisions.check_registry(registry) == []


def test_the_founder_register_is_generated_from_the_registry(registry):
    rendered = decisions.render_founder_doc(registry)
    assert decisions.FOUNDER_DOC.read_text(encoding="utf-8") == rendered, "run: python scripts/decisions.py render"


def test_the_known_open_decisions_are_all_recorded(registry):
    ids = {item["id"] for item in registry["decisions"]}
    # The fifteen decisions the owner listed on 2026-10-15, by the id each was given.
    for decision_id in ("BRAND-01", "BRAND-02", "BRAND-03", "LEG-07", "OPS-04", "OPS-05", "CO-01", "COM-07", "LEG-01", "LEG-02",
                        "COM-03", "COM-04", "COM-02", "COM-05", "OPS-02", "OPS-03", "OPS-08", "CO-02", "CO-08", "LEG-08", "LEG-09"):
        assert decision_id in ids


@pytest.mark.parametrize("target", ["development", "preview"])
def test_open_decisions_never_stop_development_or_preview(registry, target):
    rows = decisions.readiness(registry, environ={})
    assert any(not row["met"] for row in rows)
    assert decisions.gate(rows, target) == []
    assert decisions.main(["readiness", "--target", target]) == 0


def test_production_is_blocked_and_names_each_missing_item(registry):
    stopping = decisions.gate(decisions.readiness(registry, environ={}), "production")
    ids = {row["id"] for row in stopping}
    assert {"CO-01", "COM-07", "LEG-01", "LEG-02", "LEG-07", "LEG-10", "OPS-04", "OPS-05", "OPS-09"} <= ids
    for row in stopping:
        assert row["remediation"].strip(), f"{row['id']} gives no remediation"
    secrets_row = next(row for row in stopping if row["id"] == "OPS-09")
    assert "GREYGUARD_DATABASE_URL" in secrets_row["detail"]


def test_production_passes_once_every_blocking_decision_is_made(registry, monkeypatch):
    monkeypatch.setattr(decisions, "_claims_state", lambda: (True, "every claim is approved or withdrawn"))
    ready = decide_everything(registry)
    ready["decisions"][[item["id"] for item in ready["decisions"]].index("CO-01")]["value"] = "https://greyguard.example"
    rows = decisions.readiness(ready, environ=FULL_ENV)
    assert decisions.gate(rows, "production") == []
    assert decisions.gate(rows, "public-launch") == []


def test_the_site_url_must_match_the_decided_domain(registry, monkeypatch):
    monkeypatch.setattr(decisions, "_claims_state", lambda: (True, ""))
    ready = decide_everything(registry)
    rows = decisions.readiness(ready, environ={**FULL_ENV, "GREYGUARD_SITE_URL": "https://other.example"})
    assert [row["id"] for row in decisions.gate(rows, "production")] == ["CO-01"]


def test_unapproved_claims_block_production(registry, monkeypatch):
    ready = decide_everything(registry)
    rows = decisions.readiness(ready, environ=FULL_ENV)
    assert "LEG-07" in {row["id"] for row in decisions.gate(rows, "production")}


def test_a_frozen_brand_makes_final_logo_assets_blocking(registry):
    frozen = copy.deepcopy(registry)
    freeze = next(item for item in frozen["decisions"] if item["id"] == "BRAND-06")
    freeze.update(status="decided", value=True, decided_on="2027-01-01", evidence="Brand freeze")
    stopping = {row["id"] for row in decisions.gate(decisions.readiness(frozen, environ={}), "production")}
    assert {"BRAND-01", "BRAND-02"} <= stopping
    assert not {"BRAND-01", "BRAND-02"} & {row["id"] for row in decisions.gate(decisions.readiness(registry, environ={}), "production")}


def test_a_pending_decision_cannot_carry_a_value(registry):
    # A value on an undecided item could be shown as if it were approved.
    broken = copy.deepcopy(registry)
    legal = next(item for item in broken["decisions"] if item["id"] == "LEG-01")
    legal["value"] = "Approved"
    assert any("must not carry a value" in problem for problem in decisions.check_registry(broken))


def test_a_decision_needs_its_date_and_evidence(registry):
    broken = copy.deepcopy(registry)
    item = next(item for item in broken["decisions"] if item["id"] == "CO-02")
    item.update(status="decided", value="support@greyguard.example")
    assert any("decided_on and evidence" in problem for problem in decisions.check_registry(broken))


@pytest.mark.parametrize("value_type,bad", [("email", "not-an-email"), ("https_url", "http://insecure.example"),
                                             ("https_url", "https://user:pass@greyguard.example"), ("url_or_mailto", "javascript:alert(1)")])
def test_values_are_type_checked(registry, value_type, bad):
    broken = copy.deepcopy(registry)
    item = next(item for item in broken["decisions"] if item["value_type"] == value_type)
    item.update(status="decided", value=bad, decided_on="2027-01-01", evidence="x")
    assert any("not a valid" in problem for problem in decisions.check_registry(broken))


def test_no_secret_can_be_recorded(registry):
    keyed = copy.deepcopy(registry)
    keyed["decisions"][0]["api_token"] = "x"
    assert any("looks like a secret" in problem for problem in decisions.check_registry(keyed))
    valued = copy.deepcopy(registry)
    valued["decisions"][0]["temporary_behaviour"] = "use postgresql://admin:hunter2@db/greyguard"
    assert any("embedded credential" in problem for problem in decisions.check_registry(valued))


def test_computed_decisions_cannot_be_marked_decided_by_hand(registry):
    broken = copy.deepcopy(registry)
    claims = next(item for item in broken["decisions"] if item["id"] == "LEG-07")
    claims.update(status="decided", decided_on="2027-01-01", evidence="x")
    assert any("computed" in problem for problem in decisions.check_registry(broken))


def test_the_report_is_machine_readable(capsys):
    assert decisions.main(["readiness", "--target", "production", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ready"] is False and "LEG-01" in report["stopping"]
    assert {"id", "tier", "met", "remediation", "temporary_behaviour"} <= set(report["items"][0])
