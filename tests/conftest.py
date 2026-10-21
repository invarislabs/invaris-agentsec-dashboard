"""Test setup. Uses Postgres when TEST_DATABASE_URL is set (as CI does), otherwise a SQLite file.

Fixture reports in tests/fixtures are real `agentsec test` / `agentsec mcp scan` output from AgentSec's
reference agents (vulnerable and --safe) and its poisoned demo MCP server.
"""
import json
import os
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
ORIGIN = "http://testserver"


def configure(tmp_path, **extra):
    from app import db as dbmod
    from app.config import get_settings
    url = os.environ.get("TEST_DATABASE_URL") or "sqlite:///%s" % (tmp_path / "test.db")
    env = {"AGENTSEC_ENV": "development", "AGENTSEC_DEV_LOGIN": "1", "DATABASE_URL": url,
           "PUBLIC_URL": ORIGIN, "SECRET_KEY": "test-secret-key-0123456789-0123456789",  # gitleaks:allow (test only)
           "GITHUB_CLIENT_ID": "", "GITHUB_CLIENT_SECRET": ""}
    env.update({k: str(v) for k, v in extra.items()})
    for k in [k for k in os.environ if k.startswith("FREE_") or k in ("SECURE_COOKIES", "SESSION_DAYS")]:
        del os.environ[k]          # plan limits set by one test must not leak into the next
    for k, v in env.items():
        os.environ[k] = v
    get_settings.cache_clear()
    dbmod.get_engine.cache_clear()
    dbmod._sessionmaker.cache_clear()
    from app.models import Base
    engine = dbmod.get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return get_settings()


@pytest.fixture
def make_client(tmp_path):
    from fastapi.testclient import TestClient
    clients = []

    def make(**settings):
        configure(tmp_path, **settings)
        from app.main import create_app
        c = TestClient(create_app(), headers={"Origin": ORIGIN})
        clients.append(c)
        return c
    yield make
    for c in clients:
        c.close()


@pytest.fixture
def client(make_client):
    return make_client()


def sign_in(client, login="alice"):
    r = client.post("/auth/dev-login", json={"login": login})
    assert r.status_code == 200, r.text
    return client


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def project(client):
    sign_in(client)
    p = client.post("/api/projects", json={"name": "Support agent"}).json()
    token = client.post("/api/projects/%s/tokens" % p["slug"], json={"name": "CI"}).json()["token"]
    return {"slug": p["slug"], "token": token}
