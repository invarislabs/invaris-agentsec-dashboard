---
title: Uploading reports to the dashboard
nav_title: Upload to the dashboard
description: Send AgentSec reports to the hosted dashboard with agentsec upload, the GitHub Action or the HTTP API directly - tokens, metadata, transcripts, compression, limits and errors.
section: testing
order: 14
---

Reports reach the hosted dashboard only when you send them. Nothing in AgentSec uploads anything by default.

## Prerequisites

- A project and an upload token (`asp_...`) from the dashboard: see [Projects and tokens](/docs/guide/projects-and-tokens).
- The token in an environment variable, `AGENTSEC_TOKEN` by default. It is never accepted as a command-line
  argument, so it cannot end up in shell history or CI logs.

:::figure token-created
alt: Project settings, Upload tokens: a newly created token, masked, with a Copy button, above the table of the project's tokens.
Create the token in the project's **Settings**; it is shown once (masked in this picture).
:::


## With the CLI

```bash
export AGENTSEC_TOKEN=asp_...
agentsec upload .agentsec/report.json --server https://<your dashboard>
```

```text
Uploaded .agentsec/report.json to https://<your dashboard>/#/p/support-agent/r/2b4e2637b9e340b99854bbd43da6202e
```

| Option | Default | Meaning |
|---|---|---|
| `REPORT` | `.agentsec/report.json` | A `report.json` or `mcp-report.json` |
| `--server URL` | `$AGENTSEC_SERVER` | The dashboard's URL. HTTPS is required, except for `localhost` and loopback addresses |
| `--token-env NAME` | `AGENTSEC_TOKEN` | The environment variable that holds the token |
| `--branch`, `--commit`, `--ci-url` | read from GitHub Actions | Recorded with the run |
| `--label TEXT` | none | A short label, for example the model or prompt version |
| `--no-traces` | off | Leave out the full scenario transcripts; findings, their evidence and run statistics are still sent |

Inside GitHub Actions (`GITHUB_ACTIONS=true`), the branch (`GITHUB_HEAD_REF` or `GITHUB_REF_NAME`), commit
(`GITHUB_SHA`), CI-run link and repository are filled in automatically; explicit options override them.

What the client guarantees:

- the body is gzip-compressed JSON: `{"report": <report>, "metadata": {...}}`;
- the token is only sent over HTTPS, or plain HTTP to this machine;
- redirects are refused, so the token is never re-sent to another host;
- the request times out after 60 seconds.

### Errors

| Message | Cause and fix |
|---|---|
| `error: pass --server or set AGENTSEC_SERVER to your dashboard's URL` | No server given |
| `error: no token: set AGENTSEC_TOKEN to a project token from the dashboard` | The token variable is empty. The message always names `AGENTSEC_TOKEN`, even when you chose another variable with `--token-env` |
| `error: cannot read .agentsec/report.json: [Errno 2] No such file or directory: ...` | No report at that path: run `agentsec test` first, or pass the report's path |
| `error: <path> is not an AgentSec report` / `error: <path> is larger than 64 MB` | The client checks the file before sending it |
| `error: refusing to send the token over plain HTTP to <host>; use https://` | Use the `https://` URL |
| `error: --server must be a URL like https://dashboard.example.com, got '...'` | Not a URL |
| `error: the dashboard rejected the token (401); create a new project token and set AGENTSEC_TOKEN` | Wrong, revoked or mistyped token (again `AGENTSEC_TOKEN` is named whatever `--token-env` is) |
| `error: upload failed: HTTP 413: report too large` (also `upload too large`, or `report is larger than the Free plan's 25 MB limit`) | Over the plan's size limit: use `--no-traces`, or raise `FREE_MAX_REPORT_MB` on a self-hosted dashboard |
| `error: upload failed: HTTP 422: the body is not an AgentSec report: ...` | The file is not a `report.json` / `mcp-report.json` |
| `error: the dashboard answered with a redirect (HTTP 301 to ...); not following it with the token. Check --server` | Usually `http://` instead of `https://`, or a wrong path |
| `error: cannot reach https://.../api/v1/reports: ...` | Network, DNS, or a sleeping free-tier host: wake it with `curl .../healthz` first |

All of them exit with code `2`.

## From GitHub Actions

Set the AgentSec action's `dashboard-url` and `dashboard-token` inputs (and optionally `dashboard-no-traces`). A
failed upload is a warning, never a failed job. See [CI and GitHub Actions](/docs/testing/ci-github-actions#upload-every-run-to-the-dashboard).

## With the HTTP API directly

Any tool can upload: send the report to `POST /api/v1/reports` with the token as a bearer token. The body is either
`{"report": ..., "metadata": ...}` or the bare report, optionally gzip-compressed with `Content-Encoding: gzip`.

```bash
curl -sS -X POST https://<your dashboard>/api/v1/reports \
  -H "Authorization: Bearer $AGENTSEC_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @.agentsec/report.json
```

```json title="201 Created"
{"id": "395866e8d77c4055b3bc736b0c271f13", "project": "support-agent",
 "url": "https://<your dashboard>/#/p/support-agent/r/395866e8d77c4055b3bc736b0c271f13",
 "findings": 43, "inconclusive": 0}
```

With metadata and compression, from Python's standard library:

```python title="upload.py"
import gzip, json, os, urllib.request

report = json.load(open(".agentsec/report.json", encoding="utf-8"))
body = gzip.compress(json.dumps({
    "report": report,
    "metadata": {"branch": "main", "commit": "0123abc", "label": "nightly",
                 "ci_url": "https://ci.example.com/runs/42", "repository": "acme/support-agent"},
}).encode("utf-8"))
req = urllib.request.Request("https://<your dashboard>/api/v1/reports", data=body, method="POST", headers={
    "Authorization": "Bearer " + os.environ["AGENTSEC_TOKEN"],
    "Content-Type": "application/json", "Content-Encoding": "gzip"})
print(json.load(urllib.request.urlopen(req, timeout=60)))
```

Metadata fields are all optional strings: `branch` (up to 255 characters), `commit` (64), `ci_url` (500, `http` or
`https` only, otherwise dropped), `repository` (255), `label` (200). Longer values are cut; other keys are ignored.
Full request and error reference: [Dashboard API](/docs/reference/api#upload-a-report).

## What the dashboard does with a report

1. Checks the token (only its SHA-256 hash is stored) and finds its project.
2. Reads the body up to the owner's plan limit, **after** decompression, so a small gzip bomb is refused.
3. Checks it is an AgentSec report, summarises it with AgentSec's own code, and stores the full JSON compressed.
4. Removes the project's oldest runs beyond the plan's run limit.
5. Records when the token was last used and returns the run's link.

:::diagram report-to-dashboard
alt: Diagram: on your machine or in CI, agentsec test writes .agentsec/report.json, and agentsec upload or the GitHub Action sends it over HTTPS with a Bearer upload token. The hosted dashboard checks the token, reads the body within the plan's size limit after decompression, checks, summarises and stores the report, trims the project to its plan, and the run appears in the project.
The upload path, from `agentsec test` to the run in your project.
:::

`--no-traces` runs are marked, and their pages say full transcripts are not available.

## Privacy

Secrets are already masked in the report file, but traces contain your agent's real responses. Use `--no-traces` if
transcripts must not leave your machine or CI. Runs are visible only to the project's members, and are deleted
after the plan's retention period (90 days on the Free plan) by the dashboard's scheduled clean-up job.
