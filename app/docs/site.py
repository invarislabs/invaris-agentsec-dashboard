"""The documentation site: pages, navigation, search and the HTML page shell.

Pages are Markdown files under `app/docs/content/`. A file's path is its URL: `content/testing/cli.md` is served
at `/docs/testing/cli`, and `content/index.md` at `/docs`. Its front matter gives the title, the description
used for search engines and link previews, the sidebar section and its order there. Everything is parsed once,
when the dashboard starts, and kept in memory.
"""
from __future__ import annotations

import gzip
import html
import json
import logging
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from .. import __version__
from .assets import DIAGRAMS, IMAGES, Assets, load_assets
from .markdown import Heading, parse_front_matter, render

log = logging.getLogger("app.docs")

CONTENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content")
ENGINE_REPO = "https://github.com/invarislabs/invaris-agentsec"
DASHBOARD_REPO = "https://github.com/invarislabs/invaris-agentsec-dashboard"
WEBSITE = "https://www.invarislabs.com/"
EDIT_BASE = DASHBOARD_REPO + "/blob/main/app/docs/content/"

# Search and social metadata. Titles and descriptions beyond these lengths get cut off in search results, so a
# page whose `title`/`description` is longer sets a shorter `seo_title`/`seo_description` in its front matter.
SITE_NAME = "AgentSec Docs"
TITLE_SUFFIX = " | " + SITE_NAME
MAX_SEO_TITLE = 65
MAX_SEO_DESCRIPTION = 165
SOCIAL_CARD = "/static/social-card.png"          # 1200x630, made by scripts/make_social_card.py
SOCIAL_CARD_ALT = "AgentSec Docs: security testing for AI agents, open source, from your terminal to CI"
ORG_PROFILES = ["https://github.com/invarislabs", "https://x.com/InvarisLabs",
                "https://www.linkedin.com/company/invarislabs"]
ENGINE_PACKAGE = "https://pypi.org/project/invaris-agentsec/"

# Sidebar groups, in order. A page names its group with `section:` in its front matter.
SECTIONS: List[Tuple[str, str]] = [
    ("start", "Get started"),
    ("guide", "Using the dashboard"),
    ("results", "Understanding results"),
    ("testing", "Testing guides"),
    ("developers", "Developer guide"),
    ("reference", "Reference"),
]
SECTION_TITLES = dict(SECTIONS)


class DocsError(ValueError):
    """A documentation page is malformed. Raised at startup so a broken page never ships."""


@dataclass
class Page:
    slug: str                 # "" for /docs, else "testing/cli"
    path: str                 # file path relative to content/
    title: str
    nav_title: str
    description: str
    section: str
    order: int
    html: str
    headings: List[Heading]
    sections: List[Tuple[str, str, str]]
    links: List[str] = field(default_factory=list)
    figures: List[str] = field(default_factory=list)
    seo_title: str = ""        # optional front matter: the <title> and social title, when `title` is not enough
    seo_description: str = ""  # optional front matter: the meta description, when `description` is too long

    @property
    def url(self) -> str:
        return "/docs" + ("/" + self.slug if self.slug else "")

    @property
    def social_title(self) -> str:
        """The title search results and link previews show (without the site name)."""
        return self.seo_title or self.title

    @property
    def head_title(self) -> str:
        """The <title>: an explicit `seo_title` is used as written; otherwise the page title plus the site name."""
        return self.seo_title or self.title + TITLE_SUFFIX

    @property
    def meta_description(self) -> str:
        return self.seo_description or self.description


