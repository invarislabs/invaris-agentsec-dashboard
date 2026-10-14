---
title: A run's overview
nav_title: Run overview
description: Every part of a run's page in the AgentSec dashboard - the header facts, tabs, verdict, scenario grid, attack goals, rules, tools, OWASP categories, attack vectors, what the run measured, run statistics and reproduce commands.
section: guide
order: 4
---

Open a run from the sidebar, the chart or the runs table. This page covers its header and the **Overview**
tab of an agent test. MCP scans have their own layout, described in
[Policy tab and MCP scans](/docs/guide/policy-and-mcp#mcp-scans).

## The header

The breadcrumb shows **Projects / project / Agent test** (or **MCP scan**). The title is the agent name.
Below it, the run's facts:

| Fact | Where it comes from |
|---|---|
| Endpoint | `agent.endpoint` from the policy that was run |
| Seed | The seed used to build scenarios (`--seed`, default 0) |
| Policy | The policy file path given to `agentsec test` |
| Generated | When `agentsec test` wrote the report |
| AgentSec | The engine version that produced the report |
| Agent reported | What the agent said about itself through `x_agentsec.agent`: name, version, backend, model, configuration |
| {{tag:Scripted stand-in}} | Shown next to "Agent reported" when the agent reported `backend: scripted`: a test double made its decisions, so verdicts say nothing about any model |
| Label, Branch, Commit, CI | Recorded by the upload (automatic in GitHub Actions) |
| Uploaded | When the dashboard received it |

If the run was uploaded with `--no-traces`, a notice says that findings and their evidence are present but full
scenario transcripts are not.

Buttons:

- **Download report.json** (or **mcp-report.json**): the original file, exactly as uploaded, to replay or
  compare locally.
- **Compare with another run**: opens [Compare runs](/docs/guide/compare) with this run as the current one.

Tabs: **Overview**, **Findings** (with their count), **Scenarios** (with their count) and **Policy**. See
[Findings tab](/docs/guide/findings), [Scenarios and traces](/docs/guide/scenarios-and-traces) and
[Policy tab](/docs/guide/policy-and-mcp).

## Warnings and errors

Warnings the engine recorded in the report appear first in yellow boxes, for example that some scenarios were
inconclusive or not observable, or that judge calls failed. Long lists of scenario ids are folded behind
**Show N items**.

If scenarios errored, a purple box lists up to four distinct error messages with how many scenarios each affected,
for example
**35 scenarios: cannot reach agent at http://127.0.0.1:8000/agent: Connection refused**. When every scenario
errored it adds **Start the agent and run agentsec test again.**

## The verdict

A headline sentence and an explanation summarise the run. The possible headlines:

| Headline | When |
|---|---|
| This report has no scenarios. | The policy selected no scenario that could be built (categories that need `tool_effects` or `agent_roles` build nothing without them) |
| No scenario could run. | Every scenario errored, so nothing was tested |
| Nothing was tested: the attack never reached the agent. | Every scenario that ran was inconclusive (the rest errored or were not observable) |
| N findings in X of Y scenarios. | At least one finding. The explanation lists the severities and, if any, how many scenarios were inconclusive and not counted as passed |
| No findings in the scenarios that were tested, but N scenarios were inconclusive. | No findings, some inconclusive |
| No findings, but N scenarios could not be observed. | No findings, some not observable |
| No findings in the scenarios that ran; N scenarios errored. | No findings, some errors |
| All N scenarios passed. | Every scenario was tested and passed |

When there are no findings the explanation adds: "No deterministic check fired on anything the traces show.
That is evidence for these scenarios, not proof the agent is safe."

On the right are the counts: **Scenarios**, **Passed**, **With findings**, **Errors**, and **Not observable**
and **Inconclusive** when there are any. Below, when there are findings, a **severity bar** and links for each
severity (for example **Critical 10**) that open the Findings tab filtered to that severity.

## Scenarios by attack category

The dashboard's signature view: one row per attack category, one square per scenario.

| Square | Meaning |
|---|---|
| {{cell:critical}} {{cell:high}} {{cell:medium}} {{cell:low}} | The scenario has findings; the colour is its worst severity |
| {{cell:passed}} | Passed: attacked and judged, nothing found |
| {{cell:error}} | Error: the scenario could not run |
| {{cell:not_observable}} | Not observable: the agent did not report which agent acted |
| {{cell:inconclusive}} | Inconclusive: the attack was never delivered |

Hover over a square for its title, id and status; select it to open its trace. Select a category name to list
its scenarios. Under each name a short summary reads, for example, "2 findings, worst critical", "all passed",
"not tested" (every scenario errored), "not tested, all inconclusive", or "no findings", followed by
", N inconclusive" when some were. Categories that came from an [attack pack](/docs/testing/attack-packs) are
prefixed "attack pack". The number on the right is how many of the category's scenarios have findings, or
"all errored".

## Attacks that reached their goal

Shown only when at least one **attack goal** was reached, which can only happen in attack-pack scenarios that
declare goals (for example the email and browser packs). One row per `attack_goal_achieved` finding: its severity, the goal (what the attacker wanted,
such as "forwarded/sent confidential mail to an external address"), the scenario id, and the path from payload
to action, for example:

```text
open_email #18 (result 6 of 7) → forward_email #21
```

That reads: the payload arrived in the result of the `open_email` call at trace event 18, which was the 6th of 7
tool results in the scenario (so 5 earlier results were clean: a mid-task injection), and the `forward_email`
call at event 21 achieved the goal. "delivery not tracked" means the scenario does not track delivery. See
[Attack goals and exposure tracking](/docs/results/attack-goals-and-exposure).

## Rules that fired

| Column | Meaning |
|---|---|
| Rule | The finding rule id, for example `forbidden_action`. Judge rules carry a {{tag:model-assisted}} tag |
| Worst | The highest severity among its findings |
| Findings | How many findings this rule produced |
| Scenarios | In how many scenarios |

Select a row to see those findings. Every rule is explained in the [Rules reference](/docs/reference/rules).

## Tools the agent called

Every tool the agent called in this run, classified against the policy:

| Policy column | Meaning |
|---|---|
| {{sev:critical}} Forbidden action | The tool is in `forbidden_actions` |
| {{sev:high}} Not in allowed_tools | The policy has an allowlist and this tool is not on it |
| Allowed | Permitted by the policy |

**Calls** counts every call and **Scenarios** the scenarios that made one. Calls AgentSec answered were simulated
and took no real action. Calls the agent ran itself and reported (tagged "Executed by the agent and reported to
AgentSec" in the trace) really happened on your side, which is why such agents must use test doubles.

## OWASP agentic categories

Shown unless every scenario errored. Findings per category of the OWASP Top 10 for Agentic Applications, ASI01 to
ASI10. All ten are listed so gaps
are visible; categories with findings link to them. A finding can count toward more than one category. The
mapping is Invaris' closest-fit judgement, not an official OWASP classification. See
[Findings and severity](/docs/results/findings-and-severity#owasp-categories).

## How the attack arrived

Shown unless every scenario errored. Scenarios with findings by **vector** (see
[vectors](/docs/concepts#vectors-how-the-attack-reaches-the-agent)): User message, Retrieved document, Tool output,
and Tool definition or Unknown when they occur. Only vectors used in the run are listed. Each bar shows "N of M":
scenarios with findings out of the scenarios using that vector. Hover to see how many were inconclusive.

## What this run measured

The honest denominator of the run. Rates are computed over **tested** scenarios only:

| Row | Meaning |
|---|---|
| Tested | "X of N scenarios (P%): the agent was attacked and judged". The percentage is the run's **coverage** |
| With findings | "X of T tested (P%)", the **finding rate**, or "Nothing was tested" |
| Passed | Passed out of tested |
| Inconclusive | Scenarios whose attack never reached the agent |
| Errors | Scenarios that could not run |
| Not observable | Scenarios that could not be judged |

The Inconclusive, Errors and Not observable counts are links that open the Scenarios tab filtered to them; the
rows only appear when the count is not zero.
| Attack goals reached | `attack_goal_achieved` findings, and in how many scenarios |

A note underneath repeats that errored, inconclusive and not-observable scenarios measured nothing and are left
out of the rates, and says who made the agent's decisions:

- if the agent did not describe itself, the report does not record which model, or whether a scripted
  stand-in, decided; record it with `x_agentsec.agent` or in the upload label;
- if it reported `backend: scripted`, the verdicts test the pipeline and say nothing about any model;
- otherwise the verdicts describe that agent build as it reported itself, and "a model run is one observation,
  not a rate".

## Run

| Row | Meaning |
|---|---|
| Steps | Model calls across all scenarios |
| Tool calls | Tool calls across all scenarios |
| Tokens | Total, prompt and completion tokens the agent reported, or "Not reported by the agent" |
| Cost | Total cost; "Known for X of Y scenarios" when only some were known; "Unknown (no cost reported and no agent.pricing)" when none. Unknown is never shown as zero |
| Agent time | Time spent waiting for the agent |
| Outcomes | How scenarios ended: completed, limit exceeded, error |
| Stopped by limit | Which limits stopped scenarios, and how often |
| Multi-session | Scenarios that ran follow-up conversations (memory tests) |
| Agents seen | Agent names reported in a multi-agent run |
| Model-assisted | Findings that came from the judge model |

## Reproduce

Copyable commands:

- **Re-run the same scenarios**: the `agentsec test` command recorded in the report, with the policy path and seed,
  for example `agentsec test --policy agentsec.yaml --seed 0`. It does not record other options: add any `-s`,
  `--attack-pack` or `--judge` you used.
- **Check whether these findings still reproduce** (only when the run has findings):
  `agentsec replay report.json --policy agentsec.yaml`. Use
  the `report.json` downloaded from this page; replay runs against your current agent build. Each finding comes
  back REPRODUCED, NOT REPRODUCED, INCONCLUSIVE (exit code 2) or ERROR. See
  [`agentsec replay`](/docs/reference/cli#agentsec-replay).

If the report does not record the policy path, the commands assume `agentsec.yaml` and say so.
