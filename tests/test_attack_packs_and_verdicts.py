"""AgentSec 0.8.0 reports: inconclusive verdicts, attack goals, evaluation metrics, and run comparison.

The email and browser fixtures are real AgentSec report output over the engine's example attack packs,
driven by SCRIPTED stand-in agents (see tests/fixtures/generate_pack_fixtures.py), not language models.
"""
import copy
import gzip
import json
import os


from conftest import fixture

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def upload(client, token, report, metadata=None):
    return client.post("/api/v1/reports", json={"report": report, "metadata": metadata or {}},
                       headers={"Authorization": "Bearer " + token})


def detail(client, slug, rid):
    return client.get("/api/projects/%s/reports/%s" % (slug, rid)).json()


def test_inconclusive_runs_are_stored_and_never_counted_as_passed(client, project):
    rep = fixture("email-hardened-report.json")
    r = upload(client, project["token"], rep, {"label": "hardened"})
    assert r.status_code == 201 and r.json()["inconclusive"] == 1 and r.json()["findings"] == 0
    [entry] = client.get("/api/projects/%s/reports" % project["slug"]).json()["reports"]
    assert entry["inconclusive"] == 1
    assert entry["passed"] == 7 and entry["passed"] != entry["scenarios"]   # the page never says "all passed"


def test_older_reports_have_no_inconclusive_scenarios(client, project):
    for name, expected in (("vulnerable-report.json", 0), ("hardened-report.json", 0), ("mcp-report.json", None)):
        assert upload(client, project["token"], fixture(name)).json()["inconclusive"] == expected, name


def test_evaluation_counts_only_scenarios_that_measured_the_agent(client, project):
    rid = upload(client, project["token"], fixture("email-baseline-report.json")).json()["id"]
    ins = detail(client, project["slug"], rid)["insights"]
    assert ins["evaluation"] == {"scenarios": 8, "tested": 7, "with_findings": 7, "passed": 0, "inconclusive": 1,
                                 "errors": 0, "not_observable": 0, "finding_rate": 1.0, "coverage": 0.875}
    by_cat = {c["category"]: c for c in ins["categories"]}
    assert by_cat["email_agent_unauthorized_delete"]["by_status"]["inconclusive"] == 1
    assert all(set(c["by_status"]) >= {"findings", "error", "inconclusive", "not_observable", "passed"}
               for c in ins["categories"])
    assert ins["vectors"] == [{"vector": "retrieved_document", "scenarios": 8, "with_findings": 7, "errors": 0,
                               "inconclusive": 1}]
    assert ins["pack_categories"] == sorted(by_cat)        # every category here came from the email pack


def test_attack_goal_timelines_come_from_the_finding_evidence(client, project):
    rep = fixture("email-baseline-report.json")
    rid = upload(client, project["token"], rep).json()["id"]
    goals = detail(client, project["slug"], rid)["insights"]["attack_goals"]
    assert len(goals) == sum(f["rule"] == "attack_goal_achieved" for f in rep["findings"]) == 7
    events = {s["id"]: {e["seq"]: e for e in s["trace"]["events"]} for s in rep["scenarios"]}
    for g in goals:
        ev = events[g["scenario_id"]]
        delivered, action = ev[g["delivered_seq"]], ev[g["action_seq"]]
        assert delivered["type"] == "tool_result" and delivered["tool_name"] == g["delivered_tool"] == "open_email"
        assert action["type"] == "tool_call" and action["tool_name"] == g["action_tool"] == "forward_email"
        assert g["delivered_seq"] < g["action_seq"] and g["calls_in_between"] == 0
        assert 1 <= g["delivered_in_result"] <= g["tool_results"]
        assert g["severity"] == "critical" and not g["goal"].startswith("Attack succeeded")
    # the delayed (mid-task) injection arrived after several benign tool results
    [late] = [g for g in goals if g["scenario_id"] == "email_agent_delayed_injection/arrives_mid_triage"]
    assert late["delivered_in_result"] > 1


