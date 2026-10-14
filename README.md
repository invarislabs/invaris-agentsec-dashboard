# AgentSec hosted dashboard

The hosted dashboard for [Invaris AgentSec](https://github.com/invarislabs/invaris-agentsec) reports. Teams send
the `report.json` files AgentSec writes from CI or their machines, and get every run of every agent in one place:
findings with their evidence, full traces, history across runs, and what changed between any two runs.

This repository is public and open source under the [Apache License 2.0](LICENSE), like the AgentSec engine.
The engine, its CLI, the local `agentsec dashboard` and `agentsec upload` live in
[`invarislabs/invaris-agentsec`](https://github.com/invarislabs/invaris-agentsec); this repository is the hosted
service those reports are uploaded to. You can run it yourself, read exactly what it does with your reports, and
contribute to it.

**Pricing.** The hosted dashboard is free at launch, and everything in this repository is free and open source.
A few premium features will be added later; those will be paid and kept private, outside this repository. Every
plan limit lives in one place (`app/plans.py`, tuned with environment variables), so a paid plan is a new entry
there plus billing, and the open-source app keeps working without it.

## Documentation

The dashboard serves its own documentation at **`/docs`** (for example http://localhost:8000/docs when running
locally): a user guide to every page of the dashboard, how to read verdicts and findings, testing guides for the CLI,
Python API, pytest, frameworks, MCP, email and browser agents, attack packs and CI, a developer guide, and CLI, policy,
report and API references. It is public, server-rendered from the Markdown files in `app/docs/content/`, and ships
with every deployment. `tests/test_docs.py` checks it against the code: links and anchors, every CLI option, policy
key, API route, setting and finding rule. See `/docs/developers/writing-docs` to add or edit a page.

## What it does

- **Sign in with GitHub.** Only the GitHub id, login, name and avatar are kept; the OAuth access token is used once
  to read the profile and discarded.
- **Projects.** A project collects the runs of an agent or repository. Each project's runs are visible only to its
  members (today, its owner).
- **Upload tokens.** Per-project tokens (`asp_...`) that can only upload. Shown once, stored as SHA-256 hashes,
  revocable, with last-used times.
- **Ingestion.** `POST /api/v1/reports`, called by `agentsec upload` and the AgentSec GitHub Action
  (`dashboard-url`, `dashboard-token`). Accepts gzip, enforces the plan's size limit after decompression (so a
  gzip bomb is refused), records branch, commit, CI-run link and label, and keeps runs uploaded with `--no-traces`
  marked as such.
- **Project page.** The latest run's verdict and how it changed from the run before, a findings-per-run chart by
  severity (filter by agent and branch), and every run with its CI link.
- **Report views.** Overview (scenario grid by attack category, OWASP ASI01-ASI10, attack vectors, tools called),
  findings with evidence and `agentsec replay` commands, scenario traces as timelines, the policy as run, MCP
  scans, and run comparison. These are the same views as the open-source `agentsec dashboard`, and the numbers come
  from AgentSec's own code (`agentsec.dashboard.insights`, `agentsec.compare`), so the hosted and local views and
  the CLI always agree.
- **Verdicts as AgentSec 0.8.0 defines them.** Every scenario is shown as passed, findings, error, not observable or
  **inconclusive**. Inconclusive means the scenario's adversarial content never reached the agent (it did not open
  the poisoned email or page, or stopped before a mid-task injection), so nothing was measured: it is never shown
  or counted as passed, in the run list, the history chart, the overview verdict or the category grid, and a
  finding whose scenario is inconclusive in the newer run is never counted as fixed.
- **What a run measured.** Tested scenarios (attacked and judged), findings among them, passed, inconclusive, errors
  and not observable, with the rates computed over tested scenarios only.
- **Attack goals and timelines** (email, browser and other attack packs that declare `attack_goals`). For each
  `attack_goal_achieved` finding: which tool result delivered the payload (and how many earlier results carried
  none, which shows a mid-task injection), and which later tool call achieved the attacker's goal. The trace marks
  both events. Categories that came from an attack pack are labelled.
- **Baseline vs hardened.** Comparing two runs also shows what each run measured and every scenario whose verdict
  changed (findings to passed, passed to findings, tested to inconclusive), so hardening that merely stopped the
  agent from reading the poisoned content is not mistaken for a fix.
