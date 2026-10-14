"""Documentation served by the dashboard itself, under /docs.

Public (no sign-in), server-rendered from the Markdown files in `content/`, so the pages work without
JavaScript, can be indexed by search engines, and ship with every deployment of the dashboard.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from ..config import get_settings
from .site import (get_site, render_not_found, render_page, render_search, search_index_gzip, search_index_json,
                   sitemap)

router = APIRouter(prefix="/docs", include_in_schema=False)

# The pages are the same for everyone and never touch the session, so shared caches may keep them briefly
# (tests/test_docs.py checks that no Set-Cookie is ever sent with them).
CACHE = {"Cache-Control": "public, max-age=300"}


def _public_url() -> str:
    return get_settings().public_url


@router.get("", response_class=HTMLResponse)
def docs_home():
    return _page("")


@router.get("/search-index.json")
def docs_search_index(request: Request):
    # The index holds the text of every page (about 330 KB); send it compressed when the browser accepts gzip.
    headers = dict(CACHE, Vary="Accept-Encoding")
    if "gzip" in request.headers.get("accept-encoding", "").lower():
        headers["Content-Encoding"] = "gzip"
        return Response(search_index_gzip(), media_type="application/json", headers=headers)
    return Response(search_index_json(get_site()), media_type="application/json", headers=headers)


@router.get("/sitemap.xml")
def docs_sitemap():
    return Response(sitemap(get_site(), _public_url()), media_type="application/xml", headers=CACHE)


@router.get("/search", response_class=HTMLResponse)
def docs_search(q: str = ""):
    return HTMLResponse(render_search(get_site(), q[:200], _public_url()), headers={"Cache-Control": "no-cache"})


@router.get("/{slug:path}", response_class=HTMLResponse)
def docs_page(slug: str, request: Request):
    clean = slug.strip("/")
    if clean != slug:      # one URL per page: /docs/testing/cli, not /docs/testing/cli/
        target = "/docs" + ("/" + clean if clean else "")
        return RedirectResponse(target + (("?" + request.url.query) if request.url.query else ""), status_code=308)
    return _page(clean)


def _page(slug: str) -> HTMLResponse:
    site = get_site()
    page = site.by_slug.get(slug)
    if page is None:
        return HTMLResponse(render_not_found(site, _public_url()), status_code=404, headers={"Cache-Control": "no-cache"})
    return HTMLResponse(render_page(site, page, _public_url()), headers=CACHE)


__all__ = ["router"]
