"""JSON API used by the dashboard page (session cookie)."""
from __future__ import annotations

import gzip
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agentsec import __version__ as agentsec_version
from agentsec.attacks import CATEGORIES
from agentsec.evaluators import SEVERITIES
from agentsec.owasp import ASI, FRAMEWORK, REFERENCE_URL

from . import reports as store
from .config import get_settings
from .db import get_db
from .models import ApiToken, Membership, Project, Report, User, utcnow
from .plans import plan_named
from .security import current_user, new_token, project_for

router = APIRouter(prefix="/api")


def _user_dict(u: User):
    return {"id": u.id, "login": u.login, "name": u.name, "avatar_url": u.avatar_url, "plan": u.plan}


@router.get("/me")
def me(user: User = Depends(current_user)):
    plan = plan_named(user.plan)
    return {"user": _user_dict(user), "plan": plan.to_dict()}


@router.get("/meta")
def meta(user: User = Depends(current_user)):
    return {"version": agentsec_version, "severities": list(SEVERITIES), "categories": list(CATEGORIES),
            "owasp": {"name": FRAMEWORK, "url": REFERENCE_URL, "categories": ASI},
            "public_url": get_settings().public_url}


# --- projects -------------------------------------------------------------------------------------

def _project_dict(db: Session, p: Project, role: str):
    count = db.scalar(select(func.count()).select_from(Report).where(Report.project_id == p.id)) or 0
    latest = store.list_reports(db, p, limit=1)
    return {"id": p.id, "slug": p.slug, "name": p.name, "role": role, "created_at": p.created_at.isoformat(),
            "reports": count, "latest": store.entry(latest[0]) if latest else None}


@router.get("/projects")
def projects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Project, Membership.role).join(Membership, Membership.project_id == Project.id)
                      .where(Membership.user_id == user.id).order_by(Project.created_at)).all()
    return {"projects": [_project_dict(db, p, role) for p, role in rows]}


class NewProject(BaseModel):
    name: str = Field(min_length=1, max_length=120)


