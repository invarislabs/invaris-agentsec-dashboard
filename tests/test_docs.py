"""The documentation at /docs: every page renders, links resolve, and the reference pages cover what the code does.

These tests treat the implementation as the source of truth. When the engine gains a CLI option, policy key or
finding rule, or the dashboard gains a route or setting, a test here fails until the documentation describes it.
"""
import argparse
import json
import re
from pathlib import Path

import pytest

from app import __version__ as dashboard_version
from app.docs import markdown, site as docs_site
from app.docs.site import CONTENT, SECTIONS, STOPWORDS, load_site, search

from tests.conftest import ORIGIN

ROOT = Path(__file__).resolve().parent.parent
SITE = load_site(strict=True)     # CI must fail on any malformed page, even though production would skip it


def source(slug):
    return (Path(CONTENT) / (SITE.by_slug[slug].path)).read_text(encoding="utf-8")


# ----------------------------------------------------------------------------------------------- pages


def test_every_page_renders_with_metadata(client):
    assert len(SITE.pages) >= 40
    for page in SITE.pages:
        r = client.get(page.url)
        assert r.status_code == 200, page.url
        body = r.text
        assert "<title>" in body and '<meta name="description"' in body, page.url
        assert '<link rel="canonical" href="%s%s">' % (ORIGIN, page.url) in body, page.url
        assert '<meta property="og:title"' in body, page.url
        assert body.count("<h1>") == 1, page.url
        assert r.headers["content-security-policy"].startswith("default-src 'none'")


def test_docs_are_public_and_linked_from_the_dashboard(client):
    assert client.get("/docs").status_code == 200          # no sign-in needed
    index = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'href="/docs"' in index


def test_every_section_has_pages_and_the_sidebar_lists_them(client):
    html = client.get("/docs").text
    for key, title in SECTIONS:
        assert any(p.section == key for p in SITE.pages), key
        assert ">%s</h2>" % title in html
    for page in SITE.pages:
        assert 'href="%s"' % page.url in html


def test_unknown_pages_and_trailing_slashes(client):
    r = client.get("/docs/no/such/page")
    assert r.status_code == 404 and "Page not found" in r.text
    r = client.get("/docs/testing/cli/", follow_redirects=False)
    assert r.status_code == 308 and r.headers["location"] == "/docs/testing/cli"


def test_pages_are_compatible_with_the_content_security_policy(client):
    """Every script that runs comes from /static/. The only inline <script> is JSON-LD, which browsers never execute
    (script-src does not apply to it), and it cannot contain anything that would end the element early."""
    for page in SITE.pages:
        body = client.get(page.url).text
        assert ' style="' not in body, page.url
        scripts = re.findall(r"<script([^>]*)>", body)
        assert any('src="/static/' in s for s in scripts), page.url
        assert all('src="/static/' in s or s == ' type="application/ld+json"' for s in scripts), page.url
        assert "<script>" not in body.replace("&lt;script&gt;", "")
        for data in re.findall(r'<script type="application/ld\+json">(.*?)</script>', body, re.S):
            assert "<" not in data and ">" not in data, page.url


# ----------------------------------------------------------------------------------------------- links


def test_internal_links_and_anchors_resolve():
    ids = {p.url: {h.id for h in p.headings} for p in SITE.pages}
    problems = []
    for page in SITE.pages:
        for link in page.links:
            if link.startswith("http"):
                continue
            path, _, anchor = link.partition("#")
            target = path or page.url
            if target not in ids:
                problems.append("%s -> %s (no such page)" % (page.url, link))
            elif anchor and anchor not in ids[target]:
                problems.append("%s -> %s (no such anchor)" % (page.url, link))
    assert not problems, "\n".join(problems)


def test_external_links_point_at_the_project_or_known_references():
    allowed = ("https://github.com/invarislabs/", "https://genai.owasp.org/", "https://modelcontextprotocol.io")
    for page in SITE.pages:
        for link in page.links:
            if link.startswith("http"):
                assert link.startswith(allowed), (page.url, link)


# ----------------------------------------------------------------------------------------------- search, SEO


def test_search_index_covers_every_page(client):
    data = client.get("/docs/search-index.json").json()
    urls = {e["url"].split("#")[0] for e in data["entries"]}
    assert urls == {p.url for p in SITE.pages}
    assert all(e["page"] and e["section"] for e in data["entries"])