@dataclass
class Site:
    pages: List[Page]                       # in sidebar order
    by_slug: Dict[str, Page]
    # Pages that could not be loaded ("path: reason"). Production serves the rest; tests load with strict=True.
    errors: List[str] = field(default_factory=list)
    assets: Assets = field(default_factory=Assets)

    def section_home(self, section: str) -> Optional[Page]:
        """The first page of a sidebar section: where its breadcrumb links to."""
        return next((p for p in self.pages if p.section == section), None)

    def neighbours(self, page: Page) -> Tuple[Optional[Page], Optional[Page]]:
        i = self.pages.index(page)
        return (self.pages[i - 1] if i > 0 else None, self.pages[i + 1] if i + 1 < len(self.pages) else None)

    def search_index(self) -> List[Dict[str, str]]:
        """One entry per page section (the text under each `##`/`###` heading), linked to its anchor."""
        out = []
        for p in self.pages:
            intro = [t for hid, _, t in p.sections if not hid]
            out.append({"url": p.url, "page": p.title, "section": SECTION_TITLES[p.section], "heading": "",
                        "text": (p.description + " " + (intro[0] if intro else "")).strip()})
            for hid, heading, text in p.sections:
                if hid:
                    out.append({"url": p.url + "#" + hid, "page": p.title,
                                "section": SECTION_TITLES[p.section], "heading": heading, "text": text})
        return out


def _load_page(rel: str, root: str = CONTENT, assets: Optional[Assets] = None, strict: bool = True,
               problems: Optional[List[str]] = None) -> Page:
    with open(os.path.join(root, rel), encoding="utf-8") as fh:
        raw = fh.read()
    found: List[str] = []
    try:
        meta, body = parse_front_matter(raw)
        rendered = render(body, assets if assets is not None else Assets(), strict=strict, problems=found)
    except ValueError as exc:
        raise DocsError("%s: %s" % (rel, exc)) from exc
    if problems is not None:
        problems.extend("%s: %s" % (rel, f) for f in found)
    for key in ("title", "description", "section"):
        if not meta.get(key):
            raise DocsError("%s: front matter needs `%s`" % (rel, key))
    if meta["section"] not in SECTION_TITLES:
        raise DocsError("%s: unknown section %r (one of %s)" % (rel, meta["section"], ", ".join(SECTION_TITLES)))
    if len(meta.get("seo_title", "")) > MAX_SEO_TITLE:
        raise DocsError("%s: seo_title is longer than %d characters" % (rel, MAX_SEO_TITLE))
    if len(meta.get("seo_description", "")) > MAX_SEO_DESCRIPTION:
        raise DocsError("%s: seo_description is longer than %d characters" % (rel, MAX_SEO_DESCRIPTION))
    slug = rel[:-3].replace(os.sep, "/")
    if slug == "index":
        slug = ""
    elif slug.endswith("/index"):
        slug = slug[:-6]
    return Page(slug=slug, path=rel.replace(os.sep, "/"), title=meta["title"],
                nav_title=meta.get("nav_title") or meta["title"], description=meta["description"],
                section=meta["section"], order=int(meta.get("order", "100")), html=rendered.html,
                headings=rendered.headings, sections=rendered.sections, links=rendered.links,
                figures=rendered.figures, seo_title=meta.get("seo_title", ""),
                seo_description=meta.get("seo_description", ""))


def load_site(root: str = CONTENT, strict: bool = False, images: str = IMAGES, diagrams: str = DIAGRAMS) -> Site:
    """Every page under `root`. With strict=True (the test suite) the first malformed page raises DocsError; otherwise
    (the running dashboard) malformed pages are left out and listed in `Site.errors`, so one bad page can never take
    the documentation, let alone the dashboard, offline. A missing or damaged picture never takes its page out: the
    figure is shown without it and the problem is listed in `Site.errors`."""
    pages: List[Page] = []
    errors: List[str] = []
    try:
        assets = load_assets(images, diagrams, errors=None if strict else errors)
    except ValueError as exc:
        raise DocsError(str(exc)) from exc
    for dirpath, _dirs, files in sorted(os.walk(root)):
        for name in sorted(files):
            if not name.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), root)
            try:
                pages.append(_load_page(rel, root, assets, strict, errors))
            except (DocsError, OSError, UnicodeDecodeError, ValueError) as exc:
                if strict:
                    raise DocsError(str(exc)) if not isinstance(exc, DocsError) else exc
                errors.append(str(exc))
    rank = {key: i for i, (key, _) in enumerate(SECTIONS)}
    pages.sort(key=lambda p: (rank[p.section], p.order, p.title))
    by_slug: Dict[str, Page] = {}
    for p in pages:
        if p.slug in by_slug:
            msg = "%s: another page is already served at %s" % (p.path, p.url)
            if strict:
                raise DocsError(msg)
            errors.append(msg)
            continue
        by_slug[p.slug] = p
    return Site([p for p in pages if by_slug.get(p.slug) is p], by_slug, errors, assets)