def _slugify(db: Session, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "project"
    slug, n = base, 1
    while db.scalar(select(Project.id).where(Project.slug == slug)):
        n += 1
        slug = "%s-%d" % (base, n)
    return slug


@router.post("/projects", status_code=201)
def create_project(body: NewProject, user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = plan_named(user.plan)
    owned = db.scalar(select(func.count()).select_from(Project).where(Project.owner_id == user.id)) or 0
    if owned >= plan.max_projects:
        raise HTTPException(status_code=403, detail="the %s plan allows %d projects" % (plan.label, plan.max_projects))
    project = Project(name=body.name.strip(), slug=_slugify(db, body.name), owner_id=user.id)
    db.add(project)
    db.flush()
    db.add(Membership(project_id=project.id, user_id=user.id, role="owner"))
    db.commit()
    return _project_dict(db, project, "owner")


def _owner_plan(db: Session, project: Project):
    owner = db.get(User, project.owner_id)
    return plan_named(owner.plan if owner else "free")


@router.get("/projects/{slug}")
def project_detail(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_for(slug, user, db)
    role = db.scalar(select(Membership.role).where(Membership.project_id == p.id, Membership.user_id == user.id))
    d = _project_dict(db, p, role)
    d["plan"] = _owner_plan(db, p).to_dict()
    d["branches"] = sorted(b for b in db.scalars(select(Report.branch).where(Report.project_id == p.id)
                                                  .distinct()).all() if b)
    return d


class RenameProject(BaseModel):
    name: str = Field(min_length=1, max_length=120)


@router.patch("/projects/{slug}")
def rename_project(slug: str, body: RenameProject, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_for(slug, user, db, role="owner")
    p.name = body.name.strip()
    db.commit()
    return {"ok": True}


@router.delete("/projects/{slug}", status_code=204)
def delete_project(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_for(slug, user, db, role="owner")
    db.delete(p)
    db.commit()
    return Response(status_code=204)


# --- reports --------------------------------------------------------------------------------------

@router.get("/projects/{slug}/reports")
def project_reports(slug: str, branch: Optional[str] = None, name: Optional[str] = None,
                    limit: int = Query(200, ge=1, le=500),
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_for(slug, user, db)
    rows = store.list_reports(db, p, limit=limit, branch=branch, name=name)
    entries = [store.entry(r) for r in rows]
    newest = entries[0]["uploaded_at"] if entries else ""
    return {"fingerprint": "%d:%s" % (len(entries), newest), "reports": entries}


def _report_row(db: Session, p: Project, report_id: str) -> Report:
    row = db.get(Report, report_id)
    if row is None or row.project_id != p.id:
        raise HTTPException(status_code=404, detail="no such report in this project")
    return row


@router.get("/projects/{slug}/reports/{report_id}")
def report_detail(slug: str, report_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_for(slug, user, db)
    row = _report_row(db, p, report_id)
    doc = store.load_document(row)
    return {"entry": store.entry(row), "report": doc, "insights": store.insights(doc)}


@router.get("/projects/{slug}/reports/{report_id}/download")
def report_download(slug: str, report_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_for(slug, user, db)
    row = _report_row(db, p, report_id)
    name = "mcp-report.json" if row.kind == "mcp_scan" else "report.json"
    return Response(gzip.decompress(row.content), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="%s"' % name})


@router.delete("/projects/{slug}/reports/{report_id}", status_code=204)
def report_delete(slug: str, report_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_for(slug, user, db, role="owner")
    db.delete(_report_row(db, p, report_id))
    db.commit()
    return Response(status_code=204)


@router.get("/projects/{slug}/compare")
def compare(slug: str, base: str, head: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_for(slug, user, db)
    b, h = _report_row(db, p, base), _report_row(db, p, head)
    if b.kind != h.kind:
        raise HTTPException(status_code=422, detail="cannot compare an MCP scan with an agent test run")
    result = store.compare_reports(store.load_document(b), store.load_document(h))
    result["base"], result["head"] = store.entry(b), store.entry(h)
    return result


# --- tokens ---------------------------------------------------------------------------------------

def _token_dict(t: ApiToken):
    return {"id": t.id, "name": t.name, "prefix": t.prefix, "created_at": t.created_at.isoformat(),
            "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None}


@router.get("/projects/{slug}/tokens")
def tokens(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_for(slug, user, db, role="owner")
    rows = db.scalars(select(ApiToken).where(ApiToken.project_id == p.id, ApiToken.revoked_at.is_(None))
                      .order_by(ApiToken.created_at)).all()
    return {"tokens": [_token_dict(t) for t in rows]}


class NewToken(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@router.post("/projects/{slug}/tokens", status_code=201)
def create_token(slug: str, body: NewToken, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_for(slug, user, db, role="owner")
    plan = _owner_plan(db, p)
    active = db.scalar(select(func.count()).select_from(ApiToken)
                       .where(ApiToken.project_id == p.id, ApiToken.revoked_at.is_(None))) or 0
    if active >= plan.max_tokens_per_project:
        raise HTTPException(status_code=403, detail="the %s plan allows %d tokens per project"
                            % (plan.label, plan.max_tokens_per_project))
    token, prefix, digest = new_token()
    t = ApiToken(project_id=p.id, name=body.name.strip(), prefix=prefix, token_hash=digest, created_by=user.id)
    db.add(t)
    db.commit()
    d = _token_dict(t)
    d["token"] = token      # shown once; only the hash is stored
    return d


@router.delete("/projects/{slug}/tokens/{token_id}", status_code=204)
def revoke_token(slug: str, token_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_for(slug, user, db, role="owner")
    t = db.get(ApiToken, token_id)
    if t is None or t.project_id != p.id:
        raise HTTPException(status_code=404, detail="no such token")
    t.revoked_at = utcnow()
    db.commit()
    return Response(status_code=204)