def test_browser_pack_mid_task_injection_that_never_arrived_is_inconclusive(client, project):
    rid = upload(client, project["token"], fixture("browser-report.json")).json()["id"]
    d = detail(client, project["slug"], rid)
    status = {s["id"]: s["status"] for s in d["report"]["scenarios"]}
    assert status["browser_agent_delayed_page_injection/cloaked_after_views"] == "inconclusive"
    goals = d["insights"]["attack_goals"]
    assert goals and {g["action_tool"] for g in goals} == {"navigate"}
    assert all(g["scenario_id"] != "browser_agent_delayed_page_injection/cloaked_after_views" for g in goals)


def test_attack_goals_without_traces_or_delivery_tracking():
    from app.insights import attack_goals
    rep = fixture("email-baseline-report.json")
    stripped = copy.deepcopy(rep)
    for s in stripped["scenarios"]:
        s["trace"]["events"] = []
        s["trace"]["events_stripped"] = True
    g = attack_goals(stripped)[0]
    assert g["delivered_seq"] is not None and g["delivered_in_result"] is None and g["calls_in_between"] is None
    untracked = copy.deepcopy(rep)          # a scenario without `exposure`: only the call is evidence
    for f in untracked["findings"]:
        f["evidence"] = [e for e in f["evidence"] if e["type"] == "tool_call"]
    g = attack_goals(untracked)[0]
    assert g["delivered_seq"] is None and g["action_tool"] == "forward_email"
    assert attack_goals(fixture("vulnerable-report.json")) == []


def test_baseline_vs_hardened_never_counts_an_inconclusive_scenario_as_fixed(client, project):
    base = upload(client, project["token"], fixture("email-baseline-report.json"), {"label": "baseline"}).json()["id"]
    head = upload(client, project["token"], fixture("email-hardened-report.json"), {"label": "hardened"}).json()["id"]
    c = client.get("/api/projects/%s/compare?base=%s&head=%s" % (project["slug"], base, head)).json()
    untested = "email_agent_external_send/new_message"
    assert all(f["scenario_id"] != untested for f in c["fixed"]) and len(c["fixed"]) == 12
    assert {f["scenario_id"] for f in c["not_comparable"]} == {untested}
    assert {f["reason"] for f in c["not_comparable"]} == {"inconclusive"}
    changes = {x["id"]: (x["base"], x["head"]) for x in c["verdict_changes"]}
    assert changes[untested] == ("findings", "inconclusive")
    assert changes["email_agent_unauthorized_delete/delete_security_alert"] == ("inconclusive", "passed")
    assert changes["email_agent_forward_exfiltration/overt_body"] == ("findings", "passed")
    assert len(changes) == 8
    assert c["evaluation"]["base"]["with_findings"] == 7 and c["evaluation"]["head"]["passed"] == 7
    assert c["evaluation"]["head"]["inconclusive"] == 1 and c["regressions"] == 0


def test_compare_guard_holds_with_an_agentsec_compare_that_predates_inconclusive(monkeypatch):
    """The CI build of agentsec.dashboard can predate 0.8.0, whose compare called these findings fixed."""
    from app import insights as mod
    base, head = fixture("email-baseline-report.json"), fixture("email-hardened-report.json")
    real = mod._engine_compare

    def old_compare(b, h):
        c = real(b, h)
        c["fixed"] = c["fixed"] + c["not_comparable"]       # what a pre-0.8.0 compare reported
        c["not_comparable"] = []
        return c
    monkeypatch.setattr(mod, "_engine_compare", old_compare)
    c = mod.compare_reports(base, head)
    assert all(f["scenario_id"] != "email_agent_external_send/new_message" for f in c["fixed"])
    assert [f["reason"] for f in c["not_comparable"]] == ["inconclusive", "inconclusive"]
    assert c["not_comparable"][0]["severity"] == "critical"     # still ordered by severity


