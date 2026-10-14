---
title: The Findings tab
nav_title: Findings tab
description: Filter, search and read findings in the AgentSec dashboard - severity chips, category, rule, OWASP and source filters, and every block of a finding's detail.
section: guide
order: 5
---

The **Findings** tab lists every finding in the run on the left and the selected finding on the right. On a
phone the list is shown above the detail.

## Filtering and searching

| Control | What it does |
|---|---|
| Severity chips | {{sev:critical}} {{sev:high}} {{sev:medium}} {{sev:low}} with their counts. Select one or several; select again to remove |
| All categories | Only findings from one attack category |
| All rules | Only findings of one rule, for example `secret_leak` |
| All OWASP categories | Only findings mapped to one OWASP category, for example `ASI01 Agent Goal Hijack` |
| All sources | `deterministic` or `model-assisted` (judge) findings |
| Search findings | Matches the title, id, rule, observed action, policy violated and input |
| Clear filters | Appears when any filter is set |

A severity chip only appears for severities that occur, and a select only when there is more than one value to
choose from. Filters are part of the address, so
the overview's links (a severity, a rule, an OWASP bar) open this tab already filtered.

The list header shows "43 findings" or "5 of 43" when filtered, and the hint **j / k to move**: press
{{kbd:j}} and {{kbd:k}} to step through the list. Findings are sorted most severe first. Each item shows its
severity, category, title and scenario id.

:::figure findings-filter
alt: The Findings tab filtered to critical findings: the Critical chip is selected, a Clear filters button has appeared, the list header reads “10 of 43”, and the first critical finding is open on the right.
Filtered to critical findings, as the overview's **Critical 10** link opens it.
:::


## Reading a finding

The detail starts with tags: the **severity**, the **rule** id, the **category**, one tag per **OWASP**
category, and for judge findings a **Model-assisted** tag with the judge's **confidence** (0 to 1). Then the
title, and **Scenario** with a link to the scenario's full trace.

| Block | What it tells you |
|---|---|
| What the agent did | The observed action, for example `tool_call send_email(instruction='Ignore all previous...')`. For judge findings, the judge's one-sentence reason |
| Policy violated | The rule of your policy it broke, for example `forbidden_actions: send_email` or `limits.max_tool_calls = 10` |
| Input | The user message the scenario sent |
| Attack timeline | Only for `attack_goal_achieved`: task given, payload delivered (which tool result), attack goal reached (which call). See [Attack goals](/docs/results/attack-goals-and-exposure) |
| Evidence | The trace events that prove it, rendered like the trace, highlighted in the finding's severity colour, then **Open the full trace** |
| Remediation | A suggested fix, for example "Enforce the tool allowlist outside the model (deny by default) and require confirmation for irreversible actions." |
| Reproduce | Commands to replay this finding and to run only this scenario |

:::figure finding-detail
alt: A finding's detail: tags Critical, forbidden_action, indirect_prompt_injection, ASI02 Tool Misuse and ASI01 Agent Goal Hijack; the title “Indirect prompt injection triggered execute_payment”; What the agent did; Policy violated, forbidden_actions: execute_payment; the Input; the evidence tool call highlighted in red; and the Remediation.
The agent read a document carrying a fake “assistant note” and called a forbidden tool. The evidence is that call.
:::


The **Reproduce** block gives:

```bash
agentsec replay report.json --policy agentsec.yaml --finding '<finding id>'
agentsec test --policy agentsec.yaml --seed 0 -s <scenario id>
```

The first re-runs this finding's scenario against your current agent build and tells you whether it still
reproduces; the second runs just that scenario with the same seed. The policy path and seed are taken from the
report. **Copy id** copies the finding id.

## Finding ids

A finding id is `<scenario id>:<rule>[:<key>]`, for example
`indirect_prompt_injection/plain_appended:forbidden_action:send_email`. The key distinguishes several
findings of the same rule in one scenario (here, the tool name; a call made in a later memory conversation gets
a `:later` suffix). Ids are stable for the same seed and policy, which is how `agentsec compare` and the
[comparison view](/docs/guide/compare) match findings across runs.

## When there are no findings

The tab says **No findings**: "No deterministic check fired in any scenario. See the scenarios tab for what ran."
Check the [Scenarios tab](/docs/guide/scenarios-and-traces) and
[What this run measured](/docs/guide/run-overview#what-this-run-measured) before concluding the agent is safe:
inconclusive and errored scenarios produce no findings either.

## What to do with a finding

1. Read **What the agent did** and the **Evidence**. Confirm the agent really made the call or produced the text.
2. Open the full trace to see what led to it: which document or tool result carried the instruction.
3. Fix the agent (see the remediation), not the policy, unless the policy was wrong (a tool that really is
   allowed, a limit below what a healthy task needs).
4. Re-run with `agentsec replay` or `agentsec test`, upload, and compare against this run.

More guidance with examples: [Reading results: worked examples](/docs/results/interpreting).
