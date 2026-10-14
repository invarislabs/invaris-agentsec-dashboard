#!/usr/bin/env python3
"""Regenerate the screenshots used by the documentation (app/docs/images/*.webp).

Every screenshot shows the real dashboard displaying real AgentSec reports, produced fresh by this script:

- the engine's vulnerable reference agent and its hardened variant (the Quickstart), plus one run made while the
  agent was not running (every scenario errors);
- the email attack pack against the scripted stand-in assistants (tests/fixtures/generate_pack_fixtures.py);
- an MCP scan of the engine's poisoned demo server.

The dashboard runs from this checkout against a throwaway SQLite database with development sign-in; nothing is
sent anywhere else. Upload tokens created along the way are masked in the pictures and die with the database.

Requirements: the dashboard installed (`pip install -e ".[dev]"`), a checkout of the engine repository (for its
example agents), `pip install playwright pillow` and a Chromium for Playwright (`playwright install chromium`, or
set PLAYWRIGHT_CHROMIUM to a Chromium binary).

    python scripts/docs_screenshots.py --engine ../invaris-agentsec              # everything
    python scripts/docs_screenshots.py --engine ../invaris-agentsec run-overview  # some shots, by name
    python scripts/docs_screenshots.py --engine ../invaris-agentsec --serve       # set up, then keep it running

Ports 8000 (the reference agent, as in the Quickstart) and 8790 (the dashboard) must be free.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "app" / "docs" / "images"
DASH_PORT = 8790
DASH = "http://127.0.0.1:%d" % DASH_PORT
AGENT_PORT = 8000
WIDTH = 1280            # browser viewport for desktop shots
SCALE = 2               # device pixel ratio: sharp on high-density screens
MAX_WIDTH = 1600        # stored images are at most this wide (the docs column is 760 CSS px)
USER = "demo"


# --------------------------------------------------------------------------------------------- helpers

def log(*a):
    print("[docs-screenshots]", *a, flush=True)


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def wait_http(url: str, seconds: float = 30) -> None:
    end = time.time() + seconds
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception as exc:  # noqa: BLE001 - any answer, including an HTTP error, means it is up
            if hasattr(exc, "code"):
                return
            time.sleep(0.3)
    raise SystemExit("nothing answered at %s" % url)


def bin_env() -> dict:
    """An environment where `python` and `agentsec` are this interpreter's, as a user's shell would have."""
    env = dict(os.environ)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    env.pop("GITHUB_ACTIONS", None)       # no CI metadata in the reports
    return env


def run(cmd, cwd, ok=(0,), env=None) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, cwd=str(cwd), env=env or bin_env(), capture_output=True, text=True)
    if p.returncode not in ok:
        raise SystemExit("%s failed (%d):\n%s%s" % (" ".join(cmd), p.returncode, p.stdout, p.stderr))
    return p


class Server:
    def __init__(self, cmd, cwd, env=None, url=None):
        self.proc = subprocess.Popen(cmd, cwd=str(cwd), env=env or bin_env(),
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if url:
            wait_http(url)

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


# --------------------------------------------------------------------------------------------- reports

def make_reports(engine: Path, work: Path) -> dict:
    """Run AgentSec for real and return {name: report path}."""
    if not port_free(AGENT_PORT):
        raise SystemExit("port %d is in use; the reference agent needs it" % AGENT_PORT)
    policy = "examples/vulnerable_rag_agent/agentsec.yaml"
    out = {}
    existing = {"down": work / "down" / "report.json", "vulnerable": work / "vulnerable" / "report.json",
                "hardened": work / "hardened" / "report.json", "mcp": work / "mcp" / "mcp-report.json",
                "email-baseline": work / "packs" / "email-described-report.json",
                "email-hardened": work / "packs" / "email-hardened-report.json"}
    if all(p.exists() for p in existing.values()):
        log("reusing the reports in", work)
        return existing

    log("agentsec test: agent not running (every scenario errors)")
    run(["agentsec", "test", "-p", policy, "-s", "prompt_injection", "--out", str(work / "down")], engine, ok=(2,))
    out["down"] = work / "down" / "report.json"

    for name, extra, code in (("vulnerable", [], 1), ("hardened", ["--safe"], 0)):
        log("agentsec test: %s reference agent" % name)
        agent = Server([sys.executable, "examples/vulnerable_rag_agent/server.py"] + extra, engine,
                       url="http://127.0.0.1:%d/" % AGENT_PORT)
        try:
            run(["agentsec", "test", "-p", policy, "--out", str(work / name)], engine, ok=(code,))
        finally:
            agent.stop()
        out[name] = work / name / "report.json"

    log("agentsec mcp scan: poisoned demo server")
    run(["agentsec", "mcp", "scan", "--command", "python examples/mcp_servers/server.py --poisoned",
         "--out", str(work / "mcp")], engine, ok=(1,))
    out["mcp"] = work / "mcp" / "mcp-report.json"

    log("email attack pack: scripted stand-in assistants")
    sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
    import generate_pack_fixtures                                   # noqa: E402 - the fixture generator
    packs = work / "packs"
    packs.mkdir()
    generate_pack_fixtures.main(engine, packs, ("email-described-report.json", "email-hardened-report.json"))
    out["email-baseline"] = packs / "email-described-report.json"
    out["email-hardened"] = packs / "email-hardened-report.json"
    return out


# --------------------------------------------------------------------------------------------- dashboard

def start_dashboard(work: Path, port: int = DASH_PORT, github: bool = False) -> Server:
    """The dashboard from this checkout on a throwaway SQLite database. github=True: a server configured for GitHub
    sign-in only (the sign-in page as production shows it; the OAuth values are placeholders, never used)."""
    if not port_free(port):
        raise SystemExit("port %d is in use; the dashboard needs it" % port)
    base = "http://127.0.0.1:%d" % port
    env = bin_env()
    env.update({"AGENTSEC_ENV": "development", "AGENTSEC_DEV_LOGIN": "0" if github else "1",
                "DATABASE_URL": "sqlite:///%s" % (work / ("dashboard-%d.db" % port)), "PUBLIC_URL": base,
                "SECRET_KEY": "docs-screenshots-" + os.urandom(16).hex()})
    env["PUBLIC_URL"] = "https://agentsec.example.com"   # the address the pages print in commands
    if github:
        env.update({"GITHUB_CLIENT_ID": "docs-screenshot-placeholder", "GITHUB_CLIENT_SECRET": "placeholder"})
    db = work / ("dashboard-%d.db" % port)
    if db.exists():
        db.unlink()
    run([sys.executable, "-m", "alembic", "upgrade", "head"], ROOT, env=env)
    log("dashboard at", base)
    return Server([sys.executable, "-m", "uvicorn", "app.main:create_app", "--factory", "--port", str(port),
                   "--log-level", "warning"], ROOT, env=env, url=base + "/healthz")


def upload(report: Path, token: str, *extra: str) -> None:
    env = bin_env()
    env["AGENTSEC_TOKEN"] = token
    run(["agentsec", "upload", str(report), "--server", DASH] + list(extra), ROOT, env=env)


# --------------------------------------------------------------------------------------------- browser

def chromium(p):
    exe = os.environ.get("PLAYWRIGHT_CHROMIUM")
    if not exe and Path("/opt/pw-browsers/chromium").exists():
        exe = "/opt/pw-browsers/chromium"
    return p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()


def api(page, method: str, path: str, body=None):
    """Call the dashboard API as the signed-in page does (same origin, session cookie)."""
    return page.evaluate("""([m, u, b]) => fetch(u, {method: m, headers: {'Content-Type': 'application/json'},
        body: b === null ? undefined : JSON.stringify(b)}).then(r => r.status === 204 ? null : r.json())""",
                         [method, path, body])


def sign_in(page, base: str = DASH) -> None:
    page.goto(base + "/")
    page.fill("input[aria-label='Development username']", USER)
    page.click("form.devlogin button")
    page.wait_for_selector("h1:text('Projects')")


def populate(page, reports: dict) -> dict:
    """Create the projects and upload the runs. Returns ids of interesting runs."""
    tokens = {}
    have = {p["slug"] for p in api(page, "GET", "/api/projects", None)["projects"]}
    for name in ("support-agent", "email-assistant", "mcp-servers"):
        if name not in have:
            api(page, "POST", "/api/projects", {"name": name})
        tokens[name] = api(page, "POST", "/api/projects/%s/tokens" % name, {"name": "GitHub Actions"})["token"]
    log("uploading runs")
    upload(reports["down"], tokens["support-agent"], "--branch", "main")
    upload(reports["vulnerable"], tokens["support-agent"], "--branch", "main", "--label", "baseline")
    upload(reports["hardened"], tokens["support-agent"], "--branch", "harden-retrieval", "--label", "hardened")
    upload(reports["email-baseline"], tokens["email-assistant"], "--branch", "main", "--label", "baseline")
    upload(reports["email-hardened"], tokens["email-assistant"], "--branch", "main", "--label", "hardened")
    upload(reports["mcp"], tokens["mcp-servers"], "--label", "demo server, poisoned mode")
    ids = {}
    for slug in ("support-agent", "email-assistant", "mcp-servers"):
        for r in api(page, "GET", "/api/projects/%s/reports" % slug, None)["reports"]:
            ids[(slug, r.get("label") or ("down" if r.get("errors") else r["name"]))] = r["id"]
    return ids


# --------------------------------------------------------------------------------------------- capturing

class Shooter:
    """Takes each screenshot twice, in light and in dark mode, from two signed-in browser contexts."""

    def __init__(self, browser, only: set, base: str = DASH):
        self.only = only
        self.base = base
        self.pages = {}
        for theme in ("light", "dark"):
            ctx = browser.new_context(viewport={"width": WIDTH, "height": 800}, device_scale_factor=SCALE,
                                      color_scheme=theme, timezone_id="UTC", locale="en-US",
                                      bypass_csp=True)       # only so annotations can be drawn over the page
            ctx.set_default_timeout(8000)
            self.pages[theme] = ctx.new_page()
        self.taken = []

    def want(self, name: str) -> bool:
        return not self.only or name in self.only

    def sign_in(self):
        for page in self.pages.values():
            sign_in(page, self.base)

    def go(self, page, where: str, width: int = WIDTH) -> None:
        page.set_viewport_size({"width": width, "height": 800})
        page.goto("about:blank")                  # a fresh load, never just a hash change
        page.goto(self.base + "/" + where)
        page.wait_for_load_state("networkidle")
        if self.base.startswith("http") and where.startswith("#/"):
            page.wait_for_selector("main .page", timeout=20000)
            page.wait_for_function("() => !document.querySelector('main .loading')", timeout=20000)
        page.wait_for_timeout(500)

    def shoot(self, name: str, where: str, target=None, setup=None, width: int = WIDTH, height=None,
              annotate=None) -> None:
        """Open `where` (a dashboard #/ route), run `setup(page)`, make the window tall enough to show the whole
        view without scrolling, and save the area `target(page)` returns (None: the whole window)."""
        if not self.want(name):
            return
        clip = None
        for theme in ("light", "dark"):
            page = self.pages[theme]
            self.go(page, where, width)
            if setup:
                setup(page)
            tall = height or max(800, page.evaluate("() => (document.querySelector('main') || document.body).scrollHeight"))
            page.set_viewport_size({"width": width, "height": tall})
            page.mouse.move(width - 2, tall - 2)
            page.wait_for_timeout(350)
            if annotate:
                draw_marks(page, annotate)
            if clip is None:                       # the dark picture uses exactly the light one's area
                try:
                    clip = target(page) if target else None
                except Exception:
                    page.screenshot(path=str(IMAGES.parent / ("failed-%s.png" % name)))
                    raise
            png = page.screenshot(clip=clip, animations="disabled", caret="hide")
            save(png, name, theme)
        self.taken.append(name)


def box(locator, pad: int = 16, page=None, left_of_main: bool = False) -> dict:
    """The area of an element plus some padding, kept inside the window and right of the sidebar."""
    b = locator.first.bounding_box()
    if b is None:
        raise SystemExit("nothing to photograph: %s" % locator)
    page = page or locator.page
    vw = page.viewport_size["width"]
    vh = page.viewport_size["height"]
    floor_x = 0 if left_of_main else main_left(page)
    x0, y0 = max(floor_x, b["x"] - pad), max(0, b["y"] - pad)
    x1, y1 = min(vw, b["x"] + b["width"] + pad), min(vh, b["y"] + b["height"] + pad)
    return {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}


def main_left(page) -> float:
    return page.evaluate("() => { const m = document.querySelector('main'); return m ? m.getBoundingClientRect().left : 0 }")


def main_area(page, until=None, pad: int = 24, top: float = 0) -> dict:
    """The main column (no sidebar), from `top` to the bottom of `until` (or of the window)."""
    x = main_left(page)
    vw, vh = page.viewport_size["width"], page.viewport_size["height"]
    bottom = vh
    if until is not None:
        b = until.first.bounding_box()
        bottom = min(vh, b["y"] + b["height"] + pad)
    return {"x": x, "y": top, "width": vw - x, "height": bottom - top}


def section(page, title: str):
    return page.locator("section.section", has=page.locator("header h2", has_text=title))


def draw_marks(page, marks) -> None:
    """Numbered markers next to parts of the page: [(css selector, number, side)], side "left" or "right"."""
    page.evaluate("""(marks) => {
      const dark = matchMedia('(prefers-color-scheme: dark)').matches;
      for (const [sel, n, side] of marks) {
        const el = document.querySelector(sel);
        if (!el) throw new Error('no element for marker ' + sel);
        const r = el.getBoundingClientRect();
        const m = document.createElement('div');
        m.textContent = String(n);
        Object.assign(m.style, {position: 'fixed', zIndex: 99999, width: '22px', height: '22px', borderRadius: '50%',
          display: 'grid', placeItems: 'center', font: '600 12px/1 system-ui, sans-serif',
          color: dark ? '#0e1116' : '#ffffff', background: dark ? '#8e9aff' : '#2f3dc4',
          boxShadow: '0 0 0 3px ' + (dark ? 'rgba(14,17,22,.85)' : 'rgba(255,255,255,.9)'),
          top: (r.top + r.height / 2 - 11) + 'px',
          left: (side === 'left' ? r.left - 30 : r.right + 8) + 'px'});
        document.body.appendChild(m);
      }
    }""", marks)


def save(png: bytes, name: str, theme: str) -> None:
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if im.width > MAX_WIDTH:
        im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS)
    IMAGES.mkdir(parents=True, exist_ok=True)
    out = IMAGES / ("%s-%s.webp" % (name, theme))
    im.save(out, "WEBP", quality=82, method=6)
    log("%-28s %5s %4dx%-5d %4d KB" % (name, theme, im.width, im.height, out.stat().st_size // 1024))


def run_ref(ids: dict, project: str, key: str, tab: str = "overview", sub: str = "", query: str = "") -> str:
    from urllib.parse import quote
    r = "#/p/%s/r/%s/%s" % (project, ids[(project, key)], tab)
    return r + ("/" + quote(sub, safe="") if sub else "") + (("?" + query) if query else "")


def capture(browser, reports: dict, work: Path, engine: Path, only: set) -> dict:
    sh = Shooter(browser, only)
    sh.sign_in()
    light = sh.pages["light"]

    # ---- a new account: no projects, then one empty project
    sh.shoot("projects-empty", "#/", lambda p: main_area(p, p.locator(".panel")))
    api(light, "POST", "/api/projects", {"name": "support-agent"})
    sh.shoot("project-empty", "#/p/support-agent", lambda p: main_area(p, p.locator(".panel").last))

    ids = populate(light, reports)
    (work / "ids.json").write_text(json.dumps({"%s|%s" % k: v for k, v in ids.items()}, indent=1))
    vul = lambda tab="overview", **kw: run_ref(ids, "support-agent", "baseline", tab, **kw)     # noqa: E731

    # ---- projects and tokens
    sh.shoot("projects", "#/", lambda p: main_area(p, p.locator(".panel").first, pad=14))

    def new_token(page):
        page.fill("input[aria-label='Token name']", "Local testing")
        page.click("text=Create token")
        page.wait_for_selector(".warn-box .cmd code")
        # the token is real but dies with this throwaway database; mask it anyway
        page.evaluate("""() => { const c = document.querySelector('.warn-box .cmd code');
                                 c.textContent = c.textContent.slice(0, 12) + '•'.repeat(24); }""")
        page.wait_for_timeout(300)

    def token_cleanup(page):
        for t in api(page, "GET", "/api/projects/support-agent/tokens", None)["tokens"]:
            if t["name"] == "Local testing":
                api(page, "DELETE", "/api/projects/support-agent/tokens/%s" % t["id"], None)
    if sh.want("token-created"):
        sh.shoot("token-created", "#/p/support-agent/settings",
                 lambda p: main_area(p, section(p, "Upload tokens")), setup=lambda p: (token_cleanup(p), new_token(p)))
        token_cleanup(light)
    sh.shoot("project-settings-plan", "#/p/support-agent/settings", lambda p: box(section(p, "Plan")))

    # ---- the layout, with numbered markers
    sh.shoot("dashboard-layout", vul(), height=800, annotate=[
        (".rail-head .bar-actions", 1, "left"), (".project-select", 2, "right"), ("#rail-nav a", 3, "right"),
        ("#runs .rail-group", 4, "right"), ("#rail-foot .who-am-i", 5, "right"), ("nav.tabs", 6, "left"),
        ("nav.tabs a.doc-link", 7, "left")])

    # ---- the project page
    sh.shoot("project-page", "#/p/support-agent", lambda p: main_area(p, section(p, "Findings per run")))
    sh.shoot("runs-table", "#/p/support-agent", lambda p: box(section(p, "Runs")))

    # ---- a run
    sh.shoot("run-verdict", vul(), lambda p: main_area(p, p.locator(".sevkey")))
    sh.shoot("run-categories", vul(), lambda p: box(section(p, "Scenarios by attack category")))
    sh.shoot("run-rules", vul(), lambda p: box(section(p, "Rules that fired")))
    sh.shoot("run-tools", vul(), lambda p: box(section(p, "Tools the agent called")))
    sh.shoot("run-owasp", vul(), lambda p: box(section(p, "OWASP agentic categories")))
    sh.shoot("run-measured", vul(), lambda p: box(section(p, "What this run measured")))
    sh.shoot("run-attack-goals", run_ref(ids, "email-assistant", "baseline"),
             lambda p: box(section(p, "Attacks that reached their goal")))
    sh.shoot("run-errored", run_ref(ids, "support-agent", "down"),
             lambda p: main_area(p, section(p, "What this run measured")))

    # ---- findings
    sh.shoot("findings-filter", vul("findings", query="sev=critical"),
             lambda p: main_area(p, p.locator(".list").first, top=p.locator("nav.tabs").bounding_box()["y"] - 8),
             height=1150)
    sh.shoot("finding-detail", vul("findings"), lambda p: clip_until(box(p.locator(".detail").first, pad=12),
             p.locator(".detail section.block", has=p.locator("h3", has_text="Remediation"))), height=1700)

    # ---- scenarios and traces (email pack: delivery, attack goals, inconclusive)
    email = lambda tab="overview", **kw: run_ref(ids, "email-assistant", "baseline", tab, **kw)   # noqa: E731
    sh.shoot("scenario-attack", email("scenarios", sub="email_agent_forward_exfiltration/overt_body"),
             lambda p: box(p.locator(".detail").first, pad=12, page=p) | {"height": trace_top(p) - box(p.locator(".detail").first, pad=12, page=p)["y"]})
    sh.shoot("trace-evidence", email("scenarios", sub="email_agent_forward_exfiltration/overt_body"),
             lambda p: evidence_area(p))
    sh.shoot("scenario-inconclusive", email("scenarios", sub="email_agent_unauthorized_delete/delete_security_alert"),
             lambda p: box(p.locator(".detail").first, pad=12, page=p) | {"height": trace_top(p) - box(p.locator(".detail").first, pad=12, page=p)["y"]})
    sh.shoot("policy-tab", vul("policy"), lambda p: main_area(p, top=p.locator("nav.tabs").bounding_box()["y"] - 8),
             height=1100)

    # ---- comparing
    cmp = "#/p/email-assistant/compare?base=%s&head=%s" % (ids[("email-assistant", "baseline")],
                                                          ids[("email-assistant", "hardened")])
    sh.shoot("compare-summary", cmp, lambda p: main_area(p, p.locator("details").first.locator("summary")), width=1440)
    sh.shoot("compare-not-comparable", cmp, lambda p: box(p.locator("details", has_text="Not comparable")), width=1440)
    sh.shoot("compare-verdicts", cmp, lambda p: box(section(p, "Scenario verdicts")), width=1440)

    # ---- MCP scan
    mcp = lambda tab="overview": run_ref(ids, "mcp-servers", "demo server, poisoned mode", tab)     # noqa: E731
    sh.shoot("mcp-overview", mcp(), lambda p: main_area(p, section(p, "Definitions").locator("table").locator("tr").nth(5)))
    sh.shoot("mcp-definitions", mcp("items"), lambda p: main_area(p, top=p.locator("nav.tabs").bounding_box()["y"] - 8),
             height=1000)

    # ---- live updates: a new upload while the project is open
    if sh.want("upload-toast"):
        token = api(light, "POST", "/api/projects/support-agent/tokens", {"name": "toast"})["token"]

        def arrive(page):
            upload(reports["hardened"], token, "--branch", "main", "--label", "hardened")
            page.wait_for_selector("#toast:not([hidden])", timeout=30000)
            page.wait_for_timeout(500)
        def corner(p):
            t = p.locator("#toast").bounding_box()
            vw = p.viewport_size["width"]
            return {"x": vw - 760, "y": t["y"] - 150, "width": 760, "height": t["height"] + 150 + 24}
        sh.shoot("upload-toast", "#/p/support-agent", corner, setup=arrive, height=800)

    # ---- the sign-in page, as a server with GitHub sign-in (and no development sign-in) shows it
    if sh.want("signin"):
        github = start_dashboard(work, port=DASH_PORT + 1, github=True)
        try:
            sh_in = Shooter(browser, only, base="http://127.0.0.1:%d" % (DASH_PORT + 1))
            sh_in.shoot("signin", "#/", lambda p: box(p.locator(".signin"), pad=28, left_of_main=True))
        finally:
            github.stop()

    # ---- the local dashboard (agentsec dashboard) on the Quickstart's two runs
    if sh.want("local-dashboard"):
        local = work / "local"
        (local / ".agentsec" / "hardened").mkdir(parents=True, exist_ok=True)
        shutil.copy(reports["vulnerable"], local / ".agentsec" / "report.json")
        shutil.copy(reports["hardened"], local / ".agentsec" / "hardened" / "report.json")
        lp = DASH_PORT + 2
        srv = Server(["agentsec", "dashboard", ".agentsec", "--port", str(lp)], local, url="http://127.0.0.1:%d/" % lp)
        try:
            sh_local = Shooter(browser, only, base="http://127.0.0.1:%d" % lp)
            sh_local.shoot("local-dashboard", "", None, height=560)
        finally:
            srv.stop()

    # ---- the HTML report agentsec test writes
    if sh.want("report-html"):
        html_path = reports["vulnerable"].parent / "report.html"
        sh_file = Shooter(browser, only, base="file://" + str(html_path.parent))
        sh_file.shoot("report-html", "report.html", None, height=900)
    return ids


def clip_until(area: dict, locator, pad: int = 4) -> dict:
    b = locator.first.bounding_box()
    return dict(area, height=b["y"] + b["height"] + pad - area["y"])


def trace_top(page) -> float:
    return page.locator(".detail").first.locator("text=/^Trace, /").first.bounding_box()["y"] - 4


def evidence_area(page) -> dict:
    """From the tool result that delivered the payload to the call that reached the attack goal."""
    d = page.locator(".detail").first.bounding_box()
    first = page.locator(".detail .ev").filter(has_text="Payload delivered").first.bounding_box()
    last = page.locator(".detail .ev").filter(has_text="Attack goal reached").last.bounding_box()
    return {"x": d["x"], "y": first["y"] - 10, "width": d["width"], "height": last["y"] + last["height"] + 12 - (first["y"] - 10)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--engine", required=True, type=Path, help="checkout of invaris-agentsec (for its example agents)")
    ap.add_argument("--serve", action="store_true", help="set everything up, print the address, keep running")
    ap.add_argument("--keep", type=Path, help="work in this directory and keep it (default: a temporary one)")
    ap.add_argument("shots", nargs="*", help="only these screenshots (names without -light/-dark)")
    args = ap.parse_args()
    engine = args.engine.resolve()
    if not (engine / "examples" / "vulnerable_rag_agent" / "server.py").exists():
        raise SystemExit("%s is not a checkout of invaris-agentsec" % engine)
    from playwright.sync_api import sync_playwright

    work = args.keep.resolve() if args.keep else Path(tempfile.mkdtemp(prefix="agentsec-docs-shots-"))
    work.mkdir(parents=True, exist_ok=True)
    try:
        reports = make_reports(engine, work)
        dash = start_dashboard(work)
        try:
            with sync_playwright() as p:
                browser = chromium(p)
                if args.serve:
                    page = browser.new_page()
                    sign_in(page)
                    ids = populate(page, reports)
                    (work / "ids.json").write_text(json.dumps({"%s|%s" % k: v for k, v in ids.items()}, indent=1))
                    log("ready: %s (sign in as %s); Ctrl+C to stop" % (DASH, USER))
                    try:
                        while True:
                            time.sleep(3600)
                    except KeyboardInterrupt:
                        return
                capture(browser, reports, work, engine, set(args.shots))
                browser.close()
        finally:
            dash.stop()
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
