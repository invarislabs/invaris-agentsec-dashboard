"""POST /api/v1/reports: what `agentsec upload` and the GitHub Action call, with a project token."""
from __future__ import annotations

import json
import zlib

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import reports as store
from .config import get_settings
from .db import get_db
from .models import ApiToken, Project, User, utcnow
from .plans import LimitReached, plan_named
from .security import TOKEN_PREFIX, hash_token

router = APIRouter(prefix="/api/v1")


def token_from(request: Request, db: Session) -> ApiToken:
    auth = request.headers.get("authorization", "")
    scheme, _, value = auth.partition(" ")
    if scheme.lower() != "bearer" or not value.startswith(TOKEN_PREFIX):
        raise HTTPException(status_code=401, detail="send a project token as 'Authorization: Bearer asp_...'",
                            headers={"WWW-Authenticate": "Bearer"})
    t = db.scalar(select(ApiToken).where(ApiToken.token_hash == hash_token(value.strip())))
    if t is None or t.revoked_at is not None:
        raise HTTPException(status_code=401, detail="invalid or revoked token", headers={"WWW-Authenticate": "Bearer"})
    return t


async def read_body(request: Request, limit: int) -> bytes:
    """Read at most `limit` bytes after decompression, so a small gzip bomb cannot exhaust memory."""
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > limit:
            raise HTTPException(status_code=413, detail="upload too large")
    if request.headers.get("content-encoding", "").lower() == "gzip":
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            out = d.decompress(bytes(raw), limit + 1)
        except zlib.error:
            raise HTTPException(status_code=400, detail="the body is not valid gzip")
        if len(out) > limit or d.unconsumed_tail:
            raise HTTPException(status_code=413, detail="report too large")
        if not d.eof:
            raise HTTPException(status_code=400, detail="the gzip body is truncated")
        return out
    return bytes(raw)


@router.post("/reports", status_code=201)
async def upload_report(request: Request, db: Session = Depends(get_db)):
    token = token_from(request, db)
    project = db.get(Project, token.project_id)
    owner = db.get(User, project.owner_id)
    plan = plan_named(owner.plan if owner else "free")
    limit = plan.max_report_mb * 1024 * 1024
    body = await read_body(request, limit)
    try:
        payload = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="the body must be JSON")
    report = payload.get("report") if isinstance(payload, dict) and "report" in payload else payload
    metadata = payload.get("metadata") if isinstance(payload, dict) else None
    try:
        row = store.store_report(db, project, plan, report, metadata, token=token, size_bytes=len(body))
    except store.InvalidReport as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except LimitReached as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    token.last_used_at = utcnow()
    db.commit()
    url = "%s/#/p/%s/r/%s" % (get_settings().public_url, project.slug, row.id)
    return {"id": row.id, "project": project.slug, "url": url, "findings": row.findings,
            "inconclusive": row.inconclusive}
