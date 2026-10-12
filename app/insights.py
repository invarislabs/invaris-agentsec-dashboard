"""Report insights and run comparison for the page, from AgentSec itself.

`agentsec.dashboard.insights` (the local `agentsec dashboard`) computes the aggregates and `agentsec.compare`
the comparison, and `agentsec.verdicts` holds the rules all three views share: a scenario is tested only
when the agent was attacked and judged; `inconclusive` (the adversarial content never reached the agent) is
never passed, and a finding whose scenario is inconclusive in the newer run is never fixed; attack timelines
and per-scenario verdict changes are read from the report.

This module only fills in what an older installed AgentSec does not return yet (0.8.0 and the
`add-dashboard` branch predate `agentsec.verdicts`), using the vendored copy in `_compat_verdicts.py`, so the
page is correct with every supported engine and identical to the CLI and the local dashboard with the
current one (tests/test_engine_parity.py).
"""
from __future__ import annotations

from typing import Any, Dict

from agentsec.attacks import CATEGORIES
from agentsec.evaluators import SEVERITIES, severity_rank

try:
    from agentsec import verdicts as _v
    ENGINE_VERDICTS = True
except ImportError:  # AgentSec 0.8.0 and earlier
    from . import _compat_verdicts as _v
    ENGINE_VERDICTS = False

try:
    from agentsec.dashboard.insights import compare_reports as _engine_compare
    from agentsec.dashboard.insights import insights as _engine_insights
except ImportError as exc:  # pragma: no cover - a deployment problem, not a runtime one
    raise ImportError("this dashboard needs an AgentSec build that includes agentsec.dashboard "
                      "(AgentSec 0.9.0 or later, or a checkout of invaris-agentsec); see README") from exc

STATUSES = _v.STATUSES
inconclusive_count = _v.inconclusive_count
evaluation = _v.evaluation
attack_goals = _v.attack_goals


def insights(report: Dict[str, Any]) -> Dict[str, Any]:
    data = _engine_insights(report)
    if data.get("kind") != "test":
        return data
    for c in data.get("categories", []):
        for k in STATUSES:
            c["by_status"].setdefault(k, 0)
    if any("inconclusive" not in v for v in data.get("vectors", [])):
        undelivered: Dict[str, int] = {}
        for s in report.get("scenarios") or []:
            if isinstance(s, dict) and _v.status_of(s) == "inconclusive":
                key = s.get("vector") or "unknown"
                undelivered[key] = undelivered.get(key, 0) + 1
        for v in data.get("vectors", []):
            v.setdefault("inconclusive", undelivered.get(v["vector"], 0))
    data.setdefault("evaluation", _v.evaluation(report))
    data.setdefault("attack_goals", _v.attack_goals(report))
    data.setdefault("reported", _v.agent_reported(report))
    data.setdefault("pack_categories", sorted({c["category"] for c in data.get("categories", [])} - set(CATEGORIES)))
    return data


def compare_reports(base: Dict[str, Any], head: Dict[str, Any]) -> Dict[str, Any]:
    """`agentsec compare` as data, with verdict changes, what each run measured, and why each finding that
    cannot be called fixed is not comparable."""
    c = _engine_compare(base, head)
    # An older AgentSec compare calls these fixed; the newer run measured nothing there, so they are not.
    untested = [f for f in c["fixed"] if _v.not_comparable_reason(f, head) in ("inconclusive", "not_observable")]
    if untested:
        ids = {f["id"] for f in untested}
        c["fixed"] = [f for f in c["fixed"] if f["id"] not in ids]
        c["not_comparable"] = sorted(c["not_comparable"] + untested, key=_severity_order)
    for f in c["not_comparable"]:
        f.setdefault("reason", _v.not_comparable_reason(f, head))
    c.setdefault("verdict_changes", _v.verdict_changes(base, head))
    if head.get("kind") != "mcp_scan":
        c.setdefault("evaluation", {"base": _v.evaluation(base), "head": _v.evaluation(head)})
    return c


def _severity_order(f: Dict[str, Any]):
    return (-severity_rank(f["severity"]) if f.get("severity") in SEVERITIES else 0, f.get("id") or "")


__all__ = ["ENGINE_VERDICTS", "STATUSES", "attack_goals", "compare_reports", "evaluation", "inconclusive_count",
           "insights"]
