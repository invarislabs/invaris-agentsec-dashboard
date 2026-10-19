---
title: Policy reference (agentsec.yaml)
nav_title: Policy reference
description: Every key of the AgentSec policy file - agent, allowed_tools, forbidden_actions, tool_effects, agent_roles, secrets, limits, spend_limits, address_allowlist, tests, attack_packs and judge - with defaults and validation rules.
seo_title: agentsec.yaml Policy Reference: Tools, Secrets and Limits
seo_description: Every key of the AgentSec policy file: agent, allowed and forbidden tools, tool_effects, agent_roles, secrets, limits, spend limits, tests, packs and judge.
section: reference
order: 2
---

A policy is a YAML file, `agentsec.yaml` by default. It says what the agent may do and how AgentSec should test
it. **Unknown keys are rejected** so typos are caught. Get the machine-readable schema with
`agentsec schema policy`.

## Full example

```yaml title="agentsec.yaml"
version: "1"

agent:
  name: support-agent
  endpoint: http://localhost:8000/v1/chat/completions
  model: agentsec-target
  api_key_env: SUPPORT_AGENT_TOKEN
  headers:
    X-Env: test
  timeout_s: 30
  declare_tools: true
  stream: false
  retrieval_tools: [search_documents]
  pricing:
    input_per_1k: 0.003
    output_per_1k: 0.015

allowed_tools: [search_documents, create_draft]
forbidden_actions: [send_email, reveal_credentials, execute_payment]

tool_effects:
  search_documents: [read, untrusted_content]
  create_draft: [write]

secrets:
  - sk-EXAMPLE-FAKE-KEY
  - env:DB_TEST_PASSWORD

limits:
  max_steps: 12
  max_tool_calls: 10
  max_repeated_calls: 3
  max_tokens: 20000
  max_seconds: 120
  max_cost_usd: 0.50

tests:
  - prompt_injection
  - indirect_prompt_injection
  - secret_extraction
  - unauthorized_tool_use
  - tool_output_poisoning
  - unsafe_retrieved_documents
  - loop_and_budget_limits
  - memory_poisoning

attack_packs: []

judge:                      # only used with agentsec test --judge
  endpoint: http://localhost:11434/v1/chat/completions
  model: my-local-judge
  checks: [goal_hijack, paraphrased_leak]
  min_confidence: 0.7
  severity: medium
```

## Top-level keys

| Key | Required | Default | Meaning |
|---|---|---|---|
| `version` | no | `"1"` | Schema version. Only `"1"` is supported |
| `agent` | yes | | How to reach the agent |
| `allowed_tools` | no | none | Tools the agent may call. Omitted: no allowlist is enforced. `[]`: any tool call is a violation |
| `forbidden_actions` | no | `[]` | Actions that must never be attempted. Also used as names in attack payloads and offered as decoy tools |
| `tool_effects` | no | `{}` | What each tool's call does and what its result contains. See [below](#tool-effects) |
| `agent_roles` | no | `{}` | Multi-agent systems: each agent's authority. See [below](#agent-roles) |
| `secrets` | no | `[]` | Values that must never appear in output |
| `limits` | no | see below | Operating budgets |
| `spend_limits` | no | none | Caps on tools that move money |
| `address_allowlist` | no | none | Deny-by-default destination check for tools that move money |
| `tests` | no | all categories | Which attack categories to run |
| `attack_packs` | no | `[]` | Extra categories from local files or installed packages |
| `judge` | no | none | The optional model-assisted judge |

## `agent`

| Key | Default | Meaning |
|---|---|---|
| `name` | required | Label used in reports and to group runs in the dashboard |
| `endpoint` | required | Full URL receiving POST requests; must start with `http://` or `https://` |
| `model` | `agentsec-target` | Sent as `model` in each request |
| `api_key_env` | none | Name of an environment variable holding a bearer token; the value is never stored |
| `headers` | `{}` | Extra HTTP headers (strings) |
| `timeout_s` | `30` | Per-request timeout (at least 0.1). A timeout errors that scenario |
| `declare_tools` | `true` | Advertise allowed tools and forbidden decoys. `false` for agents that manage their own tools |
| `stream` | `false` | Request and assemble a server-sent-events response |
| `retrieval_tools` | `[]` | Tools whose results carry adversarial content. Empty: every allowed tool does |
| `pricing` | none | `input_per_1k` and `output_per_1k` (numbers): compute cost from tokens when the agent reports none |

## `limits`

| Key | Default | Enforced |
|---|---|---|
| `max_steps` | `12` | Live: model calls per conversation |
| `max_tool_calls` | `10` | Live: the call that would exceed it is recorded, flagged and not executed |
| `max_repeated_calls` | `3` | After the run: identical calls with identical arguments |
| `max_tokens` | none | After the run: total prompt and completion tokens the agent reports |
| `max_seconds` | none | Live between steps, and after the run |
| `max_cost_usd` | none | After the run, when cost is known (unknown cost is skipped, never guessed) |

Integer limits must be whole numbers of at least 1; seconds and cost at least 0. Step and tool-call limits apply
per conversation, so a memory scenario's follow-up gets a fresh budget.

## `secrets`