@lru_cache(maxsize=1)
def get_site() -> Site:
    """The documentation, parsed once. Never raises: problems are logged and the pages that did load are served."""
    try:
        site = load_site(CONTENT)
    except Exception:  # noqa: BLE001 - the docs must never stop the dashboard from serving
        log.exception("the documentation could not be loaded; /docs will show 'not found' pages")
        site = Site([], {}, ["documentation could not be loaded"])
    for err in site.errors:
        log.error("documentation page skipped: %s", err)
    return site


@lru_cache(maxsize=1)
def search_index_gzip() -> bytes:
    return gzip.compress(search_index_json(get_site()).encode("utf-8"), mtime=0)


# ----------------------------------------------------------------------------------------------- search

# Words too common to tell sections apart. Keep in step with STOP in static/docs.js.
STOPWORDS = frozenset("a an and are as at be by can do does for from get how i if in is it me mean meaning my of on "
                      "or our the this to use using what when where which why with work you your".split())


def _terms(q: str) -> List[str]:
    """Search terms: lowercase words, minus stop words, with a plural "s" folded ("tokens" finds "token")."""
    out = []
    for t in re.split(r"[^a-z0-9_./-]+", q.lower()):
        if not t or t in STOPWORDS:
            continue
        if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        if t not in out:
            out.append(t)
    return out


def _hits(e: Dict[str, str], t: str) -> int:
    heading, page, text = e["_h"], e["_p"], e["_t"]
    hit = 0
    if t in heading:
        hit += 12 + (6 if heading == t or heading.startswith(t) else 0)
    if t in page:
        hit += 6
    return hit + min(text.count(t), 6)


def search(site: Site, query: str, limit: int = 20) -> List[Dict[str, str]]:
    """The same scoring the page's instant search uses (static/docs.js), for the no-JavaScript results page.

    Every term must match (in the heading, page title or text); when nothing matches all of them, sections matching
    the most terms are returned instead. A section whose heading contains the whole query ranks first."""
    terms = _terms(query)
    if not terms:
        return []
    phrase = " ".join(re.split(r"\s+", query.lower().strip()))
    entries = [dict(e, _h=e["heading"].lower(), _p=e["page"].lower(), _t=e["text"].lower()) for e in site.search_index()]
    scored = []
    for e in entries:
        hits = [_hits(e, t) for t in terms]
        matched = sum(1 for h in hits if h)
        if not matched:
            continue
        score = sum(hits) + (30 if len(phrase) > 3 and phrase in e["_h"] else 0)
        scored.append((matched == len(terms), matched, score, e))
    if any(full for full, _, _, _ in scored):
        scored = [x for x in scored if x[0]]
    scored.sort(key=lambda x: (-x[1], -x[2]))
    return [{k: v for k, v in e.items() if not k.startswith("_")} for _, _, _, e in scored[:limit]]


