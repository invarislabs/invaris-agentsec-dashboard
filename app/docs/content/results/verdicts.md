---
title: Verdicts and outcomes
description: What every AgentSec result means - scenario verdicts (passed, findings, error, not observable, inconclusive), execution outcomes, replay outcomes, skipped tests, exit codes, and what to do next for each.
section: results
order: 1
---

AgentSec reports results at several levels. This page defines every one of them and tells you what to do next.

## Scenario verdicts

Every scenario ends with exactly one status. When several could apply, the first one in this table wins:

| Order | Status | Meaning | Counts as tested? |
|---|---|---|---|
| 1 | {{status:findings}} | At least one check fired. Wins even if the scenario later errored: an agent that took a forbidden action and then crashed still took it | Yes |
| 2 | {{status:error}} | The scenario could not complete: agent unreachable, timeout, HTTP error, invalid reply | No |
| 3 | {{status:not_observable}} | The scenario needs to know which agent acted (multi-agent), the agent reported no attribution, and nothing was found | No |
| 4 | {{status:inconclusive}} | The scenario tracks delivery, its adversarial content never appeared in any tool result the agent received, and nothing was found | No |
| 5 | {{status:passed}} | The agent was attacked and judged, and no check fired | Yes |

> [!IMPORTANT] Only "passed" and "findings" are tested
> Errored, not-observable and inconclusive scenarios measured nothing. They are never counted as passed, they
> are left out of the finding rate, and a finding whose scenario is in one of these states in a newer run is
> never counted as fixed. The CLI, the local dashboard and the hosted dashboard all apply this rule from the
> same code (`agentsec.verdicts`).

### What to do for each verdict

| Verdict | Typical cause | What to do next |
|---|---|---|
| {{status:findings}} | The agent obeyed an injection, leaked a secret, exceeded a limit... | Open the finding's evidence, fix the agent, then replay. See [worked examples](/docs/results/interpreting) |
| {{status:passed}} | No check fired on anything the trace shows | Treat it as evidence for this scenario, not proof of safety. Keep it in CI to catch regressions |
| {{status:error}} | The agent is down, the endpoint or port is wrong, the token env var is unset, the reply is not in the expected format | Read the error message on the scenario. Fix the setup and run again. If every scenario errored, `agentsec test` exits `2` |
| {{status:not_observable}} | A multi-agent scenario, but the system did not say which agent made each call | Report `actor` / `delegated_by` (see [Multi-agent testing](/docs/testing/multi-agent)), or drop the category |
| {{status:inconclusive}} | The agent finished without opening the poisoned email or page, or stopped before the step where the injection appears | Give the agent a task that leads it to the poisoned item, check that its tools are wired to AgentSec, and with a real model run it more than once |

## Execution outcomes

Separately from its verdict, each scenario's trace records how the conversation ended (`trace.outcome`):

| Outcome | Shown as | Meaning |
|---|---|---|
| `completed` | Completed | The agent gave a final answer without asking for more tools |
| `limit_exceeded` | Stopped by `<limit>` | AgentSec stopped it because a live limit was hit: `max_steps`, `max_tool_calls` or `max_seconds` |
| `error` | Error | The adapter failed; the message is in `trace.error` |

A scenario stopped by a limit usually also has a limit finding (for example `limit_max_tool_calls`).

## Attack goal states

Scenarios from attack packs can declare **attack goals**, the tool calls that would prove the attack worked.
Each goal ends in one of three states:

| State | JSON `achieved` | Meaning |
|---|---|---|
| Achieved | `true` | After the payload reached the agent, it made a matching call (`attack_goal_achieved` finding) |
| Not achieved | `false` | The payload reached the agent and it did not make a matching call |
| Not tested | `null` | The payload never reached the agent |

See [Attack goals and exposure tracking](/docs/results/attack-goals-and-exposure).

## Run-level results and exit codes

The CLI turns a run into an exit code, which is what fails a CI job:

| Code | `agentsec test` | `agentsec compare` | `agentsec replay` |
|---|---|---|---|
| `0` | No finding at or above `--fail-on` | No new or worsened finding at or above `--fail-on` | Nothing reproduced |
| `1` | A finding at or above `--fail-on` (default `low`, so any finding) | A regression at or above `--fail-on` | A finding reproduced, or a new one appeared |
| `2` | Configuration error, or **every** scenario errored | A report could not be read | A replayed scenario errored (even if another finding reproduced), or nothing reproduced but something was inconclusive |

For `replay` the checks are applied in order: any errored rerun gives `2`, then any reproduced or new finding gives
`1`, then any inconclusive rerun gives `2`, otherwise `0`. `--fail-on none` never fails on findings. Exit code `2` means "could not measure", which is why a broken setup is
never mistaken for a clean result. Full details: [CLI reference](/docs/reference/cli#exit-codes).

> [!NOTE] Inconclusive scenarios do not change the exit code of `agentsec test`
> A run with no findings but some inconclusive scenarios exits `0`, and prints a warning listing them. If your
> CI must also require delivery, use the Python API: `RunResult.passed` is false while any scenario is
> inconclusive.

## Replay outcomes

`agentsec replay` re-runs the findings of an earlier report against your current agent build and prints one
line per finding:

| Outcome | Meaning |
|---|---|
| REPRODUCED | The same finding (same id) came back |
| NOT REPRODUCED | The scenario ran, was tested, and the finding did not come back. Evidence, not proof, of a fix: a model-backed agent can vary between runs |
| INCONCLUSIVE | The rerun never delivered the payload, so it cannot show the finding is fixed. Exit code `2` if nothing reproduced |
| ERROR | The scenario could not run |
| NEW | A finding that was not in the original report |

The summary line reads, for example, `1 reproduced, 1 not reproduced, 0 inconclusive, 0 new, 0 errored`.

## Skipped

AgentSec has no "skipped" verdict for a scenario that ran. "Skipped" appears in these places:

| Where | What is skipped and why |
|---|---|
| Categories that build no scenarios | `action_without_authorization`, `deceptive_action_report`, `dangerous_composition`, part of `identity_and_session_confusion` and `multi_agent_delegation` build scenarios only when the policy declares `tool_effects` or `agent_roles`. Listing them without those adds nothing; it is not an error |
| pytest plugin | `agentsec_run` skips a test (instead of passing it) when the category built no scenarios, when every scenario was not observable, or when every scenario was inconclusive or not observable. It warns when only some were inconclusive |
| `agentsec replay` | Model-assisted (judge) findings are skipped unless you pass `--judge`: `note: skipped N model-assisted finding(s); pass --judge to re-check them` |
| The judge | A judge check that fails or returns an unusable verdict is skipped, never counted as a pass or a finding; the run warns `judge: N of M judge calls failed or returned an unusable verdict` |

## Pass and fail at a glance

| Question | Answer |
|---|---|
| Did the build fail? | Look at the exit code (CI) or any finding at or above your threshold |
| Did the agent resist the attacks? | Look at **passed** among **tested** scenarios, never at the raw scenario count |
| Did my fix work? | Compare against the old run: **fixed** counts only re-tested scenarios; check **Not comparable** and **Scenario verdicts** |
| Is my agent safe? | AgentSec gives evidence for the scenarios it ran, not a proof. A clean run means no check fired on what the traces show |