def test_server_side_search(client):
    hits = search(SITE, "inconclusive")
    assert hits and any("/docs/results/verdicts" in h["url"] for h in hits)
    r = client.get("/docs/search", params={"q": "upload token"})
    assert r.status_code == 200 and "/docs/guide/projects-and-tokens" in r.text and "noindex" in r.text
    r = client.get("/docs/search", params={"q": "zzzz-nothing-matches"})
    assert "Nothing matches" in r.text


def test_sitemap_lists_every_page(client):
    r = client.get("/docs/sitemap.xml")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    for page in SITE.pages:
        assert "<loc>%s%s</loc>" % (ORIGIN, page.url) in r.text
    assert r.text.count("<loc>") == len(SITE.pages)                 # nothing else: no search pages, no duplicates
    assert client.get("/sitemap.xml").text == r.text                # the conventional root address serves it too


def _head(html):
    return html.split("</head>", 1)[0]


def _meta(html, attr, name):
    m = re.search(r'<meta %s="%s" content="([^"]*)">' % (attr, re.escape(name)), _head(html))
    return m.group(1) if m else None


def _json_ld(html):
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert len(blocks) == 1
    return json.loads(blocks[0])


def test_titles_and_descriptions_are_unique_and_fit_search_results(client):
    """Search engines cut titles at about 60 characters and descriptions at about 160; duplicates compete with each
    other. Every page has its own, within the limits page authors are given (see developers/writing-docs)."""
    titles, descriptions = {}, {}
    for page in SITE.pages:
        html = client.get(page.url).text
        title = re.search(r"<title>(.*?)</title>", html).group(1)
        desc = _meta(html, "name", "description")
        assert 10 <= len(title) <= 70, (page.url, title)
        assert 50 <= len(desc) <= 170, (page.url, desc)               # escaped HTML: a little longer than the text
        assert title not in titles, (page.url, titles.get(title))
        assert desc not in descriptions, (page.url, descriptions.get(desc))
        titles[title], descriptions[desc] = page.url, page.url
        assert _meta(html, "property", "og:title") and _meta(html, "property", "og:description") == desc
    home = client.get("/docs").text
    assert "AI Agent Security Testing" in re.search(r"<title>(.*?)</title>", home).group(1)


def test_seo_front_matter_is_validated(tmp_path):
    from app.docs.site import DocsError
    root = tmp_path / "content"
    root.mkdir()
    (root / "index.md").write_text("---\ntitle: Home\ndescription: d\nsection: start\nseo_title: %s\n---\nx\n"
                                   % ("x" * 66), encoding="utf-8")
    with pytest.raises(DocsError, match="seo_title"):
        load_site(str(root), strict=True)
    (root / "index.md").write_text("---\ntitle: Home\ndescription: d\nsection: start\nseo_description: %s\n---\nx\n"
                                   % ("x" * 166), encoding="utf-8")
    with pytest.raises(DocsError, match="seo_description"):
        load_site(str(root), strict=True)


def test_link_previews_use_the_social_card(client):
    import struct
    card = ROOT / "app" / "static" / "social-card.png"
    head = card.read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", head[16:24]) == (1200, 630)
    assert card.stat().st_size <= 150 * 1024
    assert client.get("/static/social-card.png").status_code == 200
    html = client.get("/docs/quickstart").text
    assert _meta(html, "property", "og:image") == ORIGIN + "/static/social-card.png"
    assert _meta(html, "name", "twitter:card") == "summary_large_image"
    assert _meta(html, "name", "twitter:image") == ORIGIN + "/static/social-card.png"
    assert _meta(html, "property", "og:url") == ORIGIN + "/docs/quickstart"
    assert _meta(html, "property", "og:type") == "article"
    assert _meta(client.get("/docs").text, "property", "og:type") == "website"