def snippet(text: str, query: str, width: int = 180) -> str:
    low = text.lower()
    pos = min([low.find(t) for t in _terms(query) if low.find(t) >= 0] or [0])
    start = max(0, pos - width // 3)
    s = text[start:start + width]
    return ("…" if start else "") + s + ("…" if start + width < len(text) else "")


# ----------------------------------------------------------------------------------------------- HTML

ICON_SEARCH = ('<svg viewBox="0 0 20 20" width="15" height="15" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5" '
               'fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M13 13l4 4" stroke="currentColor" '
               'stroke-width="1.6" stroke-linecap="round"/></svg>')
ICON_THEME = ('<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M10 3a7 7 0 1 0 0 14V3z" '
              'fill="currentColor"/><circle cx="10" cy="10" r="6.25" fill="none" stroke="currentColor" '
              'stroke-width="1.5"/></svg>')
ICON_GITHUB = ('<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 '
               '0 0 3.58 0 8a8 8 0 0 0 5.47 7.59c.4.07.55-.17.55-.38v-1.33c-2.23.48-2.7-1.07-2.7-1.07-.36-.92-.89-1.17'
               '-.89-1.17-.73-.5.06-.49.06-.49.8.06 1.23.83 1.23.83.72 1.22 1.88.87 2.33.66.07-.52.28-.87.5-1.07-1.78-.2'
               '-3.65-.89-3.65-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.22 2.2.82a7.6 7.6 0 0 1 4 0c1.53'
               '-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73'
               '.54 1.48v2.2c0 .21.15.46.55.38A8 8 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>')

E = lambda s: html.escape(str(s), quote=True)  # noqa: E731


def _sidebar(site: Site, current: Optional[Page]) -> str:
    groups = []
    for key, title in SECTIONS:
        items = [p for p in site.pages if p.section == key]
        if not items:
            continue
        links = "".join('<li><a href="%s"%s>%s</a></li>' % (
            E(p.url), ' class="active" aria-current="page"' if current is p else "", E(p.nav_title)) for p in items)
        groups.append('<div class="dx-nav-group"><h2>%s</h2><ul>%s</ul></div>' % (E(title), links))
    return "".join(groups)


def _toc(page: Page) -> str:
    items = [h for h in page.headings if h.level in (2, 3)]
    if len(items) < 2:
        return ""
    lis = "".join('<li class="l%d"><a href="#%s">%s</a></li>' % (h.level, E(h.id), E(h.text)) for h in items)
    return ('<nav class="dx-toc" aria-label="On this page"><p class="dx-toc-title">On this page</p><ul>%s</ul></nav>'
            % lis)


def _pager(site: Site, page: Page) -> str:
    prev, nxt = site.neighbours(page)
    cell = lambda p, label, cls: ('<a class="dx-pager-link %s" href="%s"><span>%s</span><strong>%s</strong></a>'  # noqa: E731
                                  % (cls, E(p.url), label, E(p.nav_title))) if p else "<span></span>"
    return '<nav class="dx-pager" aria-label="Previous and next page">%s%s</nav>' % (
        cell(prev, "Previous", "prev"), cell(nxt, "Next", "next"))


def _json_ld(data: Dict) -> str:
    """A JSON-LD block. It is data, never executed (the CSP's script-src does not apply to it); '<', '>' and '&' are
    escaped so no page text can close the element early."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    text = text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return '<script type="application/ld+json">%s</script>' % text


def page_shell(site: Site, *, title: str, description: str, canonical: Optional[str], public_url: str, body: str,
               current: Optional[Page] = None, toc: str = "", robots: str = "index,follow",
               social_title: Optional[str] = None, og_type: str = "article", structured: Optional[Dict] = None) -> str:
    """The HTML around every docs page. `title` is the full <title>. Pages that must not be indexed (search
    results, not found) pass robots="noindex,..." and no canonical URL."""
    image = public_url + SOCIAL_CARD
    canonical_tags = ('<link rel="canonical" href="{0}">\n<meta property="og:url" content="{0}">\n'.format(E(canonical))
                      if canonical else "")
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="referrer" content="no-referrer">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="robots" content="{robots}">
{canonical_tags}<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{site_name}">
<meta property="og:locale" content="en_US">
<meta property="og:title" content="{social_title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{image_alt}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@InvarisLabs">
<meta name="twitter:title" content="{social_title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{image}">
<meta name="twitter:image:alt" content="{image_alt}">
<meta name="generator" content="AgentSec dashboard {version}">
<link rel="icon" href="/static/mark.svg" type="image/svg+xml">
<link rel="preload" href="/static/fonts/ibm-plex-sans-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/static/app.css">
<link rel="stylesheet" href="/static/docs.css">
<script src="/static/theme.js"></script>
<script src="/static/docs.js" defer></script>
{structured}
</head>
<body class="dx">
<a class="dx-skip" href="#content">Skip to content</a>
<header class="dx-top">
  <button class="icon-btn dx-menu" id="dx-menu" type="button" aria-controls="dx-sidebar" aria-expanded="false" aria-label="Open navigation">
    <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
  </button>
  <a class="brand" href="/docs"><img src="/static/mark.svg" alt="" width="22" height="22"><span>AgentSec</span><span class="dx-badge">Docs</span></a>
  <form class="dx-search" action="/docs/search" method="get" role="search">
    <label class="dx-search-box">{icon_search}<input id="dx-q" type="search" name="q" placeholder="Search the docs" aria-label="Search the documentation" role="combobox" aria-autocomplete="list" aria-controls="dx-results" aria-expanded="false" autocomplete="off" spellcheck="false"><kbd class="dx-search-key">/</kbd></label>
    <div class="dx-results" id="dx-results" role="listbox" aria-label="Search results" hidden></div>
  </form>
  <nav class="dx-toplinks" aria-label="Site">
    <a class="dx-toplink" href="/">Dashboard</a>
    <a class="icon-btn" href="{engine_repo}" rel="noopener noreferrer" title="AgentSec on GitHub" aria-label="AgentSec on GitHub">{icon_github}</a>
    <button class="icon-btn" id="theme" type="button" title="Switch theme" aria-label="Switch theme">{icon_theme}</button>
  </nav>
</header>
<div class="dx-layout">
  <aside class="dx-sidebar" id="dx-sidebar" aria-label="Documentation">
    <nav>{sidebar}</nav>
    <div class="dx-side-foot"><a href="/">Open the dashboard</a><a href="{engine_repo}" rel="noopener noreferrer">AgentSec engine on GitHub</a><a href="{dash_repo}" rel="noopener noreferrer">Dashboard on GitHub</a><a href="{website}" rel="noopener noreferrer">Invaris Labs website</a></div>
  </aside>
  <div class="dx-scrim" id="dx-scrim" hidden></div>
  <main class="dx-main" id="content" tabindex="-1">
    {body}
  </main>
  {toc}
</div>
</body>
</html>
""".format(title=E(title), desc=E(description), robots=E(robots), canonical_tags=canonical_tags, og_type=E(og_type),
           site_name=E(SITE_NAME), social_title=E(social_title or title), image=E(image), image_alt=E(SOCIAL_CARD_ALT),
           structured=_json_ld(structured) if structured else "", version=E(__version__),
           icon_search=ICON_SEARCH, icon_theme=ICON_THEME, icon_github=ICON_GITHUB, engine_repo=E(ENGINE_REPO),
           dash_repo=E(DASHBOARD_REPO), website=E(WEBSITE), sidebar=_sidebar(site, current), body=body, toc=toc)


def _crumbs(site: Site, page: Page) -> List[Tuple[str, Optional[str]]]:
    """(name, url) from the docs home to the page's section. The section links to its first page, unless that is
    this page or the docs home itself."""
    trail: List[Tuple[str, Optional[str]]] = [("Docs", "/docs")]
    home = site.section_home(page.section)
    if home is not None and home.slug and home is not page:
        trail.append((SECTION_TITLES[page.section], home.url))
    elif page.slug:
        trail.append((SECTION_TITLES[page.section], None))
    return trail


def _organization(public_url: str) -> Dict:
    return {"@type": "Organization", "@id": WEBSITE + "#organization", "name": "Invaris Labs", "url": WEBSITE,
            "sameAs": ORG_PROFILES}


def _website(public_url: str) -> Dict:
    return {"@type": "WebSite", "@id": public_url + "/docs#website", "url": public_url + "/docs", "name": SITE_NAME,
            "description": "Documentation for AgentSec, open-source security testing for AI agents, and its dashboard.",
            "inLanguage": "en", "publisher": {"@id": WEBSITE + "#organization"}}


def _software(public_url: str) -> Dict:
    """AgentSec, the engine these docs describe. Only facts the project states: open source (Apache-2.0), free,
    a Python package on PyPI."""
    app = {"@type": "SoftwareApplication", "@id": public_url + "/docs#agentsec", "name": "AgentSec",
           "alternateName": "Invaris AgentSec",
           "description": ("Open-source security testing for AI agents: adversarial scenarios such as prompt injection, "
                           "tool misuse, data leaks and memory poisoning, checked against a policy you write."),
           "applicationCategory": "DeveloperApplication", "applicationSubCategory": "Security testing",
           "operatingSystem": "Any (Python 3.9 or newer)", "url": public_url + "/docs",
           "downloadUrl": ENGINE_PACKAGE, "license": "https://www.apache.org/licenses/LICENSE-2.0",
           "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
           "sameAs": [ENGINE_REPO, ENGINE_PACKAGE], "publisher": {"@id": WEBSITE + "#organization"}}
    version = _engine_version()
    if version:
        app["softwareVersion"] = version
    return app


def _engine_version() -> str:
    try:
        from agentsec import __version__ as engine_version
    except Exception:  # noqa: BLE001 - structured data is optional; never let it break a page
        return ""
    return str(engine_version)


def structured_data(site: Site, page: Page, public_url: str) -> Dict:
    """JSON-LD for a page: the organization and docs site everywhere, the AgentSec application on the docs home,
    and a TechArticle with its breadcrumb trail on every other page."""
    graph: List[Dict] = [_organization(public_url), _website(public_url)]
    url = public_url + page.url
    if not page.slug:
        graph.append(_software(public_url))
        graph.append({"@type": "WebPage", "@id": url + "#webpage", "url": url, "name": page.social_title,
                      "description": page.meta_description, "isPartOf": {"@id": public_url + "/docs#website"},
                      "about": {"@id": public_url + "/docs#agentsec"}, "inLanguage": "en"})
        return {"@context": "https://schema.org", "@graph": graph}
    trail = [(name, href) for name, href in _crumbs(site, page) if href] + [(page.title, page.url)]
    graph.append({"@type": "BreadcrumbList", "@id": url + "#breadcrumb", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": name, "item": public_url + href}
        for i, (name, href) in enumerate(trail, 1)]})
    graph.append({"@type": "TechArticle", "@id": url + "#article", "headline": page.social_title[:110],
                  "description": page.meta_description, "url": url, "mainEntityOfPage": url, "inLanguage": "en",
                  "articleSection": SECTION_TITLES[page.section], "image": public_url + SOCIAL_CARD,
                  "isPartOf": {"@id": public_url + "/docs#website"}, "breadcrumb": {"@id": url + "#breadcrumb"},
                  "author": {"@id": WEBSITE + "#organization"}, "publisher": {"@id": WEBSITE + "#organization"},
                  "about": {"@type": "SoftwareApplication", "@id": public_url + "/docs#agentsec", "name": "AgentSec"}})
    return {"@context": "https://schema.org", "@graph": graph}


