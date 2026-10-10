"""Settings, read once from the environment. See .env.example for every variable."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional


def _bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    public_url: str
    github_client_id: Optional[str]
    github_client_secret: Optional[str]
    dev_login: bool
    secure_cookies: bool
    session_days: int
    # Free plan limits (see app/plans.py). Paid plans will get their own values.
    free_max_projects: int
    free_max_reports_per_project: int
    free_retention_days: int
    free_max_report_mb: int
    free_max_tokens_per_project: int
    environment: str = field(default="production")

    @property
    def github_enabled(self) -> bool:
        return bool(self.github_client_id and self.github_client_secret)


class ConfigError(RuntimeError):
    pass


NON_PRODUCTION = ("development", "test")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    environment = os.environ.get("AGENTSEC_ENV", "production").strip().lower()
    if environment not in NON_PRODUCTION:
        environment = "production"      # anything unrecognised ("prod", "staging", a typo) gets every production check
    secret = os.environ.get("SECRET_KEY", "")
    dev_login = _bool("AGENTSEC_DEV_LOGIN")
    if environment == "production":
        if len(secret) < 32:
            raise ConfigError("SECRET_KEY must be set to at least 32 random characters in production")
        if dev_login:
            raise ConfigError("AGENTSEC_DEV_LOGIN cannot be enabled in production")
    settings = Settings(
        database_url=os.environ.get("DATABASE_URL", "postgresql+psycopg://agentsec@localhost:5432/dashboard"),
        secret_key=secret or "dev-only-insecure-secret-key-change-me-0000",
        public_url=os.environ.get("PUBLIC_URL", "http://localhost:8000").rstrip("/"),
        github_client_id=os.environ.get("GITHUB_CLIENT_ID") or None,
        github_client_secret=os.environ.get("GITHUB_CLIENT_SECRET") or None,
        dev_login=dev_login,
        secure_cookies=_bool("SECURE_COOKIES", environment == "production"),
        session_days=_int("SESSION_DAYS", 14),
        free_max_projects=_int("FREE_MAX_PROJECTS", 10),
        free_max_reports_per_project=_int("FREE_MAX_REPORTS_PER_PROJECT", 500),
        free_retention_days=_int("FREE_RETENTION_DAYS", 90),
        free_max_report_mb=_int("FREE_MAX_REPORT_MB", 25),
        free_max_tokens_per_project=_int("FREE_MAX_TOKENS_PER_PROJECT", 10),
        environment=environment,
    )
    if environment == "production" and not settings.github_enabled:
        raise ConfigError("set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET so people can sign in")
    return settings
