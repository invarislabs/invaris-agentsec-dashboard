from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Optional, Tuple
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .db import get_db
from .models import Membership, Project, User

TOKEN_PREFIX = "asp_"

# Report text is hostile (adversarial payloads and agent output): the page only ever inserts it as text,
# and this policy allows nothing but the dashboard's own script, styles and fonts.
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; "
       "img-src 'self' data: https://avatars.githubusercontent.com; connect-src 'self'; "
       "base-uri 'none'; form-action 'self' https://github.com; frame-ancestors 'none'")


def new_token() -> Tuple[str, str, str]:
    """(token shown once, prefix kept for display, sha256 hash stored)."""
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    return token, token[:12], hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


class SameOriginWrites(BaseHTTPMiddleware):
    """State-changing requests made with the session cookie must come from this site's own pages.
    Uploads (/api/v1/) authenticate with a bearer token instead and are exempt."""

    def __init__(self, app, public_url: str):
        super().__init__(app)
        parts = urlsplit(public_url)
        self.origin = "%s://%s" % (parts.scheme, parts.netloc)

    async def dispatch(self, request, call_next):
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and not request.url.path.startswith("/api/v1/"):
            origin = request.headers.get("origin")
            if origin is None:
                ref = request.headers.get("referer")
                if ref:
                    p = urlsplit(ref)
                    origin = "%s://%s" % (p.scheme, p.netloc)
            own = "%s://%s" % (request.url.scheme, request.headers.get("host", ""))
            if origin not in (self.origin, own):
                return JSONResponse({"detail": "cross-site request refused"}, status_code=403)
        return await call_next(request)


def current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    uid = request.session.get("uid")
    if not uid:
        return None
    user = db.get(User, uid)
    if user is None:
        request.session.clear()
    return user


def current_user(user: Optional[User] = Depends(current_user_optional)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="sign in first")
    return user


def project_for(slug: str, user: User, db: Session, role: Optional[str] = None) -> Project:
    """The project, if the user is a member. Not found and not allowed look the same (404)."""
    row = db.execute(select(Project, Membership).join(Membership, Membership.project_id == Project.id)
                     .where(Project.slug == slug, Membership.user_id == user.id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="no such project")
    project, membership = row
    if role == "owner" and membership.role != "owner":
        raise HTTPException(status_code=403, detail="only the project owner can do this")
    return project
