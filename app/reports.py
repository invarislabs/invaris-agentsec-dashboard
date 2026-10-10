"""Storing, listing and reading uploaded reports. Report logic itself comes from AgentSec."""
from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

try:
    from agentsec.dashboard.index import is_report, summarize_entry
    from agentsec.dashboard.insights import compare_reports, insights
except ImportError as exc:  # pragma: no cover - a deployment problem, not a runtime one
    raise ImportError("this dashboard needs an AgentSec build that includes agentsec.dashboard "
                      "(the release after 0.7.0, or a checkout of invaris-agentsec); see README") from exc

from .models import ApiToken, Project, Report
from .plans import LimitReached, Plan

META_FIELDS = {"branch": 255, "commit": 64, "ci_url": 500, "repository": 255, "label": 200}

__all__ = ["compare_reports", "insights", "store_report", "entry", "load_document", "list_reports", "prune",
           "InvalidReport"]


class InvalidReport(ValueError):
    pass


INT_MAX = 2 ** 31 - 1


def _str(value: Any, limit: int) -> Optional[str]:
    """A string that fits its column: other types become None, NUL bytes (rejected by Postgres) are removed."""
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    text = str(value).replace("\x00", "").strip()
    return text[:limit] if text else None


def _int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or not (0 <= value <= INT_MAX):
        return default
    return value


def _clean_meta(metadata: Any) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not isinstance(metadata, dict):
        return out
    for key, limit in META_FIELDS.items():
        value = _str(metadata.get(key), limit) if isinstance(metadata.get(key), str) else None
        if value:
            out[key] = value
    if "ci_url" in out and urlsplit(out["ci_url"]).scheme not in ("http", "https"):
        del out["ci_url"]           # only links the page can safely open
    return out


def store_report(db: Session, project: Project, plan: Plan, report: Any, metadata: Any,
                 token: Optional[ApiToken] = None, size_bytes: int = 0) -> Report:
    if not is_report(report):
        raise InvalidReport("the body is not an AgentSec report: it needs findings and scenarios lists")
    try:
        meta = summarize_entry(report)
    except (TypeError, ValueError, AttributeError) as exc:
        raise InvalidReport("the report's run_config or summary is malformed: %s" % exc)
    extra = _clean_meta(metadata)
    raw = json.dumps(report, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > plan.max_report_mb * 1024 * 1024:
        raise LimitReached("report is larger than the %s plan's %d MB limit" % (plan.label, plan.max_report_mb))
    sev = meta["by_severity"]
    stripped = any(isinstance(s, dict) and isinstance(s.get("trace"), dict) and s["trace"].get("events_stripped")
                   for s in report.get("scenarios", []))
    row = Report(
        project_id=project.id, token_id=token.id if token else None,
        kind=meta["kind"], name=_str(meta["name"], 200) or "agent", target=_str(meta.get("target"), 2000),
        generated_at=_str(meta.get("generated_at"), 40), agentsec_version=_str(meta.get("version"), 40),
        seed=_int(meta.get("seed")), policy_path=_str(meta.get("policy_path"), 500),
        policy_sha256=_str(meta.get("policy_sha256"), 64),
        scenarios=_int(meta.get("scenarios"), 0), passed=_int(meta.get("passed")),
        with_findings=_int(meta.get("with_findings")), errors=_int(meta.get("errors")),
        not_observable=_int(meta.get("not_observable")), findings=_int(meta.get("findings"), 0),
        critical=_int(sev["critical"], 0), high=_int(sev["high"], 0), medium=_int(sev["medium"], 0),
        low=_int(sev["low"], 0),
        traces_stripped=stripped, size_bytes=size_bytes or len(raw), content=gzip.compress(raw), **extra)
    db.add(row)
    db.flush()
    # Rolling window: keep the newest runs up to the plan's limit.
    count = db.scalar(select(func.count()).select_from(Report).where(Report.project_id == project.id))
    if count and count > plan.max_reports_per_project:
        old = db.scalars(select(Report.id).where(Report.project_id == project.id)
                         .order_by(Report.uploaded_at.asc()).limit(count - plan.max_reports_per_project)).all()
        db.execute(delete(Report).where(Report.id.in_(old)))
    return row


def display_label(r: Report) -> str:
    bits = []
    if r.label:
        bits.append(r.label)
    if r.branch:
        bits.append(r.branch)
    if r.commit:
        bits.append(r.commit[:7])
    return " ".join(bits) if bits else "uploaded " + r.uploaded_at.strftime("%Y-%m-%d %H:%M")


def entry(r: Report) -> Dict[str, Any]:
    """Same shape as the local dashboard's report entries, plus upload metadata."""
    return {
        "id": r.id, "kind": r.kind, "name": r.name, "target": r.target, "generated_at": r.generated_at or
        r.uploaded_at.isoformat(), "uploaded_at": r.uploaded_at.isoformat(), "version": r.agentsec_version,
        "seed": r.seed, "policy_path": r.policy_path, "policy_sha256": r.policy_sha256,
        "scenarios": r.scenarios, "passed": r.passed, "with_findings": r.with_findings, "errors": r.errors,
        "not_observable": r.not_observable, "findings": r.findings,
        "by_severity": {"critical": r.critical, "high": r.high, "medium": r.medium, "low": r.low},
        "branch": r.branch, "commit": r.commit, "ci_url": r.ci_url, "repository": r.repository, "label": r.label,
        "traces_stripped": r.traces_stripped, "size_bytes": r.size_bytes,
        "display_path": display_label(r), "error": None,
        "mtime": r.uploaded_at.timestamp(),
    }


def load_document(r: Report) -> Dict[str, Any]:
    return json.loads(gzip.decompress(r.content).decode("utf-8"))


def list_reports(db: Session, project: Project, limit: int = 200, branch: Optional[str] = None,
                 name: Optional[str] = None) -> List[Report]:
    cols = [c for c in Report.__table__.columns if c.name != "content"]
    q = select(*cols).where(Report.project_id == project.id)
    if branch:
        q = q.where(Report.branch == branch)
    if name:
        q = q.where(Report.name == name)
    rows = db.execute(q.order_by(Report.uploaded_at.desc()).limit(limit)).all()
    return [Report(**row._asdict()) for row in rows]


def prune(db: Session, project: Project, plan: Plan, now: Optional[datetime] = None) -> int:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=plan.retention_days)
    result = db.execute(delete(Report).where(Report.project_id == project.id, Report.uploaded_at < cutoff))
    return result.rowcount or 0
