---
title: Comparing runs
nav_title: Compare runs
description: Compare two runs in the AgentSec dashboard - new, fixed and changed findings, not-comparable findings and why, and per-scenario verdict changes for baseline versus hardened builds.
section: guide
order: 8
---

**Compare runs** answers "what changed between these two runs?" It uses exactly the same logic as
`agentsec compare` on the command line, so the browser, the CLI and the GitHub Action always agree.

## Picking the runs

| Control | Meaning |
|---|---|
| Baseline, the earlier run | The run you compare against, for example `main` or the unhardened build |
| Current, the newer run | The run you are evaluating, for example a pull request or the hardened build |
| Swap | Exchanges the two |

Both lists group runs by agent (MCP scans are marked "(MCP scan)") and show for each run the time AgentSec
generated the report, then its label, branch and short commit. By default
the current run is the newest run that has an earlier run of the same agent, and the baseline is that earlier
run. **Compare with another run** on a run's page opens this view with that run as the current one.

:::figure compare-summary
alt: Compare runs for the email assistant: the baseline and current run pickers, the counters 0 new, 0 severity up, 12 fixed, 0 severity down, 0 unchanged and 2 not comparable, and the headline “No regressions, and 12 findings fixed. 2 findings could not be checked: the attack never reached the agent in the current run.”
The email attack pack's baseline against its hardened build (a scripted stand-in assistant).
:::


Rules:

- You need at least two runs: otherwise **Comparing needs two runs**. Runs are kept within the plan's retention and
  run limits, so keep the baseline you care about (or download its `report.json`).
- Both runs must be the same kind. An MCP scan and an agent test cannot be compared
  (`cannot compare an MCP scan with an agent test run`).
- Picking the same run twice shows **Pick two different reports**; if no pair can be chosen, **Pick two reports of
  the same kind**. When the server refuses, **These reports cannot be compared** with its reason.
- Runs of two different agents can be compared, but a warning says findings rarely line up.

## How findings are matched

Findings are matched by **id** (`<scenario>:<rule>[:<key>]`), which is stable for the same seed and policy.
The six counters at the top:

| Counter | Meaning |
|---|---|
| New | In the current run, not in the baseline. Shown in red when non-zero |
| Severity up | In both, more severe now |
| Fixed | In the baseline, not in the current run, **and** its scenario was tested again. Green when non-zero |
| Severity down | In both, less severe now |
| Unchanged | In both, same severity |
| Not comparable | In the baseline, missing now, but its scenario was not tested again, so it cannot count as fixed |

The headline sums it up: "N regressions: new or more severe findings in the current run.", "No regressions, and
N findings fixed.", "No regressions.", or "Neither run has findings to compare.", followed by
"N findings could not be checked: the attack never reached the agent in the current run." when that applies.

Below are collapsible groups with each finding's severity (and "was high" when it changed), title, scenario and
rule. **New findings**, **Severity increased** and **Fixed** (shown from the baseline run) are open;
**Severity decreased** and **Unchanged** start folded; **Not comparable** opens by itself when some of its findings
were inconclusive. Empty groups are left out. Select a finding to open it in its run. In the counters, New and
Severity up turn red and Fixed and Severity down green when they are not zero.

## Why "not comparable" matters

A finding is only **fixed** when the newer run actually re-tested its scenario and the problem is gone. If the
scenario is missing from the newer run, errored, was inconclusive or was not observable, the newer run measured
nothing there, so the finding is listed as not comparable with its reason:

| Reason | Meaning |
|---|---|
| not in the current run | The scenario was not run (a different policy, category list or `-s` selection) |
| errored in the current run | The scenario could not run, for example the agent was down |
| inconclusive in the current run (attack not delivered) | The adversarial content never reached the agent |
| not observable in the current run | The agent did not report which agent acted |

:::figure compare-not-comparable
alt: The Not comparable group of a comparison: two baseline findings of email_agent_external_send/new_message, marked inconclusive in the current run (attack not delivered).
Two baseline findings that did not come back, but only because the attack never reached the hardened agent. They are not counted as fixed.
:::


> [!IMPORTANT] Hardening that only avoids the poison is not a fix
> Suppose a "hardened" email assistant simply stops opening emails. Every poisoned-email scenario becomes
> inconclusive and its findings disappear. A naive diff would call them fixed. AgentSec lists them as not
> comparable and the scenario verdicts below show "Not tested in the current run".

## Scenario verdicts

For any two test runs, and especially a baseline versus a hardened build of the same agent, this section shows
what each run measured side by side:

| Row | Baseline / Current |
|---|---|
| Scenarios, Tested | Always shown |
| With findings, Passed, Inconclusive, Errors, Not observable | Shown when either run has any |
| Finding rate among tested | Scenarios with findings divided by tested scenarios, per run |

Then every scenario whose verdict changed, with both statuses and the change:

| Change | Meaning |
|---|---|
| No longer has findings | Findings before, tested and passed now: a real improvement (green) |
| Now has findings | Passed before, findings now: a regression (red) |
| Tested, has findings / Tested, passed | Was untested before (for example inconclusive), tested now |
| Not tested in the current run | Tested before, inconclusive now (highlighted) |
| Errored in the current run | Tested before, errored now |
| Not observable in the current run | Tested before, not observable now |
| Only in the current run / Only in the baseline | The scenario exists in one run only |

If nothing changed: "Every scenario has the same verdict in both runs."

:::figure compare-verdicts
alt: Scenario verdicts: a table of scenarios, tested, with findings, passed and inconclusive for the baseline and the current run, the finding rate among tested (100% and 0%), and the eight scenarios whose verdict changed, one of them from Findings to Inconclusive, “Not tested in the current run”.
Six scenarios no longer have findings, one became tested and passed, and one became inconclusive: not a fix.
:::

## The same comparison in the terminal or CI

Download the two reports with the links at the bottom of the page and run:

```bash
agentsec compare baseline.json current.json
```

It exits `1` when there is a new or worsened finding at or above `--fail-on` (default `low`). In CI the
GitHub Action can do this against a baseline report and post the result as a pull-request comment; see
[CI and GitHub Actions](/docs/testing/ci-github-actions#regression-testing-against-a-baseline).

Warnings `agentsec compare` prints also appear here, for example "seeds differ (0 vs 42): canaries and markers
differ, so results may not line up", "the policy differs between the two runs", and "N scenario(s) only in the
baseline (their findings are not counted as fixed): ...".
