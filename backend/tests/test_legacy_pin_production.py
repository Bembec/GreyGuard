"""The shared development PIN must never grant access in production."""

import pytest
from fastapi import HTTPException

from backend.app import api
from backend.app.production_config import load_production_config

PRODUCTION = {
    "GREYGUARD_ENV": "production",
    "GREYGUARD_BOOTSTRAP_EMAIL": "owner@example.com",
    "GREYGUARD_BOOTSTRAP_PASSWORD": "VeryStrongPassword123!",
    "GREYGUARD_ALLOWED_ORIGINS": "https://greyguard.example.com",
    "GREYGUARD_TRUSTED_HOSTS": "greyguard.example.com",
}


def test_production_refuses_to_start_with_the_shared_pin():
    with pytest.raises(RuntimeError, match="forbidden in production"):
        load_production_config({**PRODUCTION, "GREYGUARD_ADMIN_PIN": "123456"})


def test_production_starts_without_the_shared_pin():
    assert load_production_config(PRODUCTION).environment == "production"


def test_shared_pin_is_rejected_at_request_time_in_production(monkeypatch):
    monkeypatch.setenv("GREYGUARD_ENV", "production")
    monkeypatch.setenv("GREYGUARD_ADMIN_PIN", "123456")
    with pytest.raises(HTTPException) as error:
        api.require_admin("123456")
    assert error.value.status_code == 401


def test_shared_pin_still_works_in_development(monkeypatch):
    monkeypatch.setenv("GREYGUARD_ENV", "development")
    monkeypatch.setenv("GREYGUARD_ADMIN_PIN", "123456")
    assert api.require_admin("123456")["role"] == "PLATFORM_ADMIN"
