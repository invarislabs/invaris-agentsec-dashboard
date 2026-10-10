"""Sign-in with GitHub (OAuth web flow), plus a development-only login.

Only the GitHub identity (id, login, name, avatar) is kept. The GitHub access token is used once to
read the profile and then discarded; it is never stored.
"""
from __future__ import annotations

import re
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User, utcnow

router = APIRouter()

GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_USER = "https://api.github.com/user"


def _callback_url() -> str:
    return get_settings().public_url + "/auth/github/callback"


def _sign_in(request: Request, user: User) -> None:
    request.session.clear()      # new session on sign-in: no fixation
    request.session["uid"] = user.id


@router.get("/api/auth-config")
def auth_config():
    s = get_settings()
    return {"github": s.github_enabled, "dev_login": s.dev_login}


@router.get("/auth/github")
def github_start(request: Request):
    s = get_settings()
    if not s.github_enabled:
        raise HTTPException(status_code=404, detail="GitHub sign-in is not configured")
    state = secrets.token_urlsafe(24)
    request.session["oauth_state"] = state
    query = urlencode({"client_id": s.github_client_id, "redirect_uri": _callback_url(), "scope": "read:user",
                       "state": state, "allow_signup": "true"})
    return RedirectResponse(GITHUB_AUTHORIZE + "?" + query, status_code=302)


@router.get("/auth/github/callback")
async def github_callback(request: Request, code: str = "", state: str = "", db: Session = Depends(get_db)):
    s = get_settings()
    expected = request.session.pop("oauth_state", None)
    if not code or not expected or not secrets.compare_digest(state, expected):
        return RedirectResponse("/#/signin?error=state", status_code=302)
    async with httpx.AsyncClient(timeout=15) as client:
        tok = await client.post(GITHUB_TOKEN, headers={"Accept": "application/json"}, data={
            "client_id": s.github_client_id, "client_secret": s.github_client_secret, "code": code,
            "redirect_uri": _callback_url()})
        access = tok.json().get("access_token") if tok.status_code == 200 else None
        if not access:
            return RedirectResponse("/#/signin?error=github", status_code=302)
        prof = await client.get(GITHUB_USER, headers={"Authorization": "Bearer " + access,
                                                      "Accept": "application/vnd.github+json"})
    if prof.status_code != 200:
        return RedirectResponse("/#/signin?error=github", status_code=302)
    p = prof.json()
    user = upsert_github_user(db, int(p["id"]), str(p["login"]), p.get("name"), p.get("avatar_url"))
    db.commit()
    _sign_in(request, user)
    return RedirectResponse("/", status_code=302)


def upsert_github_user(db: Session, github_id: int, login: str, name, avatar_url) -> User:
    user = db.scalar(select(User).where(User.github_id == github_id))
    clash = db.scalar(select(User).where(User.login == login))
    if clash is not None and (user is None or clash.id != user.id):
        clash.login = "%s-%s" % (clash.login, clash.github_id or clash.id[:6])   # the login was renamed on GitHub
        db.flush()
    if user is None:
        user = User(github_id=github_id, login=login)
        db.add(user)
    user.login, user.name, user.avatar_url = login, name, avatar_url
    user.last_login_at = utcnow()
    db.flush()
    return user


class DevLogin(BaseModel):
    login: str


@router.post("/auth/dev-login")
def dev_login(body: DevLogin, request: Request, db: Session = Depends(get_db)):
    if not get_settings().dev_login:
        raise HTTPException(status_code=404, detail="not found")
    login = body.login.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", login):
        raise HTTPException(status_code=422, detail="use letters, digits and dashes")
    user = db.scalar(select(User).where(User.login == login))
    if user is None:
        user = User(login=login, name=login)
        db.add(user)
    user.last_login_at = utcnow()
    db.commit()
    _sign_in(request, user)
    return {"ok": True}


@router.post("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return Response(status_code=204)
