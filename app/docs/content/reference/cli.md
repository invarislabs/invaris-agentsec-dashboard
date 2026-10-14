---
title: CLI reference
description: Every agentsec command and option - test, replay, compare, mcp scan, dashboard, upload, init, schema - with defaults, examples, exit codes and error messages, plus the dashboard's maintenance command.
section: reference
order: 1
---

```text
agentsec [--version] <command> [options]
```

If `agentsec` is not on your `PATH`, `python -m agentsec` is equivalent. `agentsec --version` prints
`agentsec 0.9.0`. Every command accepts `-h` / `--help`.

| Command | Purpose |
|---|---|
| [`agentsec test`](#agentsec-test) | Run the adversarial suite against the agent in the policy |
| [`agentsec replay`](#agentsec-replay) | Re-run findings from a report to see whether they still reproduce |
| [`agentsec compare`](#agentsec-compare) | Diff two `report.json` files and flag regressions |
| [`agentsec mcp scan`](#agentsec-mcp-scan) | Check an MCP server's definitions (never calls a tool) |
| [`agentsec dashboard`](#agentsec-dashboard) | Browse reports in a local, read-only web dashboard |
| [`agentsec upload`](#agentsec-upload) | Send a report to a hosted AgentSec dashboard (opt-in) |
| [`agentsec init`](#agentsec-init) | Write a starter `agentsec.yaml` |
| [`agentsec schema`](#agentsec-schema) | Print the JSON Schema for policies or traces |

## `agentsec test`

Run the adversarial suite against the agent described in the policy.

| Option | Default | Meaning |
|---|---|---|
| `-p`, `--policy PATH` | `agentsec.yaml` | Policy file |
| `-o`, `--out DIR` | `.agentsec` | Report directory |
| `-f`, `--format LIST` | `json,html` | Comma-separated: `json` (`report.json`), `html` (`report.html`), `markdown` (`summary.md`), `sarif` (`results.sarif`) |
| `--seed N` | `0` | Seed for canaries and markers; the same seed gives the same scenarios |
| `-s`, `--scenario NAME` | all | Run only this category or scenario id. Repeatable |
| `--fail-on LEVEL` | `low` | Exit 1 if a finding at or above `critical`, `high`, `medium` or `low` exists; `none` never fails on findings |
| `--judge` | off | Also run the model-assisted checks configured under `judge:` |
| `-A`, `--attack-pack PATH_OR_MODULE` | none | Load extra categories from a `.py` file or installed package. Repeatable |
| `--mcp-listen HOST:PORT` | off | Act as the MCP server your agent connects to (streamable HTTP at `/mcp`); `:PORT` binds 127.0.0.1 |
| `-v`, `--verbose` | off | Print progress and per-finding detail (observed action, remediation, OWASP) |

```bash
agentsec test                                          # ./agentsec.yaml
agentsec test -p examples/vulnerable_rag_agent/agentsec.yaml
agentsec test -s prompt_injection -s secret_extraction/system_prompt
agentsec test --fail-on high -f json,html,markdown,sarif --out reports/
agentsec test -A my_pack.py --seed 42
agentsec test --mcp-listen 127.0.0.1:8765
```

Inside GitHub Actions it also prints one annotation per finding and appends a Markdown summary to the job summary.
Messages specific to `test`:

| Message | Meaning |
|---|---|
| `Every scenario errored; is the agent running at <endpoint>?` | Nothing ran; exit code 2 |
| `--mcp-listen must look like HOST:PORT or :PORT, e.g. 127.0.0.1:8765` | Bad `--mcp-listen` value |
| `cannot listen on <addr>: ...` | The MCP host port is taken |
| `warning: the MCP attack host is listening on <host>. It serves adversarial content and accepts any client; only do this on an isolated network.` | Bound to a non-loopback address |
| `--format must be a comma-separated list of: json, html, markdown, sarif` | Bad `-f` value |

## `agentsec replay`

```text
agentsec replay REPORT [-p POLICY] [-o DIR] [--finding ID ...] [-s SCENARIO ...] [--judge]
```

Rebuilds the scenarios of an earlier report from its recorded seed, runs them against the agent in `--policy`, and
reports each finding.

| Option | Default | Meaning |
|---|---|---|
| `REPORT` | required | `report.json` from an earlier run |
| `-p`, `--policy PATH` | `agentsec.yaml` | Policy to run, pointing at the (fixed) agent. A note is printed if it differs from the report's |
| `-o`, `--out DIR` | `.agentsec/replay` | Where the replay report is written |
| `--finding ID` | all | Replay only this finding id. Repeatable |
| `-s`, `--scenario ID` | all | Replay only findings of this scenario. Repeatable |
| `--judge` | off | Re-check model-assisted findings too; without it they are skipped with a note |

```text
Replaying 1 finding from .agentsec/report.json (seed 0)
REPRODUCED      high     Agent attempted forbidden action send_email  [prompt_injection/ignore_previous]

1 reproduced, 0 not reproduced, 0 inconclusive, 0 new, 0 errored
Report written to .agentsec/replay/report.json
```

Per-finding outcomes: `REPRODUCED`, `NOT REPRODUCED`, `INCONCLUSIVE`, `ERROR`, plus `NEW` lines for findings not in
the original report. Other messages: `Nothing to replay: the report has no matching findings.` (exit 0),
`note: the policy file differs from the one used for the report`,
`note: skipped N model-assisted finding(s); pass --judge to re-check them`.

## `agentsec compare`

```text
agentsec compare BASELINE CURRENT [--fail-on LEVEL]
```

| Argument | Meaning |
|---|---|
| `BASELINE` | The earlier `report.json` (or `mcp-report.json`), for example from `main` |
| `CURRENT` | The newer one, for example from a pull request |
| `--fail-on LEVEL` | Default `low`. Exit 1 if a **new or worsened** finding at or above this exists; `none` never fails |

Prints groups `NEW findings` (+), `Severity increased` (^), `Fixed` (-), `Severity decreased` (v), `Unchanged` (=),
`Not comparable` (?), and `Not tested in the new run` (!), then a summary such as:

```text
0 new, 0 worse, 43 fixed, 0 better, 0 unchanged
tested 35 -> 35 of 35 -> 35 scenarios; inconclusive 0 -> 0; 35 scenario verdict(s) changed
```

Warnings: `seeds differ (A vs B): canaries and markers differ, so results may not line up`,
`the policy differs between the two runs`, `N scenario(s) only in the baseline (their findings are not counted as
fixed): ...`, `N scenario(s) only in the new run: ...`. Errors (exit 2): `cannot read report <path>: ...`,
`<path> is not an AgentSec report.json`.

## `agentsec mcp scan`

```text
agentsec mcp scan (--command CMD | --url URL) [options]
```

Connects to an MCP server, lists its tools, resources and prompts, and checks their definitions. It never calls a
tool, reads a resource or fetches a prompt.

| Option | Default | Meaning |
|---|---|---|
| `--command CMD` | one of the two | Start a stdio server with this command, for example `"python server.py"` |
| `--url URL` | one of the two | Streamable-HTTP server URL |
| `--header Name=value` | none | HTTP header; `$ENV_VARS` in the value are expanded. Repeatable |
| `-p`, `--policy PATH` | none | Check tools against this policy's `allowed_tools` / `forbidden_actions` |
| `--pin FILE` | none | Compare with a pin file from an earlier `--pin-write`; changes are reported |
| `--pin-write FILE` | none | Write a pin file with the current definitions. When given, `--pin` is ignored |
| `--recheck` | off | List definitions twice in one session and report changes |
| `-o`, `--out DIR` | `.agentsec` | Report directory (writes `mcp-report.json`) |
| `--timeout SECONDS` | `20` | Connection and request timeout |
| `--fail-on LEVEL` | `low` | Exit 1 at or above this severity |

Inside GitHub Actions it prints one annotation per finding (no job summary). Messages:
`Pinned N tool, N resource and N prompt definition(s) to <file>`, `--header must look like Name=value`,
`error: cannot read pin file <file>: ...` (exit 2), and connection errors (exit 2).

## `agentsec dashboard`

```text
agentsec dashboard [PATH ...] [--host HOST] [--port PORT] [--open] [-v]
```

| Option | Default | Meaning |
|---|---|---|
| `PATH ...` | `.` | Report files or directories to search for `report.json` and `mcp-report.json` |
| `--host HOST` | `127.0.0.1` | Address to listen on; anything else prints a warning (no login) |
| `--port PORT` | `8710` | Port; `0` picks a free one |
| `--open` | off | Open it in the browser |
| `-v`, `--verbose` | off | Log each request |

Prints `AgentSec dashboard at http://127.0.0.1:8710/` and how many reports it found. Errors:
`no such file or directory: <path>`, `cannot listen on <host>:<port>: ... (choose another port with --port)`.
See [Local dashboard](/docs/guide/local-dashboard).

## `agentsec upload`

```text
agentsec upload [REPORT] [--server URL] [--token-env NAME] [--branch B] [--commit C] [--ci-url U] [--label L] [--no-traces]
```

| Option | Default | Meaning |
|---|---|---|
| `REPORT` | `.agentsec/report.json` | `report.json` or `mcp-report.json` to upload |
| `--server URL` | `$AGENTSEC_SERVER` | Dashboard URL; HTTPS except for localhost |
| `--token-env NAME` | `AGENTSEC_TOKEN` | Environment variable holding the project token |
| `--branch`, `--commit`, `--ci-url` | from GitHub Actions | Recorded with the run |
| `--label TEXT` | none | A short label, for example `'gpt-4.1 prompt v3'` |
| `--no-traces` | off | Leave out full transcripts; findings and evidence are still sent |

Prints `Uploaded <report> to <url>`. All errors are listed in
[Uploading to the dashboard](/docs/testing/upload#errors).

## `agentsec init`

```text
agentsec init [PATH]
```

Writes a starter policy to `PATH` (default `agentsec.yaml`) and prints `Wrote agentsec.yaml`. Refuses to overwrite:
`error: agentsec.yaml already exists` (exit 2). The template is shown in [Testing with the CLI](/docs/testing/cli#1-create-a-policy).

## `agentsec schema`

```text
agentsec schema policy|trace
```

Prints the JSON Schema for the policy file or for a trace, for editor validation and tooling:

```bash
agentsec schema policy > agentsec.schema.json
agentsec schema trace  > trace.schema.json
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Completed and nothing reached the `--fail-on` threshold (for `replay`: nothing reproduced) |
| `1` | A finding (or for `compare`, a regression) reached the `--fail-on` threshold; for `replay`, a finding reproduced or a new one appeared |
| `2` | Configuration error (bad or missing policy, unknown key or category, unreadable report or pin file, MCP server unreachable, upload failure), or every scenario errored. For `replay`, also when a replayed scenario errored, or nothing reproduced but a rerun was inconclusive |

## Common configuration errors

All print `error: ...` and exit with code `2`:

| Message | Fix |
|---|---|
| `cannot read policy file <path>: ...` | Check the path, or run `agentsec init` |
| `policy is not valid YAML: ...` | Fix the YAML syntax |
| `unknown key(s) in <section>: <keys> (allowed: ...)` | Typo; the allowed keys are listed |
| `` `agent` section is required `` | Add `agent:` |
| `agent.name is required and must be a string` / `agent.endpoint is required ...` | Fill them in |
| `agent.endpoint must start with http:// or https://` | Fix the URL |
| `unsupported policy version '2' (this AgentSec understands '1')` | Use `version: "1"` |
| `limits.max_tool_calls must be a whole number >= 1` | Integer limits are at least 1 |
| `unknown test category 'x'; available: ...` | Typo in `tests` or `-s`, or a pack not loaded |
| `no scenarios match --scenario x` | `-s` named nothing that was built (pack categories must also be in `tests`) |
| `attack pack 'x': no such file` | Pack paths resolve from the current directory |
| `` --judge needs a `judge:` section in the policy (endpoint, model, ...) `` | Add `judge:` or drop `--judge` |
| `unknown judge check 'x'; available: goal_hijack, paraphrased_leak, ...` | Fix `judge.checks` |

## Dashboard maintenance command

The hosted dashboard ships one command-line task, run from its repository with the dashboard's environment:

```bash
python -m app.maintenance prune
```

It deletes runs older than each project owner's plan retention (90 days on the Free plan) and prints
`Removed N expired run(s).` Run it daily; the repository's `.github/workflows/prune.yml` does. See
[Deploying](/docs/developers/contributing-and-deploying#daily-clean-up).