- **Download** any run's original `report.json` to replay it locally. `agentsec replay` reports each finding as
  reproduced, not reproduced, inconclusive (exit code 2 when nothing reproduced but something was inconclusive) or
  error.

The dashboard shows what the report records and never presents findings as a model's behaviour. When the agent
describes itself (`x_agentsec.agent`, AgentSec after 0.8.0) the run shows what it reported, and a scripted backend is
labelled **Scripted stand-in**; reports from those versions also carry each attack-pack scenario's `delivery` and
declared `attack_goals` (achieved, not achieved, or not tested), which the scenario view lists. Otherwise the page
says the report does not record who decided; record it in the upload label (for example
`--label "hardened, claude-sonnet-4-5"`).

### Engine compatibility

The rules for verdicts, evaluation, attack timelines and comparisons live in AgentSec (`agentsec.verdicts`, used by
`agentsec compare` and the local `agentsec dashboard`); `app/insights.py` takes everything the installed engine
returns and fills in only what an older engine lacks, from `app/_compat_verdicts.py`, a vendored copy of
`agentsec/verdicts.py`. So the hosted page, the local dashboard and the CLI agree:

| Installed AgentSec | Result |
|---|---|
| `add-dashboard` branch (0.7.0, what CI installs today) | Works; the vendored rules fill in inconclusive handling, timelines, verdict changes |
| `main` after 0.8.0 with `agentsec.verdicts`, local dashboard not yet ported | Works; the engine's rules are used, parity tests run |
| `main` merged with `add-dashboard` plus the local-dashboard port | Works; hosted, local and CLI results are checked to be identical |

`tests/test_engine_parity.py` checks that the vendored copy gives the engine's answers and that hosted, local and CLI
comparisons match whenever the installed engine has `agentsec.verdicts`. Delete `app/_compat_verdicts.py` once the
dashboard requires the AgentSec release that ships it.

## Security

- Report text is hostile (adversarial payloads and agent output). The page inserts it as text only, never parses it
  as HTML; a strict CSP allows only the dashboard's own script, styles and fonts; invisible characters and
  look-alike tool names are made visible.
- Session cookies are signed, `HttpOnly`, `SameSite=Lax`, and `Secure` in production. State-changing requests with
  the session cookie must come from the dashboard's own origin. Uploads use bearer tokens and never the cookie.
- Not found and not allowed look the same (404) across projects, reports and tokens.
- Production refuses to start with a weak `SECRET_KEY`, with development sign-in enabled, or without GitHub OAuth.

## Run it locally

You need Python 3.11+, Postgres 14+ (or nothing, with SQLite for a quick look), and a checkout of
AgentSec 0.9.0 or later (`pip install` below installs it from PyPI), or a checkout of `invaris-agentsec`.

```bash
pip install -e ../invaris-agentsec            # optional: a local AgentSec checkout instead of the PyPI release
pip install -e ".[dev]"

export AGENTSEC_ENV=development AGENTSEC_DEV_LOGIN=1
export DATABASE_URL=postgresql+psycopg://agentsec@localhost:5432/dashboard   # or sqlite:///dashboard.db
export PUBLIC_URL=http://localhost:8000 SECRET_KEY=dev-only-change-me-0123456789-0123456789
alembic upgrade head
uvicorn app.main:create_app --factory --reload
```

Open http://localhost:8000, sign in with any username (development only), create a project and a token, then:

```bash
export AGENTSEC_TOKEN=asp_...
agentsec test --policy agentsec.yaml
agentsec upload .agentsec/report.json --server http://localhost:8000
```

Or with Docker: `docker compose up --build` (Postgres plus the app, development sign-in on). The image installs
AgentSec 0.9.0; set `AGENTSEC_REQUIREMENT` to install another build, for example
`invaris-agentsec @ git+https://github.com/invarislabs/invaris-agentsec.git@<branch or commit>`.

## Deploy

The `Dockerfile` builds one image that applies migrations and serves on `$PORT` (default 8000) behind a
TLS-terminating proxy. It runs on any container host with Postgres; the app needs `DATABASE_URL`, `SECRET_KEY`,
`PUBLIC_URL`, `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` (see [.env.example](.env.example)), a daily
`python -m app.maintenance prune`, and nothing else. The setup below costs nothing.

### Deploy for free (Render + Neon)

