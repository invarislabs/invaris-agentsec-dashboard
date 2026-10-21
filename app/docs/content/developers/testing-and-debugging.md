---
title: Testing and debugging
description: Run the test suites of the AgentSec dashboard and engine, what the tests cover, and how to debug failing scenarios, unexpected findings, uploads and the dashboard itself.
seo_description: Run the AgentSec dashboard and engine test suites, see what they cover, and debug failing scenarios, unexpected findings, uploads and the dashboard itself.
section: developers
order: 6
---

## Dashboard tests

```bash
pip install -e ".[dev]"
pytest                                                                   # SQLite
TEST_DATABASE_URL=postgresql+psycopg://agentsec@localhost/dashboard_test pytest   # Postgres + migration check
```

CI (`.github/workflows/ci.yml`) runs on every pull request, including pull requests from forks, on every push to
`main` and weekly. The **All required checks** job fails if any other job fails or is skipped, so it is the one
check to require before merging.

| Job | What it checks |
|---|---|
| Lint | Ruff (bugs and unused code, rules in `pyproject.toml`), JavaScript syntax, shellcheck, actionlint and zizmor on the workflows |
| Secrets and dependency vulnerabilities | gitleaks over the whole Git history; pip-audit over the dependency set the Docker image installs (not on pushes to `main`, so a new advisory never blocks a deploy) |
| Tests, Python 3.12, deployed dependencies | Every test on Postgres 16 (none may skip) and on SQLite, with the engine pinned in `AGENTSEC_REQUIREMENT`; branch coverage of `app/` in the job summary, failing below 88% |
| Tests, Python 3.11, lowest supported dependencies | The same, with every dependency at the lowest version `pyproject.toml` allows |
| Tests, Python 3.13, newest dependencies | The same, with the newest release of everything, the engine included |
| Docker image builds and serves | `docker compose config`, the image build, and `scripts/smoke_test_image.sh`: production settings, migrations on start, sign-in, security headers, every sitemap page, canonical URLs and robots.txt |

Failing tests are annotated on the pull request; installed versions, coverage, audit results and the smoke test
are in each job's summary. To run the lint checks locally:

```bash
uvx ruff check .
for f in app/static/*.js; do node --check "$f"; done
uvx --from actionlint-py actionlint && uvx zizmor .github/workflows
docker build -t agentsec-dashboard:ci . && scripts/smoke_test_image.sh agentsec-dashboard:ci
```

| File | Covers |
|---|---|
| `tests/test_projects_and_reports.py` | Projects, tokens, uploads, limits, listing, compare, download, deletion |
| `tests/test_auth_and_security.py` | Sign-in, sessions, same-origin writes, CSP and headers, access checks |
| `tests/test_attack_packs_and_verdicts.py` | Inconclusive handling, attack timelines, verdict changes with real pack reports |
| `tests/test_engine_parity.py` | The vendored verdict rules match the engine; hosted, local and CLI comparisons agree |
| `tests/test_migrations.py` | One Alembic head; upgrade and downgrade on SQLite; on Postgres (with `TEST_DATABASE_URL`) the migrations produce the same schema as the models |
| `tests/test_deploy_config.py` | The Render blueprint is one free service with no secrets, the health check, migrations through the direct URL, the prune workflow and command, one engine release across CI, the Dockerfile and docker compose |
| `tests/test_docs.py` | Every docs page renders; internal links and anchors resolve; CLI options, API routes, policy keys, env vars and rules are documented; search and SEO metadata |

The fixtures in `tests/fixtures` are real AgentSec output (reference agents, the demo MCP server, and email and browser
pack runs driven by a scripted stand-in). One test runs the real `agentsec upload` client against a live server.

## Engine tests

```bash
cd ../invaris-agentsec
pip install -e ".[dev]"
pytest                          # live-model tests and the LangGraph test skip by default
pytest tests/test_evaluators.py -x -q
```

End-to-end tests start the reference agents on random ports. Live-model tests need `AGENTSEC_LLM_*` and
`AGENTSEC_RUN_LIVE_LLM=1`. When adding scenarios, update the scenario-count assertions in `test_end_to_end.py` and
`test_api_and_plugin.py`. Custom adapters in tests must accept the `session` keyword.

## Debugging a run

| Symptom | Where to look |
|---|---|
| Every scenario errored | The first `ERROR` line; `agentsec test -v`; is the agent up, the endpoint and port right, the token env var set? See [worked examples](/docs/results/interpreting#every-scenario-errored) |
| A finding you do not believe | The finding's evidence and the scenario's trace (`jq '.scenarios[] \| select(.id=="...").trace'`) |
| Scenarios inconclusive | Did the agent call the tool that carries the payload? Is `retrieval_tools` right? With `inject_after`, did the agent make enough calls? |
| Not observable | The system reports no `actor`; check `meta.actor` in the trace |
| No findings against a real agent | Does it call tools through the API (`tool_call` events exist)? Are `secrets` and `allowed_tools` filled in? |
| A pack category does nothing | It must be listed in `tests:` (or `tests:` empty); pack paths resolve from the current directory |
| Results vary between runs | A model-backed agent samples; compare several runs, keep the seed fixed |

Reproduce a single scenario quickly:

```bash
agentsec test -s indirect_prompt_injection/plain_appended -v
agentsec replay .agentsec/report.json --finding '<finding id>'
```

## Debugging the dashboard

| Symptom | Cause |
|---|---|
| The app will not start: `SECRET_KEY must be set ...` / `... cannot be enabled in production` / `set GITHUB_CLIENT_ID ...` | Production checks; set `AGENTSEC_ENV=development` locally |
| A docs page answers 404 and the log says `documentation page skipped: <file>: <reason>` | That page is malformed (bad front matter, unclosed code block, a disallowed link); `pytest tests/test_docs.py` shows the same error |
| `this dashboard needs an AgentSec build that includes agentsec.dashboard` | Install AgentSec 0.9.0+ or a checkout |
| `403 cross-site request refused` | A `POST`/`PATCH`/`DELETE` whose `Origin` (or `Referer`) is neither `PUBLIC_URL`'s origin nor the request's own `Host`: behind a proxy, check `PUBLIC_URL` and that the proxy forwards `Host` |
| Upload `401` | Wrong or revoked token, or not `asp_...` |
| Upload `413` | Report over the plan's size limit; use `--no-traces` or raise `FREE_MAX_REPORT_MB` |
| Upload hangs then fails on a free host | The host was asleep; call `/healthz` first |
| Postgres errors about prepared statements | Use the pooled URL as given; the app disables automatic preparation for PgBouncer |

Run uvicorn without `--reload` and with `--log-level debug` to see each request.
