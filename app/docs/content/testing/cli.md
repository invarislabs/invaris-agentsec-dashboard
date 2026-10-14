---
title: Testing with the CLI
description: Test an AI agent from the command line with agentsec test - prerequisites, writing a policy, running, selecting scenarios, seeds, report formats, fail thresholds, replay, compare and troubleshooting.
section: testing
order: 2
---

The `agentsec` command is the most direct way to test an agent. Use it locally while you build, and in CI.

## Prerequisites

- Python 3.9 or newer, and AgentSec installed:

```bash
pip install invaris-agentsec      # or, from a checkout: pip install -e ".[dev]"
agentsec --version
```

- Your agent running somewhere AgentSec can reach over HTTP, speaking the OpenAI-style chat-completions format.
  If it does not yet, see [Make your agent testable](/docs/testing/agent-contract), or test it in-process with the
  [Python API](/docs/testing/python-api).
- A test deployment: synthetic credentials, sandboxed or mocked tools, never production.

## 1. Create a policy

```bash
agentsec init                    # writes agentsec.yaml; refuses to overwrite an existing file
```

The starter policy:

```yaml title="agentsec.yaml (from agentsec init)"
version: "1"

agent:
  name: my-agent
  endpoint: http://localhost:8000/v1/chat/completions

allowed_tools:
  - search_documents
  - create_draft

forbidden_actions:
  - send_email
  - reveal_credentials
  - execute_payment

# Synthetic credentials your agent can see; they must never appear in its output.
secrets: []

limits:
  max_steps: 12
  max_tool_calls: 10
  max_cost_usd: 0.50

tests:
  - prompt_injection
  - indirect_prompt_injection
  - secret_extraction
  - unauthorized_tool_use
  - tool_output_poisoning
  - unsafe_retrieved_documents
  - loop_and_budget_limits
```

Edit it for your agent:

- `agent.endpoint`: the full URL that receives POST requests.
- `allowed_tools`: every tool your agent really has. The allowlist check only runs when this key is present.
- `forbidden_actions`: dangerous actions the agent must never take, using the real names your agent would
  recognise (they are also used in attack payloads).
- `secrets`: synthetic credentials the agent can see. Use `env:NAME` to read one from the environment.
- `limits`: realistic budgets for a healthy task.
- `tests`: the categories to run. Leave it empty to run all of them. See the
  [Attack catalog](/docs/reference/attack-catalog).

Every key is in the [Policy reference](/docs/reference/policy). Typos are rejected on purpose, so a misspelled
limit is never silently ignored. For editor autocompletion, export the schema:

```bash
agentsec schema policy > agentsec.schema.json
```

## 2. Run

```bash
agentsec test                                  # uses ./agentsec.yaml
agentsec test --policy path/to/agentsec.yaml   # or -p
agentsec test -v                               # progress and per-finding detail
```

The terminal shows the counts and every finding, most severe first, then the report paths. Reports go to
`.agentsec/` (`--out` to change it): `report.json` and `report.html` by default.

## 3. Run less, or differently

```bash
agentsec test -s prompt_injection                      # one category
agentsec test -s secret_extraction/system_prompt       # one scenario
agentsec test -s prompt_injection -s secret_extraction # several (repeatable)
agentsec test --seed 42                                # different canaries and markers
agentsec test --fail-on high                           # only high and critical fail the run
agentsec test --fail-on none                           # never fail on findings
agentsec test -f json,html,markdown,sarif              # all report formats
agentsec test -A my_pack.py                            # load an attack pack for this run (see below)
```

`-s` takes category names or scenario ids, and only narrows down what the policy's `tests:` list already selects (all
categories when `tests:` is empty). Asking for something that was not built, a typo or a category missing from
`tests:`, fails with `error: no scenarios match --scenario <name>`. A name in `tests:` that does not exist fails with
`error: unknown test category '<name>'; available: ...`, which lists every valid name.

`-A` loads an attack pack's categories, but they only run when they are also listed in `tests:` (or `tests:` is
empty); otherwise the run silently ignores them. See [Attack packs](/docs/testing/attack-packs#load-it).

The same `--seed` with the same policy and agent build gives the same scenarios, which is what makes findings
reproducible.

## 4. Check a fix

```bash
agentsec replay .agentsec/report.json --policy agentsec.yaml                 # every finding
agentsec replay .agentsec/report.json --finding '<finding id>'               # one finding
agentsec replay .agentsec/report.json -s memory_poisoning/doc_instruction_marker
```

Replay rebuilds the same scenarios from the seed in the report, runs them against your current agent, and prints
REPRODUCED, NOT REPRODUCED, INCONCLUSIVE, ERROR or NEW for each. It writes its own report to
`.agentsec/replay/report.json`. Exit codes: `2` if a rerun errored, otherwise `1` if a finding reproduced or a new one
appeared, otherwise `2` if a rerun was inconclusive (it cannot prove a fix), otherwise `0`.

## 5. Compare two runs

```bash
agentsec test --out .agentsec/baseline
# ... change the agent ...
agentsec test --out .agentsec/current
agentsec compare .agentsec/baseline/report.json .agentsec/current/report.json --fail-on high
```

Exit code `1` means a new or worsened finding at or above `high`. See [Comparing runs](/docs/guide/compare).

## Expected output and exit codes

| Exit code | Meaning | Typical CI effect |
|---|---|---|
| `0` | No finding at or above `--fail-on` | Job passes |
| `1` | At least one finding at or above `--fail-on` | Job fails: findings |
| `2` | Configuration error, or every scenario errored | Job fails: setup problem, nothing was measured |

## Troubleshooting

| Message | Cause and fix |
|---|---|
| `error: cannot read policy file agentsec.yaml: [Errno 2] No such file or directory` | Run `agentsec init`, or pass `--policy` |
| `error: unknown key(s) in agent: foo (allowed: api_key_env, declare_tools, ...)` | A typo in the policy; the message lists valid keys |
| `error: agent.endpoint must start with http:// or https://` | Fix `agent.endpoint` |
| `error: unknown test category 'x'; available: ...` | A typo in the policy's `tests`, or a pack category whose pack is not loaded |
| `error: no scenarios match --scenario x` | `-s` named nothing that was built: a typo, or a category not listed in `tests:` |
| `Every scenario errored; is the agent running at ...?` | Start the agent or fix the endpoint; see [worked examples](/docs/results/interpreting#every-scenario-errored) |
| `` error: --judge needs a `judge:` section in the policy (endpoint, model, ...) `` | Add a `judge:` section or drop `--judge` |
| `error: --format must be a comma-separated list of: json, html, markdown, sarif` | Fix `-f` |
| 0 findings against a real agent, and it feels too good | See [a clean run that seems too good](/docs/results/interpreting#a-clean-run-against-a-real-agent-that-seems-too-good) |

## When to use the CLI

Use it whenever your agent has (or can be given) an HTTP endpoint: it needs no code, it is what the GitHub Action
runs, and it writes every report format. Use the [Python API](/docs/testing/python-api) instead when the agent
lives in your Python process, or the [pytest plugin](/docs/testing/pytest) when you want results as unit tests.