| Piece | Service | Free-tier limits that matter here |
|---|---|---|
| Web app | [Render](https://render.com) free web service (`render.yaml`) | 512 MB, 0.1 CPU. Sleeps after 15 minutes without traffic; the next request waits about a minute. 750 instance hours a month per workspace (enough for one service). Outbound bandwidth is limited per workspace (shown in Render's dashboard). |
| Database | [Neon](https://neon.tech) Free plan | 1 GB storage per project, 100 compute-hours a month, sleeps after 5 minutes idle and wakes in under a second. No expiry. Over a limit, Neon suspends instead of billing. |
| Daily clean-up | GitHub Actions (`.github/workflows/prune.yml`) | Free for public repositories. |

To stay at $0: don't add a payment method to Render (without one, Render suspends free services at a limit instead
of billing overages), don't change the plan in `render.yaml`, and keep Neon on the Free plan. Render's own free
Postgres is not used: it is deleted 30 days after creation. Reports are stored gzip-compressed, so 1 GB holds many
thousands of typical runs; the retention clean-up keeps it bounded.

**1. Neon (database).** Sign up at neon.tech and create a project: Postgres 17, region **AWS Asia Pacific
(Singapore)** (next to the Render region in `render.yaml`; pick another pair if you prefer, as long as both match).
In the project's compute settings, set the autoscaling maximum to **0.25 CU**, so the 100 free compute-hours last
about 400 awake hours a month. Then open **Connect** and copy two connection strings:
- with **Connection pooling** on (host contains `-pooler`): this is `DATABASE_URL`;
- with it off: this is `DATABASE_DIRECT_URL`, used for migrations and the clean-up job.

Both look like `postgresql://user:password@host/neondb?sslmode=require`; paste them unchanged.

**2. Render (web app).** Sign up at render.com with GitHub. **New > Blueprint**, pick this repository, and Render
reads `render.yaml`: one free web service, nothing else. It asks for the values marked `sync: false`:
- `DATABASE_URL`, `DATABASE_DIRECT_URL`: the two Neon strings;
- `PUBLIC_URL`: `https://agentsec-dashboard.onrender.com` (correct it in step 3 if Render assigns another URL);
- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`: type `pending` for now (step 3 sets them).

`SECRET_KEY` is generated by Render. Apply the Blueprint; the first build takes a few minutes. When it is live,
`https://<your service>.onrender.com/healthz` answers `{"ok":true}`.

**3. GitHub sign-in.** Create an OAuth app (for an organization: *Settings > Developer settings > OAuth Apps >
New OAuth App*) with homepage `https://<your service>.onrender.com` and callback URL
`https://<your service>.onrender.com/auth/github/callback`. Generate a client secret. In Render, open the service's
**Environment** tab, set `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` and (if it differs) `PUBLIC_URL`, and save; Render
redeploys. Sign in at your service URL.

**4. Daily clean-up.** In this repository's *Settings > Secrets and variables > Actions*, add a secret
`PRUNE_DATABASE_URL` with the Neon **direct** connection string. Run the **prune** workflow once from the Actions tab
to check it. Without the secret, the scheduled job skips itself.

**5. Send reports.** Create a project and an upload token in the dashboard, then use `--server
https://<your service>.onrender.com` with `agentsec upload`, or the AgentSec GitHub Action's `dashboard-url` and
`dashboard-token` inputs. A sleeping service takes about a minute to wake and `agentsec upload` waits 60 seconds,
so in CI wake it first:

```yaml
- run: curl -fsS --retry 8 --retry-delay 10 --retry-all-errors https://<your service>.onrender.com/healthz
```

The Action treats a failed upload as a warning, never a failed job.

**Updates.** Render deploys `main` after CI passes (`autoDeployTrigger: checksPass`); migrations run on start.
Secrets live only in Render, Neon and GitHub Actions secrets; none is in the repository.

## Free plan limits

| Variable | Default | Meaning |
|---|---|---|
| `FREE_MAX_PROJECTS` | 10 | Projects an account can own |
| `FREE_MAX_REPORTS_PER_PROJECT` | 500 | Runs kept per project; the oldest are removed as new ones arrive |
| `FREE_RETENTION_DAYS` | 90 | Runs older than this are removed by `python -m app.maintenance prune` |
| `FREE_MAX_REPORT_MB` | 25 | Largest report, uncompressed |
| `FREE_MAX_TOKENS_PER_PROJECT` | 10 | Active upload tokens per project |

## API

Session (cookie) endpoints used by the page, all under `/api`: `me`, `meta`, `projects` (list, create),
`projects/{slug}` (read, rename, delete), `projects/{slug}/reports` (list, filter by `branch` or `name`),
`projects/{slug}/reports/{id}` (report plus insights; `/download` for the original file; delete),
`projects/{slug}/compare?base=&head=` (`agentsec compare` as data, plus `verdict_changes`, `evaluation` for both
runs, and a `reason` on each not-comparable finding: `missing`, `error` or `inconclusive`), and `projects/{slug}/tokens` (list, create, revoke).

Upload endpoint: `POST /api/v1/reports` with `Authorization: Bearer asp_...`. The body is
`{"report": <report.json>, "metadata": {"branch", "commit", "ci_url", "repository", "label"}}` or a bare report,
optionally gzip-compressed (`Content-Encoding: gzip`). It returns `201 {"id", "project", "url", "findings",
"inconclusive"}` (`inconclusive` is null for MCP scans).

## Layout

```text
app/
  main.py         app factory, middleware, static page
  config.py       settings from the environment, with production checks
  models.py       users, projects, memberships, upload tokens, reports
  plans.py        plan limits (Free today; paid plans are added here)
  auth.py         GitHub OAuth and development sign-in
  api.py          JSON API for the page
  ingest.py       POST /api/v1/reports
  reports.py      storing and reading reports; uses agentsec.dashboard for summaries
  insights.py     insights and compare from agentsec.dashboard and agentsec.verdicts; fills in only what an
                  older engine lacks
  _compat_verdicts.py  vendored agentsec/verdicts.py for engines that predate it (delete when no longer needed)
  security.py     tokens, same-origin writes, security headers, access checks
  maintenance.py  retention pruning
  docs/           the /docs documentation: Markdown pages in docs/content/, renderer, search, routes
  static/         the page (vanilla JS, no build step, bundled IBM Plex fonts)
migrations/       Alembic (uses DATABASE_DIRECT_URL when set, else DATABASE_URL)
tests/            pytest; Postgres via TEST_DATABASE_URL, otherwise SQLite
render.yaml       Render Blueprint: one free web service (see "Deploy for free")
.github/workflows ci.yml (tests on Postgres and SQLite), prune.yml (daily retention clean-up)
```

## Tests

```bash
pytest                                                    # SQLite
TEST_DATABASE_URL=postgresql+psycopg://agentsec@localhost/dashboard_test pytest   # Postgres, plus the migration check
```

The fixtures in `tests/fixtures` are real AgentSec output: the vulnerable and `--safe` reference agent, and the
poisoned demo MCP server (AgentSec 0.7 format, kept to check older reports still work), and AgentSec 0.8.0 reports
over the engine's email and browser attack packs (`email-baseline-report.json`, `email-hardened-report.json`,
`browser-report.json`), plus `email-described-report.json` in the newer format (scenario `delivery` and
`attack_goals`, and the agent describing itself as `backend: scripted`). Those four come from AgentSec's real pipeline driven by a scripted stand-in agent, not a
language model, so they exercise every verdict (findings, passed, inconclusive) and say nothing about any model.
Regenerate them with `python tests/fixtures/generate_pack_fixtures.py ../invaris-agentsec`. One test runs the real
`agentsec upload` client over HTTP against a running server.

Upgrading an existing deployment runs migration `0002`, which adds `reports.inconclusive` and fills it for runs
already stored from the stored reports.

## Not built yet

Team members and roles, organization accounts, rate limiting on the upload endpoint, object storage for very large
reports (they are stored compressed in Postgres today), and email notifications. Billing, paid plans and the
premium features planned for later (for example production trace monitoring) will be private and are not part of
this repository.

## Contributing

Issues and pull requests are welcome. Run the tests (above) before opening a pull request. Report security
problems privately as described in the engine's
[SECURITY.md](https://github.com/invarislabs/invaris-agentsec/blob/main/SECURITY.md), not in a public issue.

By contributing you agree that your contribution is licensed under the Apache License 2.0. On your first pull
request, the CLA Assistant bot asks you to confirm the [Contributor License Agreement](CLA.md) by replying with
the comment it quotes. You only need to do this once; the signature is recorded in `signatures/cla.json`.

## License

Apache License 2.0; see [LICENSE](LICENSE) and [NOTICE](NOTICE). "Invaris" and "AgentSec" are trademarks of
Invaris Labs and are not covered by the license. The bundled IBM Plex fonts are under the SIL Open Font License
1.1 (`app/static/fonts/OFL.txt`).
