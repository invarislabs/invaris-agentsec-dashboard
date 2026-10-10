from __future__ import annotations

import os

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from . import __version__
from .api import router as api_router
from .auth import router as auth_router
from .config import get_settings
from .db import get_db
from .ingest import router as ingest_router
from .security import SameOriginWrites, SecurityHeaders

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="AgentSec dashboard", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    # Order matters: the last added runs first. Sessions must wrap everything that reads request.session.
    app.add_middleware(SameOriginWrites, public_url=s.public_url)
    app.add_middleware(SecurityHeaders)
    app.add_middleware(SessionMiddleware, secret_key=s.secret_key, session_cookie="agentsec_session",
                       max_age=s.session_days * 86400, same_site="lax", https_only=s.secure_cookies)
    app.include_router(auth_router)
    app.include_router(api_router)
    app.include_router(ingest_router)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(os.path.join(STATIC, "index.html"), headers={"Cache-Control": "no-cache"})

    @app.get("/healthz", include_in_schema=False)
    def healthz(db: Session = Depends(get_db)):
        db.execute(text("select 1"))
        return JSONResponse({"ok": True})

    return app

