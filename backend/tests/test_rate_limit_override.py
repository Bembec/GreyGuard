"""The browser suite's test-only rate-limit override can never reach production.

Owner decision, 2026-10-16: production keeps GENERAL at 300 requests a minute. Only the explicit
end-to-end test environment (GREYGUARD_ENV=test plus an exact sentinel) may raise read limits.
"""
import pytest

from backend.app import abuse_protection, database
from backend.app.abuse_protection import (
    E2E_OVERRIDE_ACTOR, E2E_OVERRIDE_SENTINEL, E2E_OVERRIDE_VARIABLE, RateLimitOverrideError,
)
from backend.app.production_config import load_production_config

PRODUCTION = {
    "GREYGUARD_ENV": "production", "GREYGUARD_BOOTSTRAP_EMAIL": "owner@example.com",
    "GREYGUARD_BOOTSTRAP_PASSWORD": "a-long-production-password", "GREYGUARD_ALLOWED_ORIGINS": "https://console.example.com",
    "GREYGUARD_TRUSTED_HOSTS": "console.example.com",
}


@pytest.fixture()
def fresh_database(tmp_path, monkeypatch):
    monkeypatch.setattr(abuse_protection, "database_path", tmp_path / "limits.db")
    monkeypatch.setattr(database, "database_path", tmp_path / "limits.db")
    return tmp_path


def test_production_keeps_300_requests_a_minute():
    assert abuse_protection.DEFAULT_POLICIES["GENERAL"]["request_limit"] == 300
    assert abuse_protection.default_policies(PRODUCTION)["GENERAL"]["request_limit"] == 300
    assert abuse_protection.default_policies({})["GENERAL"]["request_limit"] == 300


def test_a_fresh_install_without_the_override_seeds_300(fresh_database, monkeypatch):
    # Production itself refuses SQLite, so the seeding runs without GREYGUARD_ENV=production here;
    # the production start-up check below takes the environment explicitly.
    monkeypatch.delenv("GREYGUARD_ENV", raising=False)
    monkeypatch.delenv(E2E_OVERRIDE_VARIABLE, raising=False)
    abuse_protection.initialize_abuse_protection()
    general = next(p for p in abuse_protection.list_policies() if p["category"] == "GENERAL")
    assert general["request_limit"] == 300 and general["updated_by"] == "system"
    abuse_protection.assert_no_test_override_in_production("production")


@pytest.mark.parametrize("environment", ["production", "development", "staging", ""])
def test_the_override_is_refused_outside_the_test_environment(environment):
    env = {**PRODUCTION, "GREYGUARD_ENV": environment, E2E_OVERRIDE_VARIABLE: E2E_OVERRIDE_SENTINEL}
    with pytest.raises(RateLimitOverrideError):
        abuse_protection.default_policies(env)
    if environment == "production":
        with pytest.raises(RateLimitOverrideError):
            load_production_config(env)


@pytest.mark.parametrize("value", ["1", "true", "yes", "", "E2E-TEST-ENVIRONMENT-ONLY"])
def test_only_the_exact_sentinel_enables_it(value):
    with pytest.raises(RateLimitOverrideError):
        abuse_protection.default_policies({"GREYGUARD_ENV": "test", E2E_OVERRIDE_VARIABLE: value})


def test_the_test_environment_without_the_variable_keeps_production_limits():
    assert abuse_protection.default_policies({"GREYGUARD_ENV": "test"}) == abuse_protection.DEFAULT_POLICIES


def test_the_override_raises_only_read_limits_never_sign_in(fresh_database, monkeypatch):
    env = {"GREYGUARD_ENV": "test", E2E_OVERRIDE_VARIABLE: E2E_OVERRIDE_SENTINEL}
    policies = abuse_protection.default_policies(env)
    assert policies["GENERAL"]["request_limit"] > 300 and policies["AGENT_ACTION"]["request_limit"] > 120
    assert policies["ADMIN_AUTH"] == abuse_protection.DEFAULT_POLICIES["ADMIN_AUTH"]
    assert policies["SERVICE_ACCOUNT"] == abuse_protection.DEFAULT_POLICIES["SERVICE_ACCOUNT"]
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    abuse_protection.initialize_abuse_protection()
    stored = {p["category"]: p for p in abuse_protection.list_policies()}
    assert stored["GENERAL"]["updated_by"] == E2E_OVERRIDE_ACTOR
    assert stored["ADMIN_AUTH"]["updated_by"] == "system"


def test_production_refuses_a_database_seeded_by_the_override(fresh_database, monkeypatch):
    monkeypatch.setenv("GREYGUARD_ENV", "test")
    monkeypatch.setenv(E2E_OVERRIDE_VARIABLE, E2E_OVERRIDE_SENTINEL)
    abuse_protection.initialize_abuse_protection()
    # The same database is then started as production, without the variable.
    monkeypatch.delenv("GREYGUARD_ENV")
    monkeypatch.delenv(E2E_OVERRIDE_VARIABLE)
    with pytest.raises(RateLimitOverrideError, match="must not run in production"):
        abuse_protection.assert_no_test_override_in_production("production")
