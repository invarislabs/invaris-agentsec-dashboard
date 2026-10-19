---
title: Architecture
description: How the AgentSec engine, CLI, local dashboard, hosted dashboard backend, database, report ingestion and documentation fit together, with the repository layout of both projects.
seo_title: AgentSec Architecture: Engine, CLI and Dashboard
seo_description: How the AgentSec engine, CLI, local dashboard, hosted dashboard, database, report ingestion and documentation fit together, with both repositories' layouts.
section: developers
order: 1
---

AgentSec is two open-source repositories (both Apache-2.0):

| Repository | What it contains |
|---|---|
| [invarislabs/invaris-agentsec](https://github.com/invarislabs/invaris-agentsec) | The engine: scenarios, runner, adapters, evaluators, reports, the `agentsec` CLI, the local `agentsec dashboard`, the upload client, the GitHub Action, reference agents and attack packs |
| [invarislabs/invaris-agentsec-dashboard](https://github.com/invarislabs/invaris-agentsec-dashboard) | The hosted dashboard: a FastAPI service with GitHub sign-in, projects, upload tokens, report storage in Postgres, the web page, and this documentation |

The dashboard depends on the engine (`invaris-agentsec>=0.9.0`) and reuses its report logic, so the CLI, the local
dashboard and the hosted dashboard compute summaries, verdicts and comparisons with the same code.

## The big picture

```diagram
 ┌──────────────────────────── invaris-agentsec (engine) ────────────────────────────┐
 │ agentsec.yaml ─▶ policies ─▶ attacks (scenarios) ─▶ runners ─▶ adapters ─▶ AGENT   │
 │                                                     │    ▲                         │
 │                                     trace ◀─────────┘    └── simulated tool results │
 │                                       │                                            │
 │                                 evaluators ─▶ findings ─▶ reports (json/html/md/sarif)
 │                                                             │                      │
 │  agentsec.verdicts, agentsec.compare, agentsec.dashboard ◀──┤ (shared report logic)│
 │  agentsec dashboard (local, read-only)  ◀───────────────────┤                      │
 │  agentsec upload  ──────────────────────────────────────────┼──────────┐           │
 └─────────────────────────────────────────────────────────────┼──────────┼───────────┘
                                                               │ gzip JSON, Bearer asp_...
 ┌──────────────────── invaris-agentsec-dashboard (hosted) ─────┼──────────▼───────────┐
 │ app/ingest.py  POST /api/v1/reports ─▶ app/reports.py ─▶ Postgres (reports.content gz)
 │ app/api.py     /api/... (session)   ◀─ app/insights.py ◀─ agentsec.dashboard / verdicts
 │ app/auth.py    GitHub OAuth, sessions   app/static/ (vanilla JS page, no build step)  │
 │ app/docs/      /docs (Markdown → server-rendered HTML, search, sitemap)              │
 └──────────────────────────────────────────────────────────────────────────────────────┘
```

## Engine layout

| Package | Responsibility |
|---|---|
| `agentsec/policies` | Policy dataclasses, the strict YAML loader, JSON Schema |
| `agentsec/attacks` | `Scenario`, `AttackGoal`, `inject_after`, the category registry (`CATEGORIES`), one module per category, `packs.py` for attack packs |
| `agentsec/runners` | `local.py` drives scenarios (multi-session, limits, simulated tools, statuses); `replay.py` re-runs findings |
| `agentsec/adapters` | `AgentAdapter`, `HTTPAgentAdapter` (plain or streaming), `CallableAdapter` |
| `agentsec/integrations` | `LangChainAdapter` and the in-process `ToolHost` |
| `agentsec/mcp` | MCP client (stdio and HTTP), definition checks, pinning, the MCP report, and the `MCPAttackHost` for `--mcp-listen` |
| `agentsec/traces` | Normalized trace and event types, JSON Schema |
| `agentsec/evaluators` | Deterministic checks, plus the optional `judge.py` |
| `agentsec/effects.py` | The `tool_effects` vocabulary and helpers |
| `agentsec/verdicts.py` | The rules every report consumer shares: tested, evaluation, attack timelines, verdict changes |
| `agentsec/compare.py` | Finding-by-id comparison for `agentsec compare` |
| `agentsec/reports` | Terminal, JSON, HTML, Markdown and SARIF writers, secret masking, GitHub annotations |
| `agentsec/owasp.py` | Rule → OWASP agentic category mapping |
| `agentsec/dashboard` | The local dashboard: report index, insights, HTTP server, static page |
| `agentsec/upload.py` | `agentsec upload` |
| `agentsec/api.py`, `pytest_plugin.py`, `cli/` | Python API, pytest plugin, the CLI |
| `action.yml`, `action/` | The GitHub Action and its scripts |
| `examples/`, `benchmarks/` | Reference agents, attack packs, MCP demo server; framework and real-agent benchmarks |

## Dashboard layout

```text
app/
  main.py          app factory: middleware, routers, static files, /, /healthz; loads the docs once (never fails start-up)
  config.py        settings from the environment, with production checks
  db.py            SQLAlchemy engine and sessions (Postgres, or SQLite for tests and quick runs)
  models.py        users, projects, memberships, upload tokens, reports
  plans.py         plan limits (Free today); every limit is read from here
  auth.py          GitHub OAuth and development sign-in, /api/auth-config
  security.py      token hashing, same-origin writes, security headers (CSP), access checks
  api.py           JSON API for the page (session cookie)
  ingest.py        POST /api/v1/reports (project token)
  reports.py       storing, listing and reading reports; uses agentsec.dashboard for summaries
  insights.py      insights and compare from AgentSec; fills in what an older engine lacks
  _compat_verdicts.py  vendored agentsec/verdicts.py for older engines
  maintenance.py   python -m app.maintenance prune
  docs/            this documentation: content/*.md, images/ (screenshots), diagrams/ (SVG), the Markdown
                   renderer, highlighter, routes
  static/          index.html, app.js, app.css (the dashboard), docs.css, docs.js, theme.js, fonts
migrations/        Alembic (0001 initial schema, 0002 reports.inconclusive)
scripts/           docs_screenshots.py and docs_diagrams.py: regenerate the documentation's pictures
tests/             pytest, with real AgentSec reports as fixtures
Dockerfile, render.yaml, docker-compose.yml, .github/workflows/{ci,prune,cla}.yml
```

## Request flows

**Upload.** `agentsec upload` gzips `{"report", "metadata"}` and posts it with `Authorization: Bearer asp_...`.
`ingest.py` hashes the token, finds the project and the owner's plan, reads the body up to the size limit after
decompression, and calls `reports.store_report`. That validates the report with `agentsec.dashboard.index.is_report`,
summarises it with `summarize_entry` (the same function the local dashboard uses), copies the summary into columns
(so lists never decompress the document), stores the JSON gzip-compressed in `reports.content`, and trims the
project to the plan's run limit.

**Viewing a run.** The page (`app/static/app.js`, hash-routed, no build step) calls
`GET /api/projects/{slug}/reports/{id}`. The API decompresses the report and returns it with `insights`, computed by
`agentsec.dashboard.insights` via `app/insights.py`. The page renders everything as text nodes.

**Comparing.** `GET /api/projects/{slug}/compare` calls `agentsec.dashboard.insights.compare_reports` (which wraps
`agentsec.compare`) and adds verdict changes and evaluation through `agentsec.verdicts`.

**Docs.** `/docs/...` routes in `app/docs/` serve pages parsed once at start-up from Markdown; see
[Writing documentation](/docs/developers/writing-docs).

## Engine compatibility

`app/insights.py` takes everything the installed engine returns and fills in only what an older engine lacks, from
`app/_compat_verdicts.py`, a vendored copy of `agentsec/verdicts.py`. `tests/test_engine_parity.py` checks that the
vendored rules give the engine's answers and that hosted, local and CLI comparisons match. The dashboard now
requires AgentSec 0.9.0, which ships `agentsec.verdicts`, so the vendored module is only a fallback and can be deleted
in a follow-up change (with its parity test).

## Design principles

- **Evidence over scores.** Findings carry input, action, policy, trace excerpt and remediation; no aggregate score.
- **Deterministic first.** Rule-based evaluators; the judge is optional, labelled and never critical.
- **Reproducible.** Seeds, policy hashes and scenario ids are recorded; replay rebuilds the same scenarios.
- **Local by default.** Nothing leaves your machine except to the agent and judge you configure, and uploads you run.
- **One source of truth for verdicts.** `agentsec.verdicts` is shared by every consumer.
- **Hostile content stays inert.** Reports are rendered as text under a strict CSP in both dashboards.
