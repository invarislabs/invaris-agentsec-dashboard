---
title: Configuration and environment variables
nav_title: Configuration
description: Every environment variable of the AgentSec dashboard (database, secrets, OAuth, cookies, plan limits) and of the AgentSec CLI, with defaults and production checks.
seo_description: Every environment variable of the AgentSec dashboard (database, secrets, OAuth, cookies, plan limits) and the AgentSec CLI, with defaults and production checks.
section: reference
order: 5
---

## Dashboard

The dashboard reads its settings once from the environment at start. A commented template is in
[.env.example](https://github.com/invarislabs/invaris-agentsec-dashboard/blob/main/.env.example); never commit a
filled-in `.env`.

| Variable | Default | Meaning |
|---|---|---|
| `AGENTSEC_ENV` | `production` | `production`, `development` or `test`. Anything unrecognised (`prod`, `staging`, a typo) is treated as production, with every production check |
| `DATABASE_URL` | `postgresql+psycopg://agentsec@localhost:5432/dashboard` | SQLAlchemy URL. `postgres://` and `postgresql://` URLs (as Neon, Supabase, Render and Heroku give them, including pooled ones) are converted to the bundled psycopg 3 driver. `sqlite:///dashboard.db` works for a quick local look |
| `DATABASE_DIRECT_URL` | unset | A direct, non-pooled URL used only for migrations (recommended when `DATABASE_URL` goes through a pooler such as Neon's) |
| `SECRET_KEY` | none (a fixed, insecure development key outside production) | Signs session cookies. **At least 32 random characters in production.** Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `PUBLIC_URL` | `http://localhost:8000` | The URL people open, without a trailing slash. Used for upload links, the OAuth callback, the same-origin check, canonical URLs of the docs |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | unset | GitHub OAuth app. Callback URL: `$PUBLIC_URL/auth/github/callback`. **Required in production** |
| `AGENTSEC_DEV_LOGIN` | off | `1` enables sign-in with any username, no GitHub. **Refused in production** |
| `SECURE_COOKIES` | `true` in production | Mark the session cookie `Secure` (HTTPS only) |
| `SESSION_DAYS` | `14` | Session lifetime |
| `PORT` | `8000` | Port the Docker image listens on (set by hosts such as Render) |

Booleans accept `1`, `true`, `yes` or `on`.

### Production checks

In production the dashboard refuses to start with:

| Error | Fix |
|---|---|
| `SECRET_KEY must be set to at least 32 random characters in production` | Set a long random `SECRET_KEY` |
| `AGENTSEC_DEV_LOGIN cannot be enabled in production` | Unset it |
| `set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET so people can sign in` | Configure the OAuth app |

The documentation is not a start-up requirement: a malformed page is logged (`documentation page skipped: ...`) and
left out, and everything else keeps working. The test suite is what refuses malformed pages.

### Plan limits

Every limit lives in `app/plans.py` and is tuned with these variables (the Free plan; paid plans would add their own):

| Variable | Default | Meaning |
|---|---|---|
| `FREE_MAX_PROJECTS` | `10` | Projects an account can own |
| `FREE_MAX_REPORTS_PER_PROJECT` | `500` | Runs kept per project; the oldest are removed as new ones arrive |
| `FREE_RETENTION_DAYS` | `90` | Runs older than this are removed by `python -m app.maintenance prune` |
| `FREE_MAX_REPORT_MB` | `25` | Largest report, uncompressed |
| `FREE_MAX_TOKENS_PER_PROJECT` | `10` | Active upload tokens per project |

### Build and test variables

| Variable | Where | Meaning |
|---|---|---|
| `AGENTSEC_REQUIREMENT` | Docker build argument, `docker compose`, CI | Which AgentSec engine to install, default `invaris-agentsec==0.9.0`. For example `invaris-agentsec @ git+https://github.com/invarislabs/invaris-agentsec.git@<branch>` |
| `TEST_DATABASE_URL` | `pytest` | Run the tests against Postgres (and the migration check); SQLite otherwise |
| `PRUNE_DATABASE_URL` | GitHub Actions secret | The direct database URL the daily prune workflow uses; the job skips itself without it |

## AgentSec CLI

| Variable | Used by | Meaning |
|---|---|---|
| `AGENTSEC_SERVER` | `agentsec upload` | Default dashboard URL when `--server` is not given |
| `AGENTSEC_TOKEN` | `agentsec upload` | The project token (another name with `--token-env`) |
| The variable named by `agent.api_key_env` | `agentsec test`, `replay` | Bearer token sent to the agent |
| The variable named by `judge.api_key_env` | `agentsec test --judge` | Bearer token sent to the judge |
| `env:NAME` entries in `secrets` | `agentsec test` | Secret values read at run time |
| `GITHUB_ACTIONS`, `GITHUB_STEP_SUMMARY` | `agentsec test` (annotations and job summary), `agentsec mcp scan` (annotations only) | Set by GitHub Actions; `GITHUB_ACTIONS=true` turns the CI output on |
| `GITHUB_HEAD_REF`, `GITHUB_REF_NAME`, `GITHUB_SHA`, `GITHUB_SERVER_URL`, `GITHUB_REPOSITORY`, `GITHUB_RUN_ID` | `agentsec upload` | Branch, commit, CI link and repository, recorded automatically only when `GITHUB_ACTIONS=true`. The client also sends `GITHUB_EVENT_NAME`, which the dashboard does not store |
| `AGENTSEC_LLM_BACKEND`, `AGENTSEC_LLM_API_KEY`, `AGENTSEC_LLM_MODEL`, `AGENTSEC_LLM_BASE_URL` | Reference email and browser assistants | Which model backs them; see [Email and browser agents](/docs/testing/email-and-browser#configure-a-model) |
| `AGENTSEC_RUN_LIVE_LLM` | The engine's test suite | `1` enables live-model tests |

The policy file is the main configuration of a test run; see the [Policy reference](/docs/reference/policy).