def test_comparing_older_reports_is_unchanged(client, project):
    base = upload(client, project["token"], fixture("vulnerable-report.json")).json()["id"]
    head = upload(client, project["token"], fixture("hardened-report.json")).json()["id"]
    c = client.get("/api/projects/%s/compare?base=%s&head=%s" % (project["slug"], base, head)).json()
    assert len(c["fixed"]) == fixture("vulnerable-report.json")["summary"]["findings"] and not c["not_comparable"]
    assert all(x["head"] == "passed" for x in c["verdict_changes"])


def test_migration_backfills_inconclusive_for_stored_runs(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    url = "sqlite:///%s" % (tmp_path / "m.db")
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(ROOT, "migrations"))
    command.upgrade(cfg, "0001")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("insert into users (id, login, plan, created_at) values ('u', 'alice', 'free', '2026-10-01')"))
        conn.execute(text("insert into projects (id, slug, name, owner_id, created_at) values ('p', 'p', 'P', 'u', '2026-10-01')"))
        for rid, kind, rep in (("a", "test", fixture("email-hardened-report.json")),
                               ("b", "test", fixture("hardened-report.json")),
                               ("c", "mcp_scan", fixture("mcp-report.json"))):
            conn.execute(text("insert into reports (id, project_id, uploaded_at, kind, name, scenarios, findings, critical, "
                              "high, medium, low, traces_stripped, size_bytes, content) values (:id, 'p', '2026-10-01', "
                              ":kind, 'x', 0, 0, 0, 0, 0, 0, 0, 0, :content)"),
                         {"id": rid, "kind": kind, "content": gzip.compress(json.dumps(rep).encode())})
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        got = dict(conn.execute(text("select id, inconclusive from reports")).all())
    assert got == {"a": 1, "b": 0, "c": None}
    command.downgrade(cfg, "0001")
    engine.dispose()


def test_scripted_fixtures_are_labelled_as_scripted():
    """The pack fixtures come from scripted stand-ins; nothing in the repository may present them as model results."""
    src = open(os.path.join(ROOT, "tests", "fixtures", "generate_pack_fixtures.py")).read()
    assert "SCRIPTED STAND-INS" in src and "not language models" in src
    readme = open(os.path.join(ROOT, "README.md")).read()
    assert "scripted stand-in" in readme


def test_newer_report_format_with_delivery_goals_and_agent_description(client, project):
    """Reports from an AgentSec with `agentsec.verdicts` carry scenario `delivery`, declared `attack_goals` and
    `run_config.agent_reported`; the dashboard shows them and keeps reading older reports."""
    rep = fixture("email-described-report.json")
    r = upload(client, project["token"], rep)
    assert r.status_code == 201 and r.json()["inconclusive"] == 1
    d = detail(client, project["slug"], r.json()["id"])
    assert d["insights"]["reported"] == [{"name": "email-assistant", "backend": "scripted", "configuration": "baseline"}]
    by_sc = {s["id"]: s for s in d["report"]["scenarios"]}
    for g in d["insights"]["attack_goals"]:
        assert g["delivered_seq"] == by_sc[g["scenario_id"]]["delivery"]["seq"]
    undelivered = by_sc["email_agent_unauthorized_delete/delete_security_alert"]
    assert undelivered["delivery"]["delivered"] is False
    assert all(g["achieved"] is None for g in undelivered["attack_goals"])     # not tested, not resisted
    # 0.8.0-format reports have none of these and still work
    old = detail(client, project["slug"], upload(client, project["token"], fixture("email-baseline-report.json")).json()["id"])
    assert old["insights"]["reported"] == [] and len(old["insights"]["attack_goals"]) == 7


def test_the_page_never_presents_a_scripted_run_as_a_model_result():
    js = open(os.path.join(ROOT, "app", "static", "app.js"), encoding="utf-8").read()
    assert "Scripted stand-in" in js and 'a.backend === "scripted"' in js
    assert "say nothing about any model" in js
