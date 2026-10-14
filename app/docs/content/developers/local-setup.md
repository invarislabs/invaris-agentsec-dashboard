---
title: Local setup and development
nav_title: Local setup
description: Run the AgentSec dashboard and engine locally - prerequisites, installing both repositories, environment variables, SQLite or Postgres, migrations, Docker Compose, and development commands.
section: developers
order: 2
---

## Prerequisites

- Python **3.11+** for the dashboard (the engine supports 3.9+).
- Git, and optionally Docker and Postgres 14+ (SQLite is fine for a quick look).
- A clone of the dashboard and, if you want to change the engine too, a clone of the engine next to it:

```bash
git clone https://github.com/invarislabs/invaris-agentsec-dashboard.git
git clone https://github.com/invarislabs/invaris-agentsec.git      # optional
cd invaris-agentsec-dashboard
python -m venv .venv && source .venv/bin/activate
```

## Install

```bash
pip install -e ../invaris-agentsec            # optional: a local engine checkout instead of the PyPI release
pip install -e ".[dev]"                       # the dashboard, with pytest
```

## Configure and run

```bash
export AGENTSEC_ENV=development AGENTSEC_DEV_LOGIN=1
export DATABASE_URL=sqlite:///dashboard.db    # or postgresql+psycopg://agentsec@localhost:5432/dashboard
export PUBLIC_URL=http://localhost:8000 SECRET_KEY=dev-only-change-me-0123456789-0123456789
alembic upgrade head
uvicorn app.main:create_app --factory --reload
```

Open http://localhost:8000, sign in with any username (development sign-in), create a project and a token. The
documentation is at http://localhost:8000/docs. Every variable is listed in
[Configuration](/docs/reference/configuration).

Send a report to it:

```bash
export AGENTSEC_TOKEN=asp_...
agentsec test --policy agentsec.yaml
agentsec upload .agentsec/report.json --server http://localhost:8000
```

Plain HTTP is accepted for `localhost` only.

> [!TIP] No agent at hand?
> Use the fixtures: `tests/fixtures/*.json` are real AgentSec reports (a vulnerable and a hardened reference agent,
> an MCP scan, email and browser pack runs). Upload any of them with `agentsec upload tests/fixtures/vulnerable-report.json`.

## Docker Compose

```bash
docker compose up --build        # Postgres 16 plus the app, development sign-in on, http://localhost:8000
```

The image installs AgentSec 0.9.0. Use another engine build with `AGENTSEC_REQUIREMENT`, for example:

```bash
AGENTSEC_REQUIREMENT="invaris-agentsec @ git+https://github.com/invarislabs/invaris-agentsec.git@<branch>" docker compose up --build
```

## Database and migrations

- Tables: `users`, `projects`, `memberships`, `api_tokens`, `reports` (see [Data models](/docs/developers/data-models)).
- Migrations live in `migrations/versions/` (`0001_initial_schema`, `0002_report_inconclusive`). `alembic upgrade head`
  applies them; the Docker image runs it on start.
- Migrations use `DATABASE_DIRECT_URL` when set, otherwise `DATABASE_URL`.
- To add a migration: change `app/models.py`, then `alembic revision -m "what changed"`, write `upgrade()` and
  `downgrade()`, and run the tests with Postgres (`TEST_DATABASE_URL`), which include a migration check.

## Development commands

| Command | Purpose |
|---|---|
| `uvicorn app.main:create_app --factory --reload` | Run the app with auto-reload |
| `pytest` | All tests on SQLite |
| `TEST_DATABASE_URL=postgresql+psycopg://agentsec@localhost/dashboard_test pytest` | Tests on Postgres, plus the migration check |
| `pytest tests/test_docs.py` | Documentation checks (links, anchors, CLI/API/policy coverage, rendering) |
| `python -m app.maintenance prune` | Delete runs past retention |
| `python tests/fixtures/generate_pack_fixtures.py ../invaris-agentsec` | Regenerate the email and browser fixtures from the engine |

## Working on the engine

```bash
cd ../invaris-agentsec
pip install -e ".[dev]"
pytest                                    # the engine's own suite (live-model tests skip by default)
python examples/vulnerable_rag_agent/server.py &
agentsec test -p examples/vulnerable_rag_agent/agentsec.yaml
```

With the engine installed in editable mode, the dashboard picks up your engine changes on its next restart.

## The front end

The dashboard page is plain JavaScript (`app/static/app.js`), CSS (`app.css`) and bundled IBM Plex fonts, with **no
build step**: edit and reload. The documentation's front end is `docs.css`, `docs.js` and `theme.js`. Rules to keep:

- Insert report data as text only (the `h()` helper does this), never as HTML.
- No inline scripts or `style=""` attributes: the Content Security Policy only allows the app's own files (set
  styles through the DOM's `el.style` as `app.js` does).
- No external assets: fonts and icons are bundled.
