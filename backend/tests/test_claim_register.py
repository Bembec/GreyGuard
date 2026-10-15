"""P7.0: the public-site claim register, and the rules that keep it honest."""
import copy
import json
from datetime import date

import pytest

from scripts import check_claims

TODAY = date(2026, 10, 15)


@pytest.fixture()
def register():
    return json.loads(check_claims.REGISTER.read_text(encoding="utf-8"))


def good_claim(**changes):
    claim = {
        "id": "GG-GATE-99", "group": "gate", "kind": "capability", "availability": "verified",
        "claim": "An action with no rule is blocked.", "scope": "Every request.",
        "evidence": ["backend/tests/test_security_foundation.py::test_unknown_action_defaults_to_block"],
        "owner": "Engineering", "status": "proposed", "approved_by": None, "approved_on": None,
        "review_by": "2027-01-15", "pages": [],
    }
    claim.update(changes)
    return claim


def problems_for(claim):
    return check_claims.check_claim(claim, TODAY)


def test_the_register_in_the_repository_is_valid(register):
    assert check_claims.check_register(register, TODAY) == []


def test_nothing_is_published_until_the_owner_approves_it(register):
    # Every claim starts proposed; approval is the project owner's decision, never engineering's.
    assert check_claims.publishable(register) == []
    approved = copy.deepcopy(register)
    approved["claims"][0].update(status="approved", approved_by="Project owner", approved_on="2026-10-15")
    assert [claim["id"] for claim in check_claims.publishable(approved)] == [register["claims"][0]["id"]]


def test_a_well_formed_claim_passes():
    assert problems_for(good_claim()) == []


def test_a_missing_file_or_test_is_reported():
    assert "missing file" in problems_for(good_claim(evidence=["docs/no-such-file.md"]))[0]
    missing_test = good_claim(evidence=["backend/tests/test_security_foundation.py::test_no_such_test"])
    assert any("missing test" in item for item in problems_for(missing_test))


def test_a_verified_capability_needs_a_test_not_just_prose():
    claim = good_claim(evidence=["docs/agent-integration.md"])
    assert any("cites no test" in item for item in problems_for(claim))
    # A limitation can rest on documentation alone.
    assert problems_for(good_claim(kind="limitation", evidence=["docs/agent-integration.md"])) == []


@pytest.mark.parametrize("text", [
    "GreyGuard is an official LangChain partner.",
    "GreyGuard is SOC 2 certified.",
    "Guaranteed to stop every attack.",
    "Blocks 100% of prompt injection.",
])
def test_claims_implying_partnerships_certifications_or_guarantees_are_rejected(text):
    assert any("implies something" in item for item in problems_for(good_claim(claim=text)))


def test_a_limitation_may_say_what_greyguard_does_not_hold():
    claim = good_claim(kind="limitation", claim="GreyGuard holds no security certification.", evidence=["docs/trust/certifications.md"])
    assert problems_for(claim) == []


def test_an_approval_must_name_who_and_when_and_expires_at_its_review_date():
    assert any("who approved" in item for item in problems_for(good_claim(status="approved")))
    stale = good_claim(status="approved", approved_by="Project owner", approved_on="2026-01-01", review_by="2026-06-01")
    assert any("review date" in item for item in problems_for(stale))
    assert any("not approved" in item for item in problems_for(good_claim(approved_by="Someone")))


def test_unknown_labels_and_duplicate_ids_are_rejected(register):
    assert any("unknown availability" in item for item in problems_for(good_claim(availability="beta")))
    duplicated = copy.deepcopy(register)
    duplicated["claims"].append(copy.deepcopy(duplicated["claims"][0]))
    assert any("listed twice" in item for item in check_claims.check_register(duplicated, TODAY))


def test_planned_work_is_labelled_planned(register):
    planned = [claim for claim in register["claims"] if claim["availability"] == "planned"]
    assert planned, "the register should carry what is planned, so the site can show it honestly"
    for claim in planned:
        assert claim["evidence"] == [] or all(not check_claims.is_test_reference(r) for r in claim["evidence"])
