"""The hosted dashboard, the local `agentsec dashboard` and `agentsec compare` must agree.

With an AgentSec that ships `agentsec.verdicts`, the vendored copy (`app/_compat_verdicts.py`) must give the
engine's answers, and the hosted comparison must match the engine's local-dashboard comparison and the CLI's.
With an older AgentSec, the parts that do not need the engine still hold."""
import importlib

import pytest

from conftest import fixture
from app import _compat_verdicts as compat
from app import insights as hosted

FIXTURES = ["email-baseline-report.json", "email-hardened-report.json", "browser-report.json",
            "email-described-report.json", "vulnerable-report.json", "hardened-report.json"]
PAIRS = [("email-baseline-report.json", "email-hardened-report.json"),
         ("email-described-report.json", "email-hardened-report.json"),
         ("vulnerable-report.json", "hardened-report.json"),
         ("email-hardened-report.json", "email-baseline-report.json")]

try:
    engine = importlib.import_module("agentsec.verdicts")
except ImportError:
    engine = None
needs_engine = pytest.mark.skipif(engine is None, reason="the installed AgentSec predates agentsec.verdicts")


@needs_engine
def test_the_vendored_rules_are_the_engines():
    assert hosted.ENGINE_VERDICTS
    assert compat.STATUSES == engine.STATUSES and compat.TESTED == engine.TESTED
    for name in FIXTURES:
        rep = fixture(name)
        for fn in ("evaluation", "attack_goals", "inconclusive_count", "agent_reported"):
            assert getattr(compat, fn)(rep) == getattr(engine, fn)(rep), (fn, name)
    for b, h in PAIRS:
        assert compat.verdict_changes(fixture(b), fixture(h)) == engine.verdict_changes(fixture(b), fixture(h))


@needs_engine
def test_hosted_local_and_cli_comparisons_agree():
    from agentsec.compare import compare
    from agentsec.dashboard.insights import compare_reports as local_compare
    for b, h in PAIRS:
        base, head = fixture(b), fixture(h)
        ours, local, cli = hosted.compare_reports(base, head), local_compare(base, head), compare(base, head)
        for key in ("new", "worse", "fixed", "better", "unchanged", "not_comparable"):
            assert [f["id"] for f in ours[key]] == [f["id"] for f in local[key]], (key, b, h)
            assert sorted(f["id"] for f in ours[key]) == sorted(f["id"] for f in getattr(cli, key)), (key, b, h)
        assert ours["verdict_changes"] == cli.verdict_changes
        assert ours["evaluation"] == {"base": cli.base_evaluation, "head": cli.head_evaluation}
        if "verdict_changes" in local:      # a local dashboard with the verdict port
            assert local["verdict_changes"] == ours["verdict_changes"]
            assert [f.get("reason") for f in local["not_comparable"]] == [f["reason"] for f in ours["not_comparable"]]


@needs_engine
def test_hosted_and_local_insights_agree():
    from agentsec.dashboard.insights import insights as local_insights
    for name in FIXTURES:
        rep = fixture(name)
        ours, local = hosted.insights(rep), local_insights(rep)
        if "evaluation" in local:            # a local dashboard with the verdict port
            for key in ("evaluation", "attack_goals", "reported", "pack_categories", "categories", "vectors"):
                assert ours[key] == local[key], (key, name)


def test_not_observable_is_not_fixed_with_any_engine():
    f = {"id": "m/1:agent_exceeded_role", "rule": "agent_exceeded_role", "scenario_id": "m/1",
         "category": "multi_agent_delegation", "severity": "high", "title": "t", "source": "deterministic"}
    base = {"findings": [f], "scenarios": [{"id": "m/1", "status": "findings"}]}
    head = {"findings": [], "scenarios": [{"id": "m/1", "status": "not_observable"}]}
    c = hosted.compare_reports(base, head)
    assert not c["fixed"] and [x["reason"] for x in c["not_comparable"]] == ["not_observable"]


def test_no_engine_build_counts_an_inconclusive_scenario_as_fixed():
    """Holds with every supported AgentSec: the hosted guard fills in for an older compare."""
    from agentsec.compare import compare
    for b, h in PAIRS:
        base, head = fixture(b), fixture(h)
        ours = hosted.compare_reports(base, head)
        status = {s["id"]: s.get("status") for s in head["scenarios"]}
        unmeasured = ("inconclusive", "error", "not_observable", None)
        assert all(status.get(f["scenario_id"]) not in unmeasured for f in ours["fixed"])
        expected = sorted(f["id"] for f in compare(base, head).fixed if status.get(f["scenario_id"]) not in unmeasured)
        assert sorted(f["id"] for f in ours["fixed"]) == expected
