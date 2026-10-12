"""Deployment configuration: Render (free web service) + Neon (free Postgres) + the scheduled prune workflow.

These guard the "$0 and no secrets in Git" promises of the README's "Deploy for free" section."""
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_SETTINGS = {"DATABASE_URL", "SECRET_KEY", "PUBLIC_URL", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"}


def test_render_blueprint_is_one_free_web_service_without_secrets():
    bp = yaml.safe_load((ROOT / "render.yaml").read_text())
    assert set(bp) == {"services"}, "no Render databases or other resources: Render's free Postgres expires"
    [svc] = bp["services"]
    assert svc["type"] == "web" and svc["runtime"] == "docker" and svc["plan"] == "free"
    assert svc["healthCheckPath"] == "/healthz"
    env = {e["key"]: e for e in svc["envVars"]}
    assert PRODUCTION_SETTINGS | {"AGENTSEC_ENV", "DATABASE_DIRECT_URL"} == set(env)
    assert env["AGENTSEC_ENV"]["value"] == "production"
    assert env["SECRET_KEY"] == {"key": "SECRET_KEY", "generateValue": True}
    for key in PRODUCTION_SETTINGS - {"SECRET_KEY"} | {"DATABASE_DIRECT_URL"}:
        assert env[key] == {"key": key, "sync": False}, key      # prompted, never stored in the repository


def test_health_check_path_exists(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_no_fly_io_configuration_remains():
    assert not (ROOT / "fly.toml").exists()
    for path in ("README.md", "Dockerfile", "render.yaml", "app/config.py", "migrations/env.py"):
        assert "fly" not in (ROOT / path).read_text().lower(), path


def test_migrations_prefer_the_direct_url(monkeypatch):
    from app.config import migration_database_url
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@ep-x-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require")
    assert "-pooler" in migration_database_url()
    monkeypatch.setenv("DATABASE_DIRECT_URL",
                       "postgresql://u:p@ep-x.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")
    assert migration_database_url() == ("postgresql+psycopg://u:p@ep-x.ap-southeast-1.aws.neon.tech/neondb"
                                        "?sslmode=require&channel_binding=require")
    monkeypatch.setenv("DATABASE_DIRECT_URL", "  ")
    assert "-pooler" in migration_database_url()


def test_alembic_runs_through_the_direct_url(tmp_path):
    """The pooled DATABASE_URL is unreachable here; migrations must use DATABASE_DIRECT_URL."""
    env = dict(os.environ, DATABASE_URL="postgresql://nobody@127.0.0.1:1/unreachable",
               DATABASE_DIRECT_URL="sqlite:///%s" % (tmp_path / "direct.db"))
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-500:]
    assert (tmp_path / "direct.db").stat().st_size > 0


def test_prune_workflow_runs_the_maintenance_command():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "prune.yml").read_text())
    on = wf.get("on", wf.get(True))                     # YAML 1.1 reads a bare `on` key as True
    assert on["schedule"] and "workflow_dispatch" in on
    job = wf["jobs"]["prune"]
    assert job["env"]["DATABASE_URL"] == "${{ secrets.PRUNE_DATABASE_URL }}"
    assert any(s.get("run") == "python -m app.maintenance prune" for s in job["steps"])
    assert wf["permissions"] == {"contents": "read"}


def test_maintenance_prune_command_removes_expired_runs(client, project):
    """What the workflow runs, against the test database: runs past retention go, recent ones stay."""
    from conftest import fixture
    from app.db import new_session
    from app.maintenance import main
    from app.models import Report, utcnow
    for _ in range(2):
        r = client.post("/api/v1/reports", json={"report": fixture("hardened-report.json")},
                        headers={"Authorization": "Bearer " + project["token"]})
        assert r.status_code == 201
    db = new_session()
    try:
        old = db.query(Report).order_by(Report.uploaded_at).first()
        old.uploaded_at = utcnow() - timedelta(days=400)
        db.commit()
    finally:
        db.close()
    assert main(["prune"]) == 0
    db = new_session()
    try:
        assert db.query(Report).count() == 1
    finally:
        db.close()
