"""The documentation at /docs: every page renders, links resolve, and the reference pages cover what the code does.

These tests treat the implementation as the source of truth. When the engine gains a CLI option, policy key or
finding rule, or the dashboard gains a route or setting, a test here fails until the documentation describes it.
"""
import argparse
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
    for page in SITE.pages:
        body = client.get(page.url).text
        assert ' style="' not in body, page.url
        scripts = re.findall(r"<script([^>]*)>", body)
        assert scripts and all('src="/static/' in s for s in scripts), page.url
        assert "<script>" not in body.replace("&lt;script&gt;", "")


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
    for asset in ("docs.css", "docs.js", "theme.js"):
        assert (app_dir / "static" / asset).resolve() in packaged


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
