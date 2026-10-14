---
title: Dashboard HTTP API
nav_title: Dashboard API
description: Every endpoint of the hosted AgentSec dashboard - the token-authenticated upload endpoint, the session API used by the web page, authentication, request and response formats, and error responses.
section: reference
order: 4
---

The dashboard has two kinds of endpoints:

| Kind | Path | Authentication | Used by |
|---|---|---|---|
| Upload | `POST /api/v1/reports` | `Authorization: Bearer asp_...` (project token) | `agentsec upload`, the GitHub Action, your own tooling |
| Session API | `/api/...` | The `agentsec_session` cookie set at sign-in | The dashboard's own web page |

Plus `/auth/...` for signing in, `/healthz`, and `/docs`. There is no public OpenAPI page (`/docs` is this
documentation).

> [!NOTE] The session API is the web page's API
> It is stable enough to script against from a signed-in browser session, but it is not a token-based public API.
> State-changing session requests (`POST`, `PATCH`, `DELETE`) must come from the dashboard's own origin (an
> `Origin` or `Referer` header matching it), or they are refused with `403 {"detail": "cross-site request refused"}`.
> Only the upload endpoint is meant for automation.

Errors are JSON: `{"detail": "<message>"}`. Request-validation errors (a missing query parameter, a name that is
too long, `limit` out of range) are FastAPI's `422`, where `detail` is a list of `{"loc", "msg", "type"}` objects. "Not found" and "not allowed" look the same (`404`) across projects,
runs and tokens, so the existence of other people's projects is never revealed. Every `/api/` response has
`Cache-Control: no-store`.

## Upload a report

```text
POST /api/v1/reports
Authorization: Bearer asp_...
Content-Type: application/json
Content-Encoding: gzip            (optional)
```

Body: a report with optional metadata, or a bare report:

```json
{
  "report": { "...": "the contents of report.json or mcp-report.json" },
  "metadata": {"branch": "main", "commit": "0123abc", "ci_url": "https://...", "repository": "acme/agent", "label": "nightly"}
}
```

| Metadata field | Max length | Notes |
|---|---|---|
| `branch` | 255 | |
| `commit` | 64 | Shown as 7 or 12 characters |
| `ci_url` | 500 | Dropped unless `http` or `https` |
| `repository` | 255 | |
| `label` | 200 | |

Values must be strings; longer values are cut and unknown keys ignored.

**Response `201 Created`:**

```json
{"id": "395866e8d77c4055b3bc736b0c271f13", "project": "support-agent",
 "url": "https://<dashboard>/#/p/support-agent/r/395866e8d77c4055b3bc736b0c271f13",
 "findings": 43, "inconclusive": 0}
```

`inconclusive` is `null` for MCP scans.

| Status | `detail` | Cause |
|---|---|---|
| 401 | `send a project token as 'Authorization: Bearer asp_...'` | Missing header, wrong scheme, or not an `asp_` token |
| 401 | `invalid or revoked token` | Unknown or revoked token |
| 400 | `the body must be JSON` | Not valid UTF-8 JSON |
| 400 | `the body is not valid gzip` / `the gzip body is truncated` | Bad gzip with `Content-Encoding: gzip` |
| 413 | `upload too large` | The body as sent (before decompression) is over the plan's size limit (25 MB on Free) |
| 413 | `report too large` | A gzip body that decompresses to more than the limit (so a gzip bomb is refused) |
| 413 | `report is larger than the Free plan's 25 MB limit` | The stored report is over the limit |
| 422 | `the body is not an AgentSec report: it needs findings and scenarios lists` | Not a report |
| 422 | `the report's run_config or summary is malformed: ...` | A damaged report |

Each upload also removes the project's oldest runs beyond the plan's run limit (500 on Free).

## Session API

All under `/api`, all require a signed-in session (`401 {"detail": "sign in first"}` otherwise).

### Account

| Method and path | Returns |
|---|---|
| `GET /api/me` | `{"user": {"id", "login", "name", "avatar_url", "plan"}, "plan": {...}}`. The plan object: `name`, `label`, `max_projects`, `max_reports_per_project`, `retention_days`, `max_report_mb`, `max_tokens_per_project`, `team_members` |
| `GET /api/meta` | `{"version": <AgentSec version>, "severities": [...], "categories": [...], "owasp": {"name", "url", "categories"}, "public_url"}` |
| `GET /api/auth-config` | `{"github": bool, "dev_login": bool}`. No session needed: used by the sign-in page |

### Projects

| Method and path | Body | Returns |
|---|---|---|
| `GET /api/projects` | | `{"projects": [project, ...]}` |
| `POST /api/projects` | `{"name": "..."}` (1 to 120 characters) | `201` project. `403 the Free plan allows 10 projects` at the limit |
| `GET /api/projects/{slug}` | | Project plus `plan` and `branches` (distinct recorded branches) |
| `PATCH /api/projects/{slug}` | `{"name": "..."}` | `{"ok": true}`. Owner only |
| `DELETE /api/projects/{slug}` | | `204`. Deletes the project, its tokens and runs. Owner only |

A project object: `id`, `slug`, `name`, `role` (`owner`), `created_at`, `reports` (count), `latest` (the newest
run entry or `null`). Owner-only endpoints answer `403 only the project owner can do this` to other members.

### Runs