def test_structured_data(client):
    """JSON-LD on every page: the organization and site everywhere, the AgentSec application on the docs home, and
    a TechArticle with a breadcrumb trail ending at the page's own canonical URL everywhere else."""
    home = _json_ld(client.get("/docs").text)
    types = {n["@type"] for n in home["@graph"]}
    assert home["@context"] == "https://schema.org"
    assert {"Organization", "WebSite", "SoftwareApplication", "WebPage"} <= types
    app = next(n for n in home["@graph"] if n["@type"] == "SoftwareApplication")
    assert app["name"] == "AgentSec" and app["offers"]["price"] == "0" and "aggregateRating" not in app
    for page in SITE.pages:
        if not page.slug:
            continue
        data = _json_ld(client.get(page.url).text)
        nodes = {n["@type"]: n for n in data["@graph"]}
        article, crumbs = nodes["TechArticle"], nodes["BreadcrumbList"]["itemListElement"]
        assert article["url"] == ORIGIN + page.url and article["headline"] and len(article["headline"]) <= 110
        assert [c["position"] for c in crumbs] == list(range(1, len(crumbs) + 1))
        assert crumbs[0]["item"] == ORIGIN + "/docs" and crumbs[-1]["item"] == ORIGIN + page.url
        for c in crumbs:
            assert c["item"].startswith(ORIGIN + "/docs") and c["item"][len(ORIGIN):] in {p.url for p in SITE.pages}


def test_breadcrumbs_link_each_section_to_its_first_page(client):
    html = client.get("/docs/testing/mcp").text
    crumbs = re.search(r'<nav class="dx-crumbs" aria-label="Breadcrumb">(.*?)</nav>', html).group(1)
    assert '<a href="/docs">Docs</a>' in crumbs and '<a href="/docs/testing/overview">Testing guides</a>' in crumbs
    first = client.get("/docs/testing/overview").text      # a section's first page does not link to itself
    crumbs = re.search(r'<nav class="dx-crumbs" aria-label="Breadcrumb">(.*?)</nav>', first).group(1)
    assert 'href="/docs/testing/overview"' not in crumbs and "<span>Testing guides</span>" in crumbs


def test_pages_that_must_not_be_indexed(client):
    """Search results, the search index and missing pages stay out of search engines, and claim no canonical URL."""
    for path, status in (("/docs/search?q=token", 200), ("/docs/no/such/page", 404)):
        r = client.get(path)
        assert r.status_code == status and r.headers["x-robots-tag"] == "noindex", path
        assert '<meta name="robots" content="noindex,follow">' in r.text and 'rel="canonical"' not in r.text, path
    assert client.get("/docs/search-index.json").headers["x-robots-tag"] == "noindex"
    for page in SITE.pages:
        assert "x-robots-tag" not in client.get(page.url).headers, page.url


def test_robots_txt(client):
    r = client.get("/robots.txt")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    lines = r.text.splitlines()
    assert "Sitemap: %s/docs/sitemap.xml" % ORIGIN in lines
    assert {"Disallow: /api/", "Disallow: /auth/", "Disallow: /docs/search"} <= set(lines)
    disallowed = [l.split(":", 1)[1].strip() for l in lines if l.startswith("Disallow:")]
    for page in SITE.pages:                                       # no documentation page is blocked
        assert not any(page.url.startswith(d) for d in disallowed), page.url
    assert not any("/static/".startswith(d) for d in disallowed)  # crawlers need the CSS and fonts to render pages


# ----------------------------------------------------------------------------------------------- renderer


def test_markdown_is_escaped_and_links_are_restricted():
    out = markdown.render("Hello <script>alert(1)</script> & **bold** `<b>`").html
    assert "<script>" not in out and "&lt;script&gt;" in out and "<strong>bold</strong>" in out
    assert "<code>&lt;b&gt;</code>" in out
    with pytest.raises(ValueError):
        markdown.render("[x](javascript:alert(1))")
    with pytest.raises(ValueError):
        markdown.render("[x](relative/page)")


def test_markdown_features():
    text = "\n".join([
        "## Title {#custom}", "", "> [!WARNING] Careful", "> Body text.", "",
        "| a | b |", "|---|---:|", "| `x \\| y` | 2 |", "",
        "```yaml title=\"agentsec.yaml\"", "version: \"1\"  # comment", "```", "",
        "- one", "  - nested", "- two", "", ":::cards", "- [Docs](/docs): home", ":::", "",
        "{{status:inconclusive}} {{sev:high}} {{cell:passed}} {{kbd:Ctrl K}}",
    ])
    r = markdown.render(text)
    assert r.headings[0].id == "custom"
    assert 'class="dx-callout dx-warning"' in r.html and "Careful" in r.html
    assert "<code>x | y</code>" in r.html and 'class="num"' in r.html
    assert 'class="tk-key"' in r.html and 'class="tk-comment"' in r.html and "agentsec.yaml" in r.html
    assert "<ul><li>one<ul><li>nested</li></ul></li><li>two</li></ul>" in r.html
    assert 'class="dx-card"' in r.html
    assert 'class="status inconclusive"' in r.html and "<kbd>Ctrl</kbd> <kbd>K</kbd>" in r.html
    with pytest.raises(ValueError):
        markdown.render("{{status:maybe}}")
    with pytest.raises(ValueError):
        markdown.render("```bash\nunclosed")


