"""What each plan allows.

At launch every account is on the free plan. Premium features will be added as new plans with their
own limits and flags; the rest of the app asks this module, never hard-codes a limit, so adding a
paid plan means adding an entry here (and billing elsewhere), not editing every endpoint.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict

from .config import get_settings


@dataclass(frozen=True)
class Plan:
    name: str
    label: str
    max_projects: int
    max_reports_per_project: int     # oldest runs beyond this are removed when a new one arrives
    retention_days: int              # runs older than this are removed by `python -m app.maintenance prune`
    max_report_mb: int               # uncompressed report.json size
    max_tokens_per_project: int
    team_members: bool               # planned premium feature: invite others to a project

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def free_plan() -> Plan:
    s = get_settings()
    return Plan(name="free", label="Free", max_projects=s.free_max_projects,
                max_reports_per_project=s.free_max_reports_per_project, retention_days=s.free_retention_days,
                max_report_mb=s.free_max_report_mb, max_tokens_per_project=s.free_max_tokens_per_project,
                team_members=False)


def plan_named(name: str) -> Plan:
    # Only "free" exists today. Unknown names fall back to free rather than failing closed for users.
    return free_plan()


class LimitReached(Exception):
    """A plan limit stops this action. The message is user-facing."""