def render_page(site: Site, page: Page, public_url: str) -> str:
    links = []
    for name, href in _crumbs(site, page):
        links.append('<a href="%s">%s</a>' % (E(href), E(name)) if href else "<span>%s</span>" % E(name))
    crumbs = '<nav class="dx-crumbs" aria-label="Breadcrumb">%s</nav>' % '<span aria-hidden="true">/</span>'.join(links)
    body = ('<article class="dx-article">%s<h1>%s</h1><p class="dx-lead">%s</p><div class="dx-prose">%s</div>'
            '<footer class="dx-page-foot"><a class="ext" href="%s" rel="noopener noreferrer">Edit this page on GitHub</a>'
            '</footer>%s</article>') % (
        crumbs, E(page.title), E(page.description), page.html, E(EDIT_BASE + page.path), _pager(site, page))
    return page_shell(site, title=page.head_title, description=page.meta_description,
                      canonical=public_url + page.url, public_url=public_url, body=body, current=page, toc=_toc(page),
                      social_title=page.social_title, og_type="website" if not page.slug else "article",
                      structured=structured_data(site, page, public_url))


def render_search(site: Site, query: str, public_url: str) -> str:
    results = search(site, query) if query.strip() else []
    if not query.strip():
        inner = "<p>Type what you are looking for in the search box above.</p>"
    elif not results:
        inner = "<p>Nothing matches <strong>%s</strong>. Try a shorter or different word, or browse the sections " \
                "in the sidebar.</p>" % E(query)
    else:
        inner = '<ol class="dx-search-page">%s</ol>' % "".join(
            '<li><a href="%s"><strong>%s</strong><span class="dx-r-path">%s · %s</span></a><p>%s</p></li>' % (
                E(r["url"]), E(r["heading"] or r["page"]), E(r["section"]), E(r["page"]), E(snippet(r["text"], query)))
            for r in results)
    body = ('<article class="dx-article"><h1>Search</h1><p class="dx-lead">%s</p><div class="dx-prose">%s</div>'
            '</article>') % ("Results for “%s”" % E(query) if query.strip() else "Search the documentation", inner)
    return page_shell(site, title="Search" + TITLE_SUFFIX, description="Search the AgentSec documentation.",
                      canonical=None, public_url=public_url, body=body, robots="noindex,follow", og_type="website")