def test_front_matter_is_required(tmp_path):
    from app.docs.site import DocsError
    (tmp_path / "bad.md").write_text("---\ntitle: x\n---\nbody\n", encoding="utf-8")
    with pytest.raises(DocsError, match="needs `description`"):
        load_site(str(tmp_path), strict=True)


# ----------------------------------------------------------------------------------------------- coverage of the implementation


def _subparsers(parser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                yield name, sub
                for nested, subsub in _subparsers(sub):
                    yield name + " " + nested, subsub


def test_cli_reference_documents_every_command_and_option():
    from agentsec.cli.main import build_parser
    doc = source("reference/cli")
    missing = []
    for name, sub in _subparsers(build_parser()):
        if name == "mcp":
            continue          # only a group: `agentsec mcp scan` is documented
        if "agentsec %s" % name not in doc:
            missing.append("command agentsec %s" % name)
        for action in sub._actions:
            if isinstance(action, argparse._HelpAction):
                continue
            for opt in action.option_strings:
                if "`%s" % opt not in doc:
                    missing.append("agentsec %s %s" % (name, opt))
    assert not missing, "document these in reference/cli.md:\n" + "\n".join(missing)


def _schema_keys(node):
    """Every property name in a JSON Schema, at any depth (the policy schema `agentsec schema policy` prints)."""
    keys = set()
    if isinstance(node, dict):
        for k, v in (node.get("properties") or {}).items():
            keys.add(k)
            keys |= _schema_keys(v)
        for k in ("additionalProperties", "items"):
            keys |= _schema_keys(node.get(k))
        for k in ("$defs", "definitions"):
            for v in (node.get(k) or {}).values():
                keys |= _schema_keys(v)
        for k in ("anyOf", "oneOf", "allOf"):
            for v in node.get(k) or []:
                keys |= _schema_keys(v)
    return keys


def test_policy_reference_documents_every_key():
    from agentsec.policies import policy_json_schema
    keys = _schema_keys(policy_json_schema())
    doc = source("reference/policy")
    missing = sorted(k for k in keys if "`%s`" % k not in doc)
    assert len(keys) > 30 and not missing, "document these policy keys in reference/policy.md: %s" % missing


def test_policy_examples_in_the_docs_load():
    from agentsec.policies import parse_policy
    checked = 0
    for page in SITE.pages:
        text = source(page.slug)
        for title, body in re.findall(r'```yaml(?: title="([^"]*)")?\n(.*?)\n```', text, re.S):
            if re.search(r"^agent:", body, re.M) and ("agentsec.yaml" in (title or "") or "version:" in body):
                parse_policy(body)
                checked += 1
    assert checked >= 3


def test_api_reference_documents_every_route():
    from app.main import create_app
    norm = lambda s: re.sub(r"\{[^}]+\}", "{}", s)  # noqa: E731  {report_id} in code, {id} in the docs
    doc = norm(source("reference/api"))
    missing = []
    for route in create_app().routes:
        path = getattr(route, "path", "")
        if path.startswith(("/api", "/auth", "/healthz")):
            if norm(path) not in doc:
                missing.append(path)
    assert not missing, "document these routes in reference/api.md: %s" % missing


def test_configuration_reference_documents_every_setting():
    doc = source("reference/configuration")
    config = (ROOT / "app" / "config.py").read_text(encoding="utf-8")
    names = set(re.findall(r'(?:environ\.get|_bool|_int)\("([A-Z_]+)"', config))
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    names |= set(re.findall(r"^#?\s*([A-Z][A-Z_]+)=", example, re.M))
    missing = sorted(n for n in names if "`%s`" % n not in doc)
    assert names and not missing, "document these settings in reference/configuration.md: %s" % missing


def test_rules_reference_documents_every_rule():
    owasp = pytest.importorskip("agentsec.owasp")
    rules = getattr(owasp, "_BY_RULE", None)
    if not rules:
        pytest.skip("this AgentSec build does not expose its rule mapping")
    doc = source("reference/rules")
    missing = sorted(r for r in rules if "`%s`" % r not in doc)
    assert not missing, "document these rules in reference/rules.md: %s" % missing


def test_attack_catalog_documents_every_builtin_category():
    from agentsec.attacks import CATEGORIES
    doc = source("reference/attack-catalog")
    missing = sorted(c for c in CATEGORIES if "`%s`" % c not in doc)
    assert not missing, "document these categories in reference/attack-catalog.md: %s" % missing


# ----------------------------------------------------------------------------------------------- production safety


@pytest.fixture
def broken_docs(tmp_path, monkeypatch):
    """A copy of the docs with one malformed page, served by the app the way production would load it."""
    import shutil
    root = tmp_path / "content"
    shutil.copytree(CONTENT, root)
    (root / "testing" / "broken.md").write_text("---\ntitle: Broken\n---\n```bash\nnever closed\n", encoding="utf-8")
    monkeypatch.setattr(docs_site, "CONTENT", str(root))
    docs_site.get_site.cache_clear()
    docs_site.search_index_gzip.cache_clear()
    yield root
    docs_site.get_site.cache_clear()
    docs_site.search_index_gzip.cache_clear()


def test_a_malformed_page_never_stops_the_dashboard(broken_docs, make_client, caplog):
    import logging
    logging.getLogger("app.docs").disabled = False     # an earlier test's logging.config call may have disabled it
    with caplog.at_level("ERROR", logger="app.docs"):
        client = make_client()                       # create_app() loads the docs: it must not raise
    assert client.get("/healthz").json() == {"ok": True}
    assert client.get("/").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/docs/testing/cli").status_code == 200
    assert client.get("/docs/testing/broken").status_code == 404
    assert any("testing/broken.md" in r.getMessage() for r in caplog.records)
    assert docs_site.get_site().errors and len(docs_site.get_site().pages) == len(SITE.pages)


def test_strict_loading_fails_on_a_malformed_page(broken_docs):
    from app.docs.site import DocsError
    with pytest.raises(DocsError, match="broken.md"):
        load_site(str(broken_docs), strict=True)
    assert load_site(str(broken_docs)).errors


def test_docs_never_set_cookies_even_for_signed_in_users(client):
    """Docs responses may be kept by shared caches (Cache-Control: public), so they must never carry a session."""
    from tests.conftest import sign_in
    sign_in(client)
    for path in ("/docs", "/docs/testing/cli", "/docs/search-index.json", "/docs/sitemap.xml", "/docs/search?q=token"):
        r = client.get(path)
        assert r.status_code == 200 and "set-cookie" not in r.headers, path
    assert "set-cookie" not in client.get("/docs/nope").headers


def test_search_index_is_compressed_when_accepted(client):
    import gzip
    import json
    r = client.get("/docs/search-index.json", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip" and r.headers["vary"] == "Accept-Encoding"
    assert len(r.json()["entries"]) > 200                     # httpx decompressed it
    raw = client.get("/docs/search-index.json", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in raw.headers and json.loads(raw.content)["entries"] == r.json()["entries"]
    assert len(gzip.compress(raw.content)) < len(raw.content) / 2


def test_unsafe_links_are_refused():
    for bad in ("//evil.example/x", "http://example.com", "javascript:alert(1)", "data:text/html,x", "../x"):
        with pytest.raises(ValueError):
            markdown.render("[x](%s)" % bad)
        with pytest.raises(ValueError):
            markdown.render(":::cards\n- [x](%s): y\n:::" % bad)


def test_every_page_is_packaged():
    """pyproject's package-data must ship every page, so the Docker image (pip install .) serves all of them."""
    import glob
    import tomllib
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = data["tool"]["setuptools"]["package-data"]["app"]
    app_dir = ROOT / "app"
    packaged = {Path(p).resolve() for pat in patterns for p in glob.glob(str(app_dir / pat), recursive=True)}
    pages = {p.resolve() for p in Path(CONTENT).rglob("*.md")}
    assert pages and pages <= packaged
    for asset in ("docs.css", "docs.js", "theme.js", "social-card.png"):
        assert (app_dir / "static" / asset).resolve() in packaged
    pictures = {p.resolve() for d in ("images", "diagrams") for p in (app_dir / "docs" / d).iterdir()}
    assert pictures and pictures <= packaged


# ----------------------------------------------------------------------------------------------- dashboard <-> docs


def test_links_from_the_dashboard_to_the_docs_resolve():
    ids = {p.url: {h.id for h in p.headings} for p in SITE.pages}
    js = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    links = ["/docs/" + m for m in re.findall(r'docLink\("([^"]+)"', js)]
    links += [u for u in re.findall(r'href: "(/docs[^"]*)"', js) if u != "/docs/"]   # "/docs/" + path: the helper
    links += re.findall(r'href="(/docs[^"]*)"', html)
    assert len(links) >= 15
    for link in links:
        path, _, anchor = link.partition("#")
        assert path in ids, link
        assert not anchor or anchor in ids[path], link


def test_search_stop_words_match_the_browser_implementation():
    js = (ROOT / "app" / "static" / "docs.js").read_text(encoding="utf-8")
    words = re.search(r'var STOP = \(([^;]+)\)\.split', js).group(1)
    assert set("".join(re.findall(r'"([^"]*)"', words)).split()) == set(STOPWORDS)


@pytest.mark.parametrize("query,expected", [
    ("how do I upload a report", "/docs/testing/upload"),
    ("what does inconclusive mean", "/docs/reference/glossary#inconclusive"),
    ("dark mode", "/docs/guide/dashboard-tour"),
    ("exit codes", "/docs/reference/cli#exit-codes"),
    ("scripted stand-in", "/docs/reference/glossary#scripted-stand-in"),
    ("x_agentsec", "/docs/testing/agent-contract"),
])
def test_search_finds_the_right_page_for_common_questions(query, expected):
    urls = [h["url"] for h in search(SITE, query, limit=5)]
    assert any(u.startswith(expected) for u in urls), (query, urls)


def test_docs_name_the_engine_and_dashboard_versions_they_describe():
    """The docs describe the engine version the dashboard is built and tested with (Dockerfile, CI)."""
    pinned = re.search(r'AGENTSEC_REQUIREMENT="invaris-agentsec==([0-9.]+)"',
                       (ROOT / "Dockerfile").read_text(encoding="utf-8")).group(1)
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "invaris-agentsec==%s" % pinned in ci
    intro = source("")
    assert "AgentSec %s" % pinned in intro and "dashboard %s" % dashboard_version in intro


# ----------------------------------------------------------------------------------------------- screenshots and diagrams

def _used(kind):
    return {f.split(":", 1)[1] for p in SITE.pages for f in p.figures if f.startswith(kind + ":")}


def test_every_picture_exists_in_both_themes_and_is_used():
    """Each screenshot is a light and dark pair of the same size; no picture is shipped without a page using it."""
    shots = {name.rsplit("-", 1)[0] for name in SITE.assets.images}
    assert shots and shots == _used("figure")
    assert set(SITE.assets.diagrams) and set(SITE.assets.diagrams) == _used("diagram")
    for name in shots:
        light, dark = SITE.assets.screenshot(name)
        assert (light.width, light.height) == (dark.width, dark.height), name


def test_pictures_stay_small():
    """WebP, at most 1600 pixels wide (twice the docs column) and small enough not to slow pages down."""
    total = 0
    for img in SITE.assets.images.values():
        size = Path(img.path).stat().st_size
        total += size
        assert img.width <= 1600 and size <= 200 * 1024, img.file
    assert total <= 6 * 1024 * 1024
    for name, svg in SITE.assets.diagrams.items():
        assert len(svg) <= 30 * 1024, name


def test_pictures_are_described_and_captioned(client):
    """Every screenshot and diagram has a text alternative and a caption; the hidden theme's picture is lazy-loaded."""
    seen = 0
    for page in SITE.pages:
        if not page.figures:
            continue
        html = client.get(page.url).text
        for fig in re.findall(r'<figure class="dx-figure[^"]*">(.*?)</figure>', html, re.S):
            seen += 1
            assert "<figcaption>" in fig and re.search(r"<figcaption>\s*\S", fig), page.url
            for alt in re.findall(r'<img [^>]*alt="([^"]*)"', fig) + re.findall(r'role="img" aria-label="([^"]*)"', fig):
                assert len(alt) >= 12, page.url
            for img in re.findall(r"<img [^>]*>", fig):
                assert 'loading="lazy"' in img and 'width="' in img and 'height="' in img, page.url
    assert seen == sum(len(p.figures) for p in SITE.pages)


def test_pictures_are_served_with_long_caching_and_nothing_else_is(client):
    page = client.get("/docs/guide/run-overview").text
    url = re.search(r'src="(/docs/img/[a-z0-9-]+-light\.webp\?v=[0-9a-f]+)"', page).group(1)
    r = client.get(url)
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp"
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert "set-cookie" not in r.headers and r.content[:4] == b"RIFF"
    assert client.get(url.split("?")[0]).headers["cache-control"] == "public, max-age=300"   # no version: brief
    for bad in ("/docs/img/nope-light.webp", "/docs/img/..%2Fsite.py", "/docs/img/%2E%2E%2F%2E%2E%2Fconfig.py",
                "/docs/img/run-verdict-light.png"):
        assert client.get(bad).status_code == 404, bad


def test_unsafe_diagrams_are_refused():
    from app.docs.assets import clean_svg
    ok = '<svg viewBox="0 0 10 10"><path class="d-line" d="M0,0 H5" marker-end="url(#x-a)"/></svg>'
    assert clean_svg(ok, "x").startswith('<svg aria-hidden="true"')
    for bad in ('<svg viewBox="0 0 1 1"><script>alert(1)</script></svg>',
                '<svg viewBox="0 0 1 1" onload="alert(1)"></svg>',
                '<svg viewBox="0 0 1 1"><rect style="fill:red"/></svg>',
                '<svg viewBox="0 0 1 1"><a href="https://evil.example"><text>x</text></a></svg>',
                '<svg viewBox="0 0 1 1"><image href="x.png"/></svg>',
                '<svg viewBox="0 0 1 1"><foreignObject>x</foreignObject></svg>',
                '<svg viewBox="0 0 1 1"><rect fill="url(https://evil.example/x)"/></svg>',
                '<svg><rect/></svg>', '<div></div>'):
        with pytest.raises(ValueError):
            clean_svg(bad, "bad")


def test_figure_blocks_need_alt_text_a_caption_and_a_known_picture():
    assets = SITE.assets
    name = sorted(_used("figure"))[0]
    ok = markdown.render(":::figure %s\nalt: What the picture shows, in words.\nThe caption.\n:::" % name, assets)
    assert 'class="dx-light"' in ok.html and 'class="dx-dark"' in ok.html and ok.figures == ["figure:" + name]
    for bad in (":::figure %s\nThe caption only.\n:::" % name,                   # no alt line
                ":::figure %s\nalt: short\nCaption.\n:::" % name,               # alt too short to describe anything
                ":::figure %s\nalt: What the picture shows, in words.\n:::" % name,   # no caption
                ":::figure %s\nalt: What the picture shows, in words.\nCaption." % name,  # never closed
                ":::figure no-such-shot\nalt: What the picture shows, in words.\nCaption.\n:::",
                ":::diagram no-such-diagram\nalt: What the picture shows, in words.\nCaption.\n:::",
                ":::picture x\nalt: What the picture shows, in words.\nCaption.\n:::"):
        with pytest.raises(ValueError):
            markdown.render(bad, assets)


def test_a_missing_picture_never_takes_its_page_down(tmp_path):
    """Production keeps the page and shows the caption without the picture; strict loading (CI) refuses it."""
    import shutil
    from app.docs.site import DocsError
    root, images = tmp_path / "content", tmp_path / "images"
    shutil.copytree(CONTENT, root)
    shutil.copytree(docs_site.IMAGES, images)
    victim = sorted(_used("figure"))[0]
    (images / (victim + "-dark.webp")).unlink()
    (images / "Not A Valid Name.webp").write_bytes(b"x")
    site = load_site(str(root), images=str(images))
    assert len(site.pages) == len(SITE.pages)
    assert any(victim in e for e in site.errors) and any("Not A Valid Name" in e for e in site.errors)
    page = next(p for p in site.pages if "figure:" + victim in p.figures)
    assert 'class="dx-figure dx-missing"' in page.html
    with pytest.raises(DocsError):
        load_site(str(root), strict=True, images=str(images))

