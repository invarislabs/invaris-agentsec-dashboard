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
- **Download** any run's original `report.json` to replay it locally.

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
`invaris-agentsec` that includes `agentsec.dashboard` (the release after 0.7.0, or the branch that adds it).

```bash
pip install -e ../invaris-agentsec            # AgentSec with agentsec.dashboard
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

Or with Docker: `docker compose up --build` (Postgres plus the app, development sign-in on). Set
`AGENTSEC_REQUIREMENT` to the AgentSec requirement to install, for example
`invaris-agentsec @ git+https://github.com/invarislabs/invaris-agentsec.git@<branch>`, until a release includes
`agentsec.dashboard`.

## Deploy

The `Dockerfile` builds one image that applies migrations and serves on `$PORT` (default 8000). It runs on any
container host with a managed Postgres (Fly.io, Render, Railway, ECS, Cloud Run); terminate TLS in front of it.

1. Create a GitHub OAuth app. Callback URL: `https://<your host>/auth/github/callback`.
2. Set the environment from [.env.example](.env.example): `DATABASE_URL`, `SECRET_KEY`, `PUBLIC_URL`,
   `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`.
3. Schedule `python -m app.maintenance prune` daily to delete runs past the plan's retention.
4. Check `GET /healthz`.

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
`projects/{slug}/compare?base=&head=`, and `projects/{slug}/tokens` (list, create, revoke).

Upload endpoint: `POST /api/v1/reports` with `Authorization: Bearer asp_...`. The body is
`{"report": <report.json>, "metadata": {"branch", "commit", "ci_url", "repository", "label"}}` or a bare report,
optionally gzip-compressed (`Content-Encoding: gzip`). It returns `201 {"id", "project", "url", "findings"}`.

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
  reports.py      storing and reading reports; uses agentsec.dashboard for summaries, insights and compare
  security.py     tokens, same-origin writes, security headers, access checks
  maintenance.py  retention pruning
  static/         the page (vanilla JS, no build step, bundled IBM Plex fonts)
migrations/       Alembic
tests/            pytest; Postgres via TEST_DATABASE_URL, otherwise SQLite
```

## Tests

```bash
pytest                                                    # SQLite
TEST_DATABASE_URL=postgresql+psycopg://agentsec@localhost/dashboard_test pytest   # Postgres, plus the migration check
```

The fixtures in `tests/fixtures` are real AgentSec output: the vulnerable and `--safe` reference agent, and the
poisoned demo MCP server. One test runs the real `agentsec upload` client over HTTP against a running server.

## Not built yet

Team members and roles, organization accounts, rate limiting on the upload endpoint, object storage for very large
reports (they are stored compressed in Postgres today), and email notifications. Billing, paid plans and the
premium features planned for later (for example production trace monitoring) will be private and are not part of
this repository.

## Contributing

Issues and pull requests are welcome. Run the tests (above) before opening a pull request. Report security
problems privately as described in the engine's
[SECURITY.md](https://github.com/invarislabs/invaris-agentsec/blob/main/SECURITY.md), not in a public issue.

## License

Apache License 2.0; see [LICENSE](LICENSE) and [NOTICE](NOTICE). "Invaris" and "AgentSec" are trademarks of
Invaris Labs and are not covered by the license. The bundled IBM Plex fonts are under the SIL Open Font License
1.1 (`app/static/fonts/OFL.txt`).