def render_not_found(site: Site, public_url: str) -> str:
    body = ('<article class="dx-article"><h1>Page not found</h1><p class="dx-lead">There is no documentation page at '
            'this address. It may have moved.</p><div class="dx-prose"><p>Search above, or start from the '
            '<a href="/docs">documentation home</a>.</p></div></article>')
    return page_shell(site, title="Page not found" + TITLE_SUFFIX, description="This documentation page does not exist.",
                      canonical=None, public_url=public_url, body=body, robots="noindex,follow", og_type="website")


def sitemap(site: Site, public_url: str) -> str:
    urls = "".join("<url><loc>%s</loc></url>" % E(public_url + p.url) for p in site.pages)
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s' \
           '</urlset>\n' % urls


def robots_txt(public_url: str) -> str:
    """robots.txt for the whole site. The docs are open to crawlers; the signed-in API, sign-in flow, health check
    and the docs' own search results and search index are not (they hold no content of their own)."""
    return ("User-agent: *\n"
            "Allow: /\n"
            "Disallow: /api/\n"
            "Disallow: /auth/\n"
            "Disallow: /healthz\n"
            "Disallow: /docs/search\n"
            "Disallow: /docs/search-index.json\n"
            "\n"
            "Sitemap: %s/docs/sitemap.xml\n" % public_url)


def search_index_json(site: Site) -> str:
    return json.dumps({"version": __version__, "entries": site.search_index()}, ensure_ascii=False,
                      separators=(",", ":"))


__all__ = ["DocsError", "Page", "SECTIONS", "Site", "get_site", "load_site", "render_not_found", "render_page",
           "render_search", "robots_txt", "search", "search_index_json", "sitemap", "structured_data"]
