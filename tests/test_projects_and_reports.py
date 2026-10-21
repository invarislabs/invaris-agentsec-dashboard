import gzip
import json
import threading
import time
from datetime import datetime, timedelta, timezone


from tests.conftest import ORIGIN, fixture, sign_in


def upload(client, token, report, metadata=None, gz=True):
    body = json.dumps({"report": report, "metadata": metadata or {}}).encode()
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    if gz:
        body = gzip.compress(body)
        headers["Content-Encoding"] = "gzip"
    return client.post("/api/v1/reports", content=body, headers=headers)


# --- projects and tokens --------------------------------------------------------------------------

def test_projects_are_private_to_their_members(client, project):
    assert [p["slug"] for p in client.get("/api/projects").json()["projects"]] == [project["slug"]]
    client.post("/auth/logout")
    sign_in(client, "mallory")
    assert client.get("/api/projects").json()["projects"] == []
    assert client.get("/api/projects/%s" % project["slug"]).status_code == 404
    assert client.get("/api/projects/%s/reports" % project["slug"]).status_code == 404
    assert client.delete("/api/projects/%s" % project["slug"]).status_code == 404


def test_slugs_are_unique(client):
    sign_in(client)
    a = client.post("/api/projects", json={"name": "My Agent!"}).json()["slug"]
    b = client.post("/api/projects", json={"name": "my agent"}).json()["slug"]
    assert (a, b) == ("my-agent", "my-agent-2")


def test_free_plan_project_and_token_limits(make_client):
    c = make_client(FREE_MAX_PROJECTS=2, FREE_MAX_TOKENS_PER_PROJECT=1)
    sign_in(c)
    assert c.post("/api/projects", json={"name": "a"}).status_code == 201
    assert c.post("/api/projects", json={"name": "b"}).status_code == 201
    r = c.post("/api/projects", json={"name": "c"})
    assert r.status_code == 403 and "Free plan allows 2 projects" in r.json()["detail"]
    assert c.post("/api/projects/a/tokens", json={"name": "t"}).status_code == 201
    assert c.post("/api/projects/a/tokens", json={"name": "t2"}).status_code == 403


def test_tokens_are_shown_once_and_stored_hashed(client, project):
    from app.db import new_session
    from app.models import ApiToken
    listed = client.get("/api/projects/%s/tokens" % project["slug"]).json()["tokens"]
    assert len(listed) == 1 and "token" not in listed[0] and project["token"].startswith(listed[0]["prefix"])
    db = new_session()
    stored = db.query(ApiToken).one()
    assert project["token"] not in (stored.token_hash, stored.prefix) and len(stored.token_hash) == 64
    db.close()


def test_revoked_token_cannot_upload(client, project):
    tid = client.get("/api/projects/%s/tokens" % project["slug"]).json()["tokens"][0]["id"]
    assert upload(client, project["token"], fixture("hardened-report.json")).status_code == 201
    assert client.delete("/api/projects/%s/tokens/%s" % (project["slug"], tid)).status_code == 204
    r = upload(client, project["token"], fixture("hardened-report.json"))
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"


# --- ingestion ------------------------------------------------------------------------------------

