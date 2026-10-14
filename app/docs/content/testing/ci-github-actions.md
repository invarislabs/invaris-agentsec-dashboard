---
title: CI and GitHub Actions
description: Run AgentSec in CI with the packaged GitHub Action - inputs and outputs, starting your agent, failing on severity, comparing pull requests against a baseline with a PR comment, uploading to the dashboard, and a hand-written workflow.
section: testing
order: 12
---

AgentSec ships a composite GitHub Action (`action.yml` in the engine repository) that installs AgentSec,
optionally starts your agent, runs the suite, uploads the reports, optionally compares against a baseline and
uploads to the dashboard, then fails the job if findings meet your threshold.

## Basic usage

```yaml title=".github/workflows/agent-security.yml"
name: agent-security
on: [pull_request]
permissions:
  contents: read
jobs:
  agentsec:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: invarislabs/invaris-agentsec@main
        with:
          policy: agentsec.yaml
          fail-on: high
          start-command: python my_agent/server.py --port 8000
          wait-for-url: http://127.0.0.1:8000/
```

If your agent is already running somewhere (a staging URL in the policy), omit `start-command` and
`wait-for-url`. Inside Actions, `agentsec test` also prints one annotation per finding and writes a Markdown job
summary automatically.

> [!TIP]
> Pin the action to a release tag or commit instead of `@main` for reproducible builds, and use `package:` (for
> example `invaris-agentsec==0.9.0`) to pin the engine version it installs.

## Inputs

| Input | Default | Meaning |
|---|---|---|
| `policy` | `agentsec.yaml` | Policy file, relative to `working-directory` |
| `fail-on` | `low` | Fail if a finding at or above this severity exists: `critical`, `high`, `medium`, `low`, `none` |
| `seed` | `0` | Scenario seed |
| `formats` | `json,html,markdown` | Report formats: `json`, `html`, `markdown`, `sarif` |
| `judge` | `false` | Run the model-assisted judge configured in the policy |
| `start-command` | empty | Command that starts the agent in the background; it is stopped after the tests |
| `wait-for-url` | empty | URL polled until the agent answers (any HTTP status counts) |
| `wait-timeout` | `60` | Seconds to wait for `wait-for-url` |
| `working-directory` | `.` | Where to run |
| `out` | `.agentsec` | Report directory |
| `python-version` | `3.11` | Python to set up; empty to use the runner's |
| `package` | empty | What to `pip install`; empty installs the action's own copy of AgentSec |
| `extra-args` | empty | Extra `agentsec test` arguments, for example `-s prompt_injection`. Split on spaces, with no shell quoting, so arguments cannot contain spaces |
| `baseline-report` | empty | An earlier `report.json` to compare this run against |
| `compare-fail-on` | `low` | With `baseline-report`: fail on a new or worsened finding at or above this |
| `pr-comment` | `true` | With `baseline-report`, on `pull_request`: post or update a comment with the comparison |
| `github-token` | the job's token | Token used to post the comment |
| `comment-marker` | `default` | Distinguishes this action's comment from others (for example in a matrix) |
| `dashboard-url` | empty | Upload the report to a hosted AgentSec dashboard (opt-in) |
| `dashboard-token` | empty | Project token for `dashboard-url`; pass it from a secret |
| `dashboard-no-traces` | `false` | Leave full transcripts out of the upload |
| `upload-artifact` | `true` | Upload the report directory as a workflow artifact |
| `artifact-name` | `agentsec-report` | Artifact name; make it unique per matrix entry |

## Outputs

| Output | Meaning |
|---|---|
| `exit-code` | Exit code of `agentsec test`: 0 clean, 1 findings at or above threshold, 2 error |
| `findings` | Number of findings |
| `scenarios` | Number of scenarios executed |
| `report-dir` | Directory containing the reports |
| `compare-exit-code` | 0 clean, 1 regressions, 2 error; empty when no `baseline-report` was given |

## How the job is failed

If the agent process exits, or `wait-for-url` does not answer within `wait-timeout`, the **Start the agent** step
fails the job straight away (`The agent process exited before ... became reachable` / `Timed out after 60s waiting
for ...`), with the last 50 lines of the agent's log. After that, the suite step never fails by itself: reports are uploaded first (artifact, dashboard), then a final gate step fails
the job from the recorded exit codes, printing `AgentSec exited with code N` and/or `agentsec compare exited with
code N`. The agent is always stopped. Inputs reach the scripts through environment variables and are never
interpolated into shell text, which prevents script injection through input values.