Each entry is a literal value or `env:NAME`, read from the environment at run time (unset variables are skipped).
Secrets are never written to reports; the policy section records only how many there were, and any secret found in
output is masked as its first four and last two characters (values of 8 characters or fewer are fully masked). Besides your list, AgentSec flags common credential
formats: AWS access keys, `sk-` API keys, GitHub tokens, private key headers and long bearer tokens.

Use synthetic credentials only. Give the agent the same synthetic value you list here.

## `tool_effects` {#tool-effects}

What each tool's call actually *does*, independent of whether it is allowed. `allowed_tools` answers "can the agent
ever call this tool"; `tool_effects` lets AgentSec ask "did *this task* authorize *this effect*".

```yaml
tool_effects:
  lookup_account: [read, private_data]
  read_page: [read, untrusted_content]
  send_customer_email: [external_communication]
  install_package: [write, execute, network]
  run_tests: [execute]
```

Tags are free-form; the scenarios use `read`, `write`, `delete`, `execute`, `network`, `external_communication`,
`financial`, `credential_access`, `git_mutation`, `deployment`, `persistence`, `delegation`,
`browser_state_change`, `system_change`. Two tags describe a tool's **result**:

- `private_data`: the result holds data that must not leave the trust boundary (`credential_access` counts the same);
- `untrusted_content`: the result holds text an outsider can write (web pages, emails, tickets, PR comments).

A tool missing from `tool_effects` is **unknown**, never assumed read-only. The checks that read it (task-scoped
authorization, data flow, claims versus trace, cross-account severity, multi-agent roles) stay silent for it, and
`action_without_authorization`, `deceptive_action_report` and `dangerous_composition` build no scenarios without
suitable entries. High-impact effects (`financial`, `credential_access`, `deployment`, `delete`, `git_mutation`)
make authority findings critical.

## `agent_roles` {#agent-roles}

```yaml
agent_roles:
  planner:
    effects: [read, write, delegation]
    can_delegate_to: [researcher, executor]
  researcher:
    effects: [read]
    tools: [search_docs]
```

| Key | Meaning |
|---|---|
| `effects` | The ceiling of what this agent may do itself; delegating requires `delegation` |
| `tools` | Optional: restricts the agent to these tool names too |
| `can_delegate_to` | Optional: agents it may hand work to; each must be a declared role |

Work an agent delegates never carries more authority than it holds. Without `agent_roles`, multi-agent checks stay
silent and `multi_agent_delegation` builds no scenarios. See [Multi-agent testing](/docs/testing/multi-agent).

## `spend_limits`

| Key | Default | Meaning |
|---|---|---|
| `tools` | required | Tool names this applies to (at least one) |
| `amount_field` | `amount` | The argument holding the amount |
| `max_transaction` | none | Flags a single call over this amount (`spend_limit_exceeded`, critical) |
| `max_total` | none | Flags once when the running total first exceeds this (`spend_total_exceeded`, high) |
| `currency` | `USD` | Label only |

At least one of `max_transaction` / `max_total` is required. A missing or non-numeric amount is ignored, not zero.

## `address_allowlist`

| Key | Default | Meaning |
|---|---|---|
| `tools` | required | Tool names this applies to (at least one) |
| `address_field` | `to` | The argument holding the destination |
| `addresses` | required | Allowed values (at least one); anything else is `address_not_allowlisted` (critical) |
| `case_sensitive` | `false` | Whether matching is case-sensitive |

## `tests`

The categories to run. Empty runs all of them. Valid built-in names: `prompt_injection`,
`indirect_prompt_injection`, `secret_extraction`, `unauthorized_tool_use`, `tool_output_poisoning`,
`unsafe_retrieved_documents`, `loop_and_budget_limits`, `memory_poisoning`, `action_without_authorization`,
`dangerous_composition`, `deceptive_action_report`, `identity_and_session_confusion`, `multi_agent_delegation`,
plus any category from a loaded attack pack. Anything else is an error that lists the valid names. Drop
`memory_poisoning` if your agent has no long-term memory: it passes trivially but doubles the requests.

## `attack_packs`

A list of attack pack specs: a path to a `.py` file (resolved from the **current directory**) or an installed
module name. A pack's categories run only if listed in `tests` (or `tests` is empty). See
[Attack packs](/docs/testing/attack-packs).

## `judge`

Read only by `agentsec test --judge`.

| Key | Default | Meaning |
|---|---|---|
| `endpoint` | required | OpenAI-compatible chat-completions URL (`http://` or `https://`) |
| `model` | `judge` | Sent as `model` |
| `api_key_env` | none | Environment variable holding a bearer token |
| `headers` | `{}` | Extra HTTP headers |
| `timeout_s` | `60` | Per-request timeout |
| `checks` | both built-ins | `goal_hijack`, `paraphrased_leak`, and checks provided by attack packs |
| `min_confidence` | `0.7` | Verdicts below this are ignored (0 to 1) |
| `severity` | `medium` | `low`, `medium` or `high`. `critical` is not allowed |

## Tips

- List every real tool in `allowed_tools`; the allowlist check only runs when the key is present.
- Use the real names of dangerous actions in `forbidden_actions`; they appear in attack payloads.
- Set `retrieval_tools` when only some tools return untrusted content, so writes are not fed attack payloads.
- Keep limits realistic; a limit below normal behaviour produces findings on benign runs.
- Declare `tool_effects` for write, delete, execute and financial tools to enable the authority categories.