def test_upload_stores_the_report_and_its_summary(client, project):
    rep = fixture("vulnerable-report.json")
    r = upload(client, project["token"], rep, {"branch": "main", "commit": "abc1234", "label": "nightly",
                                               "ci_url": "https://github.com/o/r/actions/runs/1"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["url"] == "%s/#/p/%s/r/%s" % (ORIGIN, project["slug"], body["id"])
    runs = client.get("/api/projects/%s/reports" % project["slug"]).json()["reports"]
    e = runs[0]
    assert e["findings"] == rep["summary"]["findings"] and e["by_severity"] == rep["summary"]["by_severity"]
    assert (e["branch"], e["commit"], e["label"], e["name"]) == ("main", "abc1234", "nightly", "vulnerable-rag-agent")
    detail = client.get("/api/projects/%s/reports/%s" % (project["slug"], body["id"])).json()
    assert detail["report"] == rep and detail["insights"]["kind"] == "test"
    assert sum(c["scenarios"] for c in detail["insights"]["categories"]) == rep["summary"]["scenarios"]
    dl = client.get("/api/projects/%s/reports/%s/download" % (project["slug"], body["id"]))
    assert json.loads(dl.content) == rep and "attachment" in dl.headers["content-disposition"]


def test_plain_json_and_bare_reports_are_accepted(client, project):
    rep = fixture("mcp-report.json")
    raw = json.dumps(rep).encode()
    r = client.post("/api/v1/reports", content=raw, headers={"Authorization": "Bearer " + project["token"]})
    assert r.status_code == 201
    e = client.get("/api/projects/%s/reports" % project["slug"]).json()["reports"][0]
    assert e["kind"] == "mcp_scan" and e["name"] == "demo-poisoned"


def test_bad_uploads(client, project):
    h = {"Authorization": "Bearer " + project["token"]}
    assert client.post("/api/v1/reports", content=b"{nope", headers=h).status_code == 400
    r = client.post("/api/v1/reports", content=json.dumps({"report": {"a": 1}}).encode(), headers=h)
    assert r.status_code == 422 and "not an AgentSec report" in r.json()["detail"]
    assert client.post("/api/v1/reports", content=b"{}", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.post("/api/v1/reports", content=b"{}").status_code == 401


def test_size_limit_and_gzip_bomb(make_client):
    c = make_client(FREE_MAX_REPORT_MB=1)
    sign_in(c)
    slug = c.post("/api/projects", json={"name": "p"}).json()["slug"]
    token = c.post("/api/projects/%s/tokens" % slug, json={"name": "t"}).json()["token"]
    bomb = gzip.compress(b"{" + b" " * (5 * 1024 * 1024) + b"}")          # ~5 KB compressed, 5 MB inflated
    r = c.post("/api/v1/reports", content=bomb, headers={"Authorization": "Bearer " + token, "Content-Encoding": "gzip"})
    assert r.status_code == 413


def test_metadata_is_sanitised(client, project):
    upload(client, project["token"], fixture("hardened-report.json"),
           {"ci_url": "javascript:alert(1)", "branch": "x" * 1000, "evil": "y"})
    e = client.get("/api/projects/%s/reports" % project["slug"]).json()["reports"][0]
    assert e["ci_url"] is None and len(e["branch"]) == 255 and "evil" not in e


def test_rolling_window_keeps_the_newest_runs(make_client):
    c = make_client(FREE_MAX_REPORTS_PER_PROJECT=2)
    sign_in(c)
    slug = c.post("/api/projects", json={"name": "p"}).json()["slug"]
    token = c.post("/api/projects/%s/tokens" % slug, json={"name": "t"}).json()["token"]
    for label in ("one", "two", "three"):
        assert upload(c, token, fixture("hardened-report.json"), {"label": label}).status_code == 201
        time.sleep(0.01)
    labels = [e["label"] for e in c.get("/api/projects/%s/reports" % slug).json()["reports"]]
    assert labels == ["three", "two"]


# --- reading, comparing, deleting -----------------------------------------------------------------

def test_compare_runs(client, project):
    base = upload(client, project["token"], fixture("vulnerable-report.json")).json()["id"]
    head = upload(client, project["token"], fixture("hardened-report.json")).json()["id"]
    c = client.get("/api/projects/%s/compare?base=%s&head=%s" % (project["slug"], base, head)).json()
    assert len(c["fixed"]) == fixture("vulnerable-report.json")["summary"]["findings"] and c["regressions"] == 0
    mcp = upload(client, project["token"], fixture("mcp-report.json")).json()["id"]
    assert client.get("/api/projects/%s/compare?base=%s&head=%s" % (project["slug"], base, mcp)).status_code == 422


def test_reports_from_another_project_are_not_reachable(client, project):
    rid = upload(client, project["token"], fixture("hardened-report.json")).json()["id"]
    other = client.post("/api/projects", json={"name": "Other"}).json()["slug"]
    assert client.get("/api/projects/%s/reports/%s" % (other, rid)).status_code == 404
    assert client.delete("/api/projects/%s/reports/%s" % (project["slug"], rid)).status_code == 204
    assert client.get("/api/projects/%s/reports/%s" % (project["slug"], rid)).status_code == 404


def test_deleting_a_project_removes_its_runs(client, project):
    from app.db import new_session
    from app.models import Report
    upload(client, project["token"], fixture("hardened-report.json"))
    assert client.delete("/api/projects/%s" % project["slug"]).status_code == 204
    db = new_session()
    assert db.query(Report).count() == 0
    db.close()


def test_retention_prune(client, project):
    from app.db import new_session
    from app.maintenance import prune_all
    from app.models import Report
    upload(client, project["token"], fixture("hardened-report.json"))
    upload(client, project["token"], fixture("hardened-report.json"))
    db = new_session()
    old = db.query(Report).first()
    old.uploaded_at = datetime.now(timezone.utc) - timedelta(days=200)
    db.commit()
    db.close()
    assert prune_all() == 1
    assert len(client.get("/api/projects/%s/reports" % project["slug"]).json()["reports"]) == 1


def test_agentsec_upload_cli_against_a_running_server(tmp_path, make_client):
    """The real `agentsec upload` client, over real HTTP, into this server."""
    import socket
    import uvicorn
    from agentsec.upload import upload as agentsec_upload
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    c = make_client(PUBLIC_URL="http://127.0.0.1:%d" % port)
    c.headers["Origin"] = "http://127.0.0.1:%d" % port
    sign_in(c)
    slug = c.post("/api/projects", json={"name": "cli"}).json()["slug"]
    token = c.post("/api/projects/%s/tokens" % slug, json={"name": "t"}).json()["token"]
    from app.main import create_app
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    try:
        path = tmp_path / "report.json"
        path.write_text(json.dumps(fixture("vulnerable-report.json")))
        result = agentsec_upload(str(path), "http://127.0.0.1:%d" % port, token, {"label": "from cli"}, no_traces=True)
        assert result["project"] == slug and result["findings"] == 43
        e = c.get("/api/projects/%s/reports" % slug).json()["reports"][0]
        assert e["label"] == "from cli" and e["traces_stripped"] is True
    finally:
        server.should_exit = True
        t.join(5)


def test_hostile_report_fields_are_stored_safely(client, project):
    rep = fixture("hardened-report.json")
    rep["generated_at"] = "2" * 500
    rep["tool"]["version"] = "v" * 500
    rep["run_config"]["policy_path"] = "p/" * 600
    rep["run_config"]["seed"] = 2 ** 40
    rep["run_config"]["policy"]["agent"]["endpoint"] = {"not": "a string"}
    rep["summary"]["passed"] = "lots"
    rep["summary"]["by_severity"]["high"] = "x"
    r = upload(client, project["token"], rep, {"branch": "ma\x00in", "commit": 12345})
    assert r.status_code == 201, r.text
    e = client.get("/api/projects/%s/reports" % project["slug"]).json()["reports"][0]
    assert len(e["generated_at"]) == 40 and len(e["version"]) == 40 and len(e["policy_path"]) == 500
    assert e["seed"] is None and e["target"] is None and e["passed"] is None and e["by_severity"]["high"] == 0
    assert e["branch"] == "main" and e["commit"] is None


def test_corrupt_and_truncated_gzip_are_rejected(client, project):
    h = {"Authorization": "Bearer " + project["token"], "Content-Encoding": "gzip"}
    assert client.post("/api/v1/reports", content=b"definitely not gzip", headers=h).status_code == 400
    whole = gzip.compress(json.dumps(fixture("hardened-report.json")).encode())
    assert client.post("/api/v1/reports", content=whole[: len(whole) // 2], headers=h).status_code == 400
