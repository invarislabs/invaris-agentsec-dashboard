---
title: Reports, SARIF and CI output
nav_title: Reports and SARIF
description: The report files AgentSec writes (JSON, HTML, Markdown, SARIF), GitHub Code Scanning integration, workflow annotations and job summaries, and querying report.json.
seo_title: AgentSec Reports and SARIF for GitHub Code Scanning
seo_description: The report files AgentSec writes (JSON, HTML, Markdown, SARIF), GitHub Code Scanning integration, workflow annotations, job summaries and querying report.json.
section: testing
order: 13
---

## Report files

`agentsec test` writes reports into the output directory (`.agentsec/` by default). Pick formats with `-f`:

| Format | File | Use |
|---|---|---|
| `json` (default) | `report.json` | The complete record: findings and every scenario's full trace. Input for `replay`, `compare`, both dashboards and the GitHub Action |
| `html` (default) | `report.html` | One self-contained page for people: summary cards, OWASP coverage, expandable findings with evidence, every trace. No scripts or external assets, light and dark themes |
| `markdown` | `summary.md` | A compact table of findings, used for the GitHub job summary |
| `sarif` | `results.sarif` | SARIF 2.1.0, for GitHub Code Scanning and other SARIF viewers |

```bash
agentsec test -f json,html,markdown,sarif
```

:::figure report-html
alt: The top of report.html for vulnerable-rag-agent: summary cards (35 scenarios, 0 passed, 43 findings, 0 errors), severity counts, the OWASP agentic categories hit, and the first expandable findings.
`report.html` from the Quickstart's first run. It follows the reader's light or dark setting.
:::

`agentsec replay` writes its own `report.json` under `.agentsec/replay/`, and `agentsec mcp scan` writes
`mcp-report.json`. The JSON format is documented in [Report format](/docs/reference/report-format).

## The Markdown summary

```markdown title="summary.md (from the vulnerable reference agent)"
## Invaris AgentSec

**35** scenarios executed, **0** passed. 43 findings.

🟥 critical 10 · 🟧 high 25 · 🟨 medium 8

| Severity | Finding | Scenario | OWASP |
|---|---|---|---|
| 🟥 critical | Indirect prompt injection triggered send_email | `indirect_prompt_injection/plain_appended` | ASI02, ASI01 |
```

## GitHub Code Scanning

`results.sarif` contains one SARIF rule per finding rule and one result per finding. `critical` and `high` map to
`error`, `medium` to `warning`, `low` to `note`. Each result carries the finding id as a fingerprint
(`agentsecFindingId`) and OWASP tags, and points at the policy file. Upload it with GitHub's action to see
findings under **Security > Code scanning**:

```yaml title=".github/workflows/agent-security.yml"
permissions:
  contents: read
  security-events: write   # required to upload SARIF
jobs:
  agentsec:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: invarislabs/invaris-agentsec@main
        id: agentsec
        with:
          formats: json,html,markdown,sarif
          fail-on: none          # let Code Scanning surface findings instead of failing the step
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: ${{ steps.agentsec.outputs.report-dir }}/results.sarif
```

Keep a `fail-on` threshold if you want both alerts and a failing job. The engine repository runs exactly this on
its own intentionally vulnerable reference agent (`.github/workflows/self-scan.yml`); those alerts are demo
findings from a target built to fail, not vulnerabilities in AgentSec.

## Annotations and job summary

When `GITHUB_ACTIONS=true`, `agentsec test` (with no extra flags) prints one workflow annotation per finding and
appends the Markdown summary to `$GITHUB_STEP_SUMMARY`:

```text
::error title=AgentSec CRITICAL::Indirect prompt injection triggered send_email (indirect_prompt_injection/plain_appended)
::warning title=AgentSec MEDIUM::Tool-call budget exceeded (loop_and_budget_limits/pagination_trap)
```

`critical` and `high` become errors, `medium` warnings, `low` notices. `agentsec mcp scan` prints annotations too.

## Querying report.json

The file is plain JSON. A few `jq` recipes:

```bash
# findings, most severe first (report.json keeps them in scenario order)
jq -r '.findings | sort_by({"critical":0,"high":1,"medium":2,"low":3}[.severity]) | .[]
       | "\(.severity)\t\(.title)\t\(.scenario_id)"' .agentsec/report.json

# scenarios that errored, with the error
jq '.scenarios[] | select(.status=="error") | {id, error: .trace.error}' .agentsec/report.json

# inconclusive scenarios
jq -r '.scenarios[] | select(.status=="inconclusive") | .id' .agentsec/report.json

# the full trace of one scenario
jq '.scenarios[] | select(.id=="prompt_injection/ignore_previous").trace' .agentsec/report.json
```

## Handling reports safely

Secrets are masked everywhere in a report (first four and last two characters kept), but traces contain your
agent's real responses and the adversarial payloads. Treat report files and CI artifacts as sensitive. Use
`agentsec upload --no-traces` if transcripts should not leave your machine or CI.
