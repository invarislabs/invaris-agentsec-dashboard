from pathlib import Path

import httpx
import pytest

from app.config import ConfigError, get_settings
from tests.conftest import ORIGIN, configure, sign_in

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


def test_api_needs_a_session(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/projects").status_code == 401


def test_dev_login_and_logout(client):
    sign_in(client, "bob")
    me = client.get("/api/me").json()
    assert me["user"]["login"] == "bob" and me["plan"]["name"] == "free"
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/api/me").status_code == 401


def test_dev_login_is_off_unless_enabled(make_client):
    c = make_client(AGENTSEC_DEV_LOGIN="0")
    assert c.post("/auth/dev-login", json={"login": "x"}).status_code == 404
    assert c.get("/api/auth-config").json() == {"github": False, "dev_login": False}


def test_production_refuses_unsafe_configuration(tmp_path, monkeypatch):
    configure(tmp_path)
    for k, v in {"AGENTSEC_ENV": "production", "SECRET_KEY": "short", "AGENTSEC_DEV_LOGIN": "0",
                 "GITHUB_CLIENT_ID": "id", "GITHUB_CLIENT_SECRET": "s"}.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    with pytest.raises(ConfigError, match="SECRET_KEY"):
        get_settings()
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    monkeypatch.setenv("AGENTSEC_DEV_LOGIN", "1")
    get_settings.cache_clear()
    with pytest.raises(ConfigError, match="DEV_LOGIN"):
        get_settings()
    monkeypatch.setenv("AGENTSEC_DEV_LOGIN", "0")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "")
    get_settings.cache_clear()
    with pytest.raises(ConfigError, match="GITHUB_CLIENT_ID"):
        get_settings()
    monkeypatch.setenv("GITHUB_CLIENT_ID", "id")
    get_settings.cache_clear()
    assert get_settings().secure_cookies is True
    # Unrecognised environment names get every production check, not none of them.
    monkeypatch.setenv("AGENTSEC_ENV", "staging")
    monkeypatch.setenv("SECRET_KEY", "short")
    get_settings.cache_clear()
    with pytest.raises(ConfigError, match="SECRET_KEY"):
        get_settings()
    get_settings.cache_clear()


def _fake_github(monkeypatch, profile):
    def handler(request: httpx.Request):
        if request.url.path == "/login/oauth/access_token":
            assert b"code=good" in request.content
            return httpx.Response(200, json={"access_token": "gho_x"})
        if request.url.path == "/user":
            assert request.headers["authorization"] == "Bearer gho_x"
            return httpx.Response(200, json=profile)
        return httpx.Response(404)
    real = httpx.AsyncClient
    monkeypatch.setattr("app.auth.httpx.AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


def test_github_sign_in_flow(make_client, monkeypatch):
    c = make_client(GITHUB_CLIENT_ID="cid", GITHUB_CLIENT_SECRET="secret")
    _fake_github(monkeypatch, {"id": 42, "login": "octo", "name": "Octo Cat", "avatar_url": "https://avatars.githubusercontent.com/u/42"})
    start = c.get("/auth/github", follow_redirects=False)
    assert start.status_code == 302 and start.headers["location"].startswith("https://github.com/login/oauth/authorize?")
    state = httpx.URL(start.headers["location"]).params["state"]
    assert "client_secret" not in start.headers["location"]
    bad = c.get("/auth/github/callback?code=good&state=wrong", follow_redirects=False)
    assert bad.headers["location"] == "/#/signin?error=state"
    start = c.get("/auth/github", follow_redirects=False)
    state = httpx.URL(start.headers["location"]).params["state"]
    done = c.get("/auth/github/callback?code=good&state=" + state, follow_redirects=False)
    assert done.status_code == 302 and done.headers["location"] == "/"
    me = c.get("/api/me").json()["user"]
    assert me["login"] == "octo" and me["name"] == "Octo Cat"


def test_github_login_renamed_to_a_taken_name(make_client, monkeypatch):
    from app.auth import upsert_github_user
    from app.db import new_session
    make_client()
    db = new_session()
    a = upsert_github_user(db, 1, "sam", None, None)
    b = upsert_github_user(db, 2, "sam", None, None)      # GitHub user 1 renamed away, user 2 took "sam"
    db.commit()
    assert b.login == "sam" and a.login == "sam-1" and a.id != b.id
    db.close()


def test_cross_site_writes_are_refused(client):
    sign_in(client)
    r = client.post("/api/projects", json={"name": "x"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.post("/api/projects", json={"name": "x"}, headers={"Origin": "", "Referer": "https://evil.example/page"})
    assert r.status_code == 403
    assert client.post("/api/projects", json={"name": "x"}, headers={"Origin": ORIGIN}).status_code == 201


def test_security_headers_and_static(client):
    r = client.get("/")
    assert r.status_code == 200 and b"/static/app.js" in r.content
    csp = r.headers["content-security-policy"]
    assert "default-src 'none'" in csp and "script-src 'self'" in csp and "unsafe-inline" not in csp
    assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/api/auth-config").headers["cache-control"] == "no-store"
    assert client.get("/healthz").json() == {"ok": True}


def test_session_cookie_flags(client):
    r = client.post("/auth/dev-login", json={"login": "alice"})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_page_never_inserts_report_text_as_markup():
    js = (STATIC / "app.js").read_text()
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
        assert sink not in js, sink


def test_database_urls_from_hosting_providers_are_accepted():
    """Neon, Supabase, Render, Railway and Heroku give DATABASE_URL as postgres:// or postgresql://."""
    from app.config import database_url, engine_options
    want = "postgresql+psycopg://u:p@db.internal:5432/app?sslmode=require"
    assert database_url("postgres://u:p@db.internal:5432/app?sslmode=require") == want
    assert database_url("postgresql://u:p@db.internal:5432/app?sslmode=require") == want
    assert database_url(want) == want
    assert database_url("postgresql+asyncpg://x/y") == "postgresql+asyncpg://x/y"
    assert database_url("sqlite:///dash.db") == "sqlite:///dash.db"
    assert database_url("  ").startswith("postgresql+psycopg://")
    # behind PgBouncer (Neon's pooled endpoint) prepared statements must stay off
    assert engine_options(want)["connect_args"] == {"prepare_threshold": None}
    assert engine_options("sqlite:///x.db") == {"connect_args": {"check_same_thread": False}}


def test_settings_normalise_database_url(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/d")
    monkeypatch.setenv("AGENTSEC_ENV", "development")
    get_settings.cache_clear()
    try:
        assert get_settings().database_url == "postgresql+psycopg://u:p@h:5432/d"
    finally:
        get_settings.cache_clear()