## Upload every run to the dashboard

1. In the dashboard, create a project and an upload token ([Projects and tokens](/docs/guide/projects-and-tokens)).
2. Add the token as a repository secret named `AGENTSEC_TOKEN`.
3. Set the inputs:

```yaml
      - uses: invarislabs/invaris-agentsec@main
        with:
          policy: agentsec.yaml
          start-command: python my_agent.py
          wait-for-url: http://127.0.0.1:8000/
          dashboard-url: https://<your dashboard>
          dashboard-token: ${{ secrets.AGENTSEC_TOKEN }}
```

Branch, commit and a link to the CI run are recorded automatically. **A failed upload is a warning, never a failed
job**: the security result is the suite's, not the dashboard's. With `dashboard-url` set but an empty token, the step
warns `dashboard-url is set but dashboard-token is empty; the report was not uploaded.`

> [!NOTE] Free hosts that sleep
> A dashboard on a free host that sleeps when idle (such as Render's free tier) takes about a minute to wake, and
> `agentsec upload` waits 60 seconds. Wake it first:
>
> ```yaml
> - run: curl -fsS --retry 8 --retry-delay 10 --retry-all-errors https://<your dashboard>/healthz
> ```

## Regression testing against a baseline

Set `baseline-report` to an earlier `report.json` and the action runs `agentsec compare` after the suite. This
catches regressions rather than every existing finding: a policy that tolerates some medium findings can still fail
a pull request that makes something new or worse.

```yaml title=".github/workflows/agent-security.yml"
name: agent-security
on:
  pull_request:
  schedule:
    - cron: "0 6 * * *"     # also run nightly, catching drift with no pull request involved
permissions:
  contents: read
  pull-requests: write      # only needed for the pull-request comment
jobs:
  baseline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: {ref: main}
      - uses: invarislabs/invaris-agentsec@main
        with:
          start-command: python my_agent/server.py --port 8000
          wait-for-url: http://127.0.0.1:8000/
          out: .agentsec/baseline
          fail-on: none          # this run only produces a baseline report
          artifact-name: agentsec-baseline
  agentsec:
    needs: baseline
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with: {name: agentsec-baseline, path: .agentsec/baseline}
      - uses: invarislabs/invaris-agentsec@main
        with:
          start-command: python my_agent/server.py --port 8000
          wait-for-url: http://127.0.0.1:8000/
          baseline-report: .agentsec/baseline/report.json
          compare-fail-on: high
```

On a `pull_request` event a comment with the new, fixed and changed findings is posted and updated in place on later
pushes. It uses the `gh` CLI (preinstalled on GitHub-hosted runners) and needs `pull-requests: write`. A forked pull
request's token often cannot comment; the step warns and continues. Set `pr-comment: false` to only gate the job.

## SARIF and Code Scanning

Add `sarif` to `formats` and upload `results.sarif`; see [Reports, SARIF and CI output](/docs/testing/reports-and-sarif#github-code-scanning).

## A hand-written workflow

Without the packaged action:

```yaml
name: agent-security
on: [pull_request]
jobs:
  agentsec:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install invaris-agentsec
      - run: python my_agent/server.py &      # your agent, with synthetic credentials
      - run: sleep 5
      - run: agentsec test --policy agentsec.yaml --fail-on high
      - uses: actions/upload-artifact@v4
        if: always()
        with: {name: agentsec-report, path: .agentsec/}
      - run: agentsec upload .agentsec/report.json
        if: always()
        env:
          AGENTSEC_SERVER: https://<your dashboard>
          AGENTSEC_TOKEN: ${{ secrets.AGENTSEC_TOKEN }}
```

Exit code `1` fails the job on findings; exit code `2` fails it on configuration or connection errors, so a broken
setup is never mistaken for a clean result. Upload the report even on failure, since it holds the evidence.

## Other CI systems

Nothing in AgentSec is GitHub-specific except the annotations and job summary. In any CI: install
`invaris-agentsec`, start the agent, run `agentsec test` with `--fail-on`, keep `.agentsec/` as an artifact, and
optionally `agentsec compare` against a stored baseline and `agentsec upload` with `--branch`, `--commit` and
`--ci-url` set from your CI's variables.
