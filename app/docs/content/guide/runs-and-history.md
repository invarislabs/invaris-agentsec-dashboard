---
title: Runs and history
description: The project page of the AgentSec dashboard - the latest run's verdict, the findings-per-run chart, agent and branch filters, and the runs table.
section: guide
order: 3
---

Open a project to see **Runs and history**: how the latest run did, how findings changed over time, and every
run in the project.

:::figure project-page
alt: The support-agent project page: the latest run passed all 35 scenarios with 43 fewer findings than the run before, and the findings-per-run chart shows three runs: one where every scenario errored, one with 43 findings and one with none.
A project with three runs of one agent: made while the agent was down (every scenario errored), the vulnerable build (43 findings) and the hardened build (all 35 passed). The newest is summarised at the top; the chart has the oldest on the left.
:::


## Before the first upload

A project without runs shows **Send your first report** with three steps:

1. **Create a project token**, with a **Create an upload token** button. Copy the token; it is shown once.
2. **Upload a report from your machine**, with copyable commands that already contain this dashboard's address:

```bash
export AGENTSEC_TOKEN=asp_...
agentsec test --policy agentsec.yaml
agentsec upload .agentsec/report.json --server https://<this dashboard>
```

3. **Or upload from GitHub Actions on every push**, with a workflow snippet using the AgentSec action's
   `dashboard-url` and `dashboard-token` inputs. See [CI and GitHub Actions](/docs/testing/ci-github-actions).

Add `--no-traces` to the upload to leave full transcripts out; findings and their evidence are still sent.

:::figure project-empty
alt: An empty project page titled support-agent with “Send your first report”: 1, create a project token; 2, commands to upload a report from your machine; 3, a GitHub Actions workflow snippet.
A project before its first upload. The commands contain the dashboard's address (the one in this picture is an example).
:::


## Header

The header shows the project name, the number of runs, and the plan facts, for example
"Free, runs kept 90 days, up to 500" (runs are deleted after 90 days, and a project keeps at most its newest 500
runs). A **Help** link opens this page. **Compare runs** appears once there are two runs; **Settings** appears for
the owner.

> [!NOTE] The page works with the newest 300 runs
> The run count, the filters, the chart, the runs table and the comparison pickers load the project's newest 300
> runs; the sidebar lists the newest 120. A project on the Free plan can hold up to 500, so in a very busy project
> the oldest stored runs are not listed here. Their links keep working.

## Filters

| Filter | Shown when | Effect |
|---|---|---|
| Agent or server | The project has runs from more than one agent or MCP server | Shows the history of one agent. The default is the agent with the most runs |
| Branch | At least one run recorded a branch | Limits the history and the table to one branch, or **All branches** |

Filters are part of the address, so a filtered view can be bookmarked. When no run matches them, the page says
**No runs match these filters**.

## The latest run

Above the chart, a summary of the newest run that matches the filters:

- **Latest run of `<agent>`, `<time>`**.
- A **verdict sentence**, the same one the run's own [Overview](/docs/guide/run-overview#the-verdict) shows,
  for example "43 findings in 35 of 35 scenarios." or "Nothing was tested: the attack never reached the agent."
  For an MCP scan: "N findings in the latest scan." or "The latest scan found nothing."
- How it changed from the run before: **Same number of findings as the run before.**,
  **N more findings than the run before.** or **N fewer findings than the run before.** This compares totals
  only; use [Compare runs](/docs/guide/compare) to see which findings are new or fixed.
- **Open the latest run**.

On the right, the counts: **Scenarios**, **Passed**, **Findings**, **Errors**, and **Inconclusive** when there are
any. For an MCP scan only **Definitions** and **Findings** are shown.

> [!IMPORTANT]
> Fewer findings is not automatically better. If the newer run has more inconclusive or errored scenarios, it
> simply tested less. Check [What this run measured](/docs/guide/run-overview#what-this-run-measured) on both runs.

## Findings per run

A stacked bar chart of the selected agent's last 60 runs, oldest on the left. Each bar is one run; its segments
are that run's findings by severity, from low at the bottom to critical at the top.

| Mark | Meaning |
|---|---|
| {{cell:critical}} {{cell:high}} {{cell:medium}} {{cell:low}} stacked segments | Findings by severity |
| A thin green bar | No findings |
| A thin purple bar | Every scenario errored; nothing was tested |
| A thin yellow bar | No findings, but some scenarios were inconclusive (shown in the legend only when it occurs) |

Hover over or focus a bar to see the upload time, the run's label and its summary. Select a bar, or press
{{kbd:Enter}} on a focused bar, to open that run. With a single run the chart says
**History starts with the second run**.

## The runs table

| Column | Meaning |
|---|---|
| Run | The upload label, or the branch, or the agent name. Below it: the short commit, the branch (when a label is shown) and **(no transcripts)** for runs uploaded with `--no-traces` |
| Uploaded | When the run arrived |
| Scenarios | Scenarios executed (definitions for MCP scans) |
| Passed | Scenarios that passed (– for MCP scans) |
| Findings | The severity strip and the run summary |
| CI | A link to the CI run, when the upload recorded one |

:::figure runs-table
alt: The runs table with three rows: hardened on branch harden-retrieval, 35 scenarios, 35 passed; baseline on main, 35 scenarios, 0 passed, 10 critical, 25 high, 8 medium; and a run on main in which 5 scenarios errored.
Runs uploaded with `--label` show the label with the branch below it; the unlabelled run shows its branch.
:::


Select any row to open the run. Labels, branches, commits and CI links come from the upload: they are read
automatically inside GitHub Actions, or set with `agentsec upload --label/--branch/--commit/--ci-url`.

> [!TIP] Label the runs you will compare
> A label such as `--label "baseline, claude-sonnet-4-5"` or `--label "hardened prompt v3"` makes the history
> readable, and records which model or configuration made the agent's decisions when the agent does not report
> it itself.
