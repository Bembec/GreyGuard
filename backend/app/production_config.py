"""Fail-closed production configuration for GreyGuard."""
from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ProductionConfig:
    environment: str
    allowed_origins: tuple[str, ...]
    trusted_hosts: tuple[str, ...]
    data_directory: str
    behind_proxy: bool


def load_production_config(environ=None):
    env = environ if environ is not None else os.environ
    environment = env.get("GREYGUARD_ENV", "development").strip().lower()
    origins = tuple(item.strip() for item in env.get("GREYGUARD_ALLOWED_ORIGINS", "http://localhost:5173").split(",") if item.strip())
    hosts = tuple(item.strip() for item in env.get("GREYGUARD_TRUSTED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if item.strip())
    data_directory = env.get("GREYGUARD_DATA_DIR", "backend/data").strip()
    if environment == "production":
        missing = [key for key in ("GREYGUARD_BOOTSTRAP_EMAIL", "GREYGUARD_BOOTSTRAP_PASSWORD", "GREYGUARD_ALLOWED_ORIGINS", "GREYGUARD_TRUSTED_HOSTS") if not env.get(key)]
        if missing: raise RuntimeError("Missing required production settings: " + ", ".join(missing))
        if "*" in origins or "*" in hosts: raise RuntimeError("Wildcard origins and hosts are forbidden in production.")
        if len(env["GREYGUARD_BOOTSTRAP_PASSWORD"]) < 16: raise RuntimeError("Production bootstrap password must contain at least 16 characters.")
    return ProductionConfig(environment, origins, hosts, data_directory, env.get("GREYGUARD_BEHIND_PROXY", "false").lower() == "true")