| Method and path | Returns |
|---|---|
| `GET /api/projects/{slug}/reports?branch=&name=&limit=200` | `{"fingerprint": "<count>:<newest upload>", "reports": [entry, ...]}`, newest first. `limit` 1 to 500; `name` filters by agent/server name |
| `GET /api/projects/{slug}/reports/{id}` | `{"entry": entry, "report": <the full report.json>, "insights": {...}}` |
| `GET /api/projects/{slug}/reports/{id}/download` | The original file as an attachment (`report.json` or `mcp-report.json`) |
| `DELETE /api/projects/{slug}/reports/{id}` | `204`. Owner only |
| `GET /api/projects/{slug}/compare?base=<id>&head=<id>` | The comparison (below). `422 cannot compare an MCP scan with an agent test run` |

Unknown run ids answer `404 no such report in this project`; unknown projects, or projects you are not a member of,
answer `404 no such project`.

A run **entry** (the list and summary shape, also used by the local dashboard):

```json
{
  "id": "395866e8d77c4055b3bc736b0c271f13", "kind": "test", "name": "vulnerable-rag-agent",
  "target": "http://127.0.0.1:8000/agent", "generated_at": "2026-10-14T11:09:01+00:00",
  "uploaded_at": "2026-10-14T11:28:58.540040", "version": "0.9.0", "seed": 0,
  "policy_path": "examples/vulnerable_rag_agent/agentsec.yaml", "policy_sha256": "0661a326...",
  "scenarios": 35, "passed": 0, "with_findings": 35, "errors": 0, "not_observable": 0, "inconclusive": 0,
  "findings": 43, "by_severity": {"critical": 10, "high": 25, "medium": 8, "low": 0},
  "branch": null, "commit": null, "ci_url": null, "repository": null, "label": null,
  "traces_stripped": false, "size_bytes": 170571, "display_path": "uploaded 2026-10-14 11:28",
  "error": null, "mtime": 1791977338.54004
}
```

`kind` is `test` or `mcp_scan`. `display_path` is the label, branch and short commit, or "uploaded" and the date.

**Insights** (for agent tests) are computed by AgentSec's own `agentsec.dashboard.insights`: `kind`, `categories`
(per-category scenario cells and status counts), `vectors`, `owasp`, `rules`, `tools`, `outcomes`, `limits`, `errors`,
`actors`, `multi_session_scenarios`, `usage`, `model_assisted`, `evaluation` (tested, with_findings, passed,
inconclusive, errors, not_observable, finding_rate, coverage), `attack_goals` (one timeline per achieved goal),
`pack_categories` and `reported` (the agent's self-description). MCP scans return `items` and their own aggregates.

**Comparison** (`agentsec compare` as data):

| Key | Meaning |
|---|---|
| `new`, `worse`, `fixed`, `better`, `unchanged` | Lists of findings, most severe first, each `{id, rule, scenario_id, category, severity, title, source}`; `worse` and `better` add `previous_severity` |
| `not_comparable` | Baseline findings whose scenario was not re-tested, each with `reason`: `missing`, `error`, `inconclusive` or `not_observable` |
| `warnings` | Seeds, policies or scenario sets differ |
| `regressions` | Number of new or worsened findings |
| `verdict_changes` | `[{"id", "title", "category", "base", "head"}]` for every scenario whose status changed |
| `evaluation` | `{"base": {...}, "head": {...}}`, what each run measured (agent tests only) |
| `base`, `head` | The two run entries |

### Tokens

| Method and path | Body | Returns |
|---|---|---|
| `GET /api/projects/{slug}/tokens` | | `{"tokens": [{"id", "name", "prefix", "created_at", "last_used_at"}]}`, active tokens only |
| `POST /api/projects/{slug}/tokens` | `{"name": "..."}` (1 to 100 characters) | `201`, the token object plus `"token": "asp_..."`, **shown only in this response** |
| `DELETE /api/projects/{slug}/tokens/{id}` | | `204`; revokes it. `404 no such token` |

All token endpoints are owner only. At the limit: `403 the Free plan allows 10 tokens per project`.

## Sign-in endpoints

| Method and path | Meaning |
|---|---|
| `GET /auth/github` | Starts GitHub OAuth (scope `read:user`). `404` when GitHub sign-in is not configured |
| `GET /auth/github/callback` | OAuth callback; redirects to `/` or to `/#/signin?error=state` / `?error=github` |
| `POST /auth/dev-login` | `{"login": "name"}` → `{"ok": true}`, development only (`404 not found` otherwise). `422 use letters, digits and dashes` |
| `POST /auth/logout` | `204`; clears the session |

## Health and docs

| Method and path | Meaning |
|---|---|
| `GET /healthz` | `{"ok": true}` after a database round-trip; used by hosts as a health check |
| `GET /docs`, `GET /docs/<page>` | This documentation (public, server-rendered) |
| `GET /docs/search?q=` | Search results page |
| `GET /docs/search-index.json` | The search index used by the docs' instant search |
| `GET /docs/sitemap.xml` | Sitemap of every documentation page |

## Example: list runs from a script

The session API needs a browser session; for automation, use the upload endpoint and download runs from the page.
To read data with a session cookie (for example while developing locally with development sign-in):

```bash
curl -s -c cookies.txt -H "Origin: http://localhost:8000" -H "Content-Type: application/json" \
     -d '{"login": "dev"}' http://localhost:8000/auth/dev-login
curl -s -b cookies.txt "http://localhost:8000/api/projects/support-agent/reports?limit=5"
```
