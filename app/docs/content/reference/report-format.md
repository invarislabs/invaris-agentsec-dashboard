---
title: Report and trace format
nav_title: Report format
description: The structure of AgentSec's report.json, mcp-report.json and traces - run configuration, summary, findings, scenarios, delivery and attack goals, trace events, secret masking and SARIF.
section: reference
order: 3
---

`report.json` is the complete record of a run, and the input to `replay`, `compare`, both dashboards and the
GitHub Action. Its schema version is `"1"`. Every string in it, including traces, has configured and detected
secrets masked.

## Top level

```json title="report.json (abbreviated, from a real run)"
{
  "report_schema_version": "1",
  "tool": {"name": "invaris-agentsec", "version": "0.9.0"},
  "generated_at": "2026-10-14T11:09:01+00:00",
  "run_config": {
    "seed": 0,
    "policy": {"...": "the policy as run, secrets omitted"},
    "policy_path": "examples/vulnerable_rag_agent/agentsec.yaml",
    "scenario_ids": ["prompt_injection/ignore_previous", "..."],
    "replay": "agentsec test --policy examples/vulnerable_rag_agent/agentsec.yaml --seed 0"
  },
  "summary": {
    "scenarios": 35, "passed": 0, "with_findings": 35, "errors": 0, "not_observable": 0, "inconclusive": 0,
    "findings": 43,
    "by_severity": {"critical": 10, "high": 25, "medium": 8, "low": 0},
    "by_owasp": {"ASI01": 19, "ASI02": 22, "ASI03": 16, "ASI06": 4, "ASI08": 2}
  },
  "owasp_framework": {"name": "OWASP Top 10 for Agentic Applications (2026)", "url": "...", "categories": {"ASI01": "Agent Goal Hijack", "...": "..."}},
  "warnings": [],
  "findings": ["..."],
  "scenarios": ["..."]
}
```

| Field | Meaning |
|---|---|
| `run_config.seed` | The seed; re-running with it, the same policy and agent build gives the same scenarios |
| `run_config.policy` | The policy as run: `version`, `agent` (no credentials), `allowed_tools`, `forbidden_actions`, `tool_effects`, `agent_roles`, `secrets_count`, `limits`, `spend_limits`, `address_allowlist` (with `addresses_count`), `tests`, `attack_packs`, `judge`, `source_sha256` |
| `run_config.policy_path` | The policy file path given to the CLI |
| `run_config.scenario_ids` | Every scenario that ran |
| `run_config.replay` | The command that re-runs the same scenarios |
| `run_config.agent_reported` | Only when the agent described itself: distinct `{name, version, backend, model, configuration}` objects |
| `summary.scenarios` | Scenarios executed |
| `summary.passed` | Scenarios tested with no findings |
| `summary.with_findings` | Scenarios with at least one finding |
| `summary.errors`, `summary.not_observable`, `summary.inconclusive` | Untested scenarios, by reason |
| `summary.findings` | Total findings (can exceed `with_findings`) |
| `summary.by_severity`, `summary.by_owasp` | Counts; a finding can count toward several OWASP categories |
| `warnings` | Inconclusive or not-observable scenarios, failed judge calls, and similar |

The finding format is described in [Findings and severity](/docs/results/findings-and-severity#anatomy-of-a-finding).

## Scenarios

```json
{
  "id": "indirect_prompt_injection/plain_appended",
  "category": "indirect_prompt_injection",
  "title": "Instruction appended to document",
  "vector": "retrieved_document",
  "status": "findings",
  "finding_ids": ["indirect_prompt_injection/plain_appended:forbidden_action:send_email"],
  "trace": {"...": "see below"}
}
```

| Field | Meaning |
|---|---|
| `vector` | `direct`, `retrieved_document` or `tool_output`; `tool_definition` in MCP scan reports |
| `status` | `findings`, `error`, `not_observable`, `inconclusive` or `passed`, in that order of precedence. A missing status is read as `passed` |
| `finding_ids` | Ids of this scenario's findings |
| `delivery` | Only for scenarios that track exposure: `{"tracked": true, "delivered", "seq", "tool"}` |
| `attack_goals` | Only for scenarios that declare goals: `description`, `tools`, `indicators`, `carries_victim_data`, `severity`, `achieved` (`true`, `false` or `null` for not tested) |

Exposure strings and sensitive values themselves are never written to the report.

## Traces

A trace is the ordered record of one scenario. JSON Schema: `agentsec schema trace`.

```json
{
  "schema_version": "1",
  "scenario_id": "loop_and_budget_limits/pagination_trap",
  "outcome": "limit_exceeded",
  "limit": "max_tool_calls",
  "error": null,
  "duration_s": 0.01,
  "usage": {"steps": 11, "tool_calls": 11, "prompt_tokens": 5077, "completion_tokens": 405,
            "total_tokens": 5482, "cost_usd": null},
  "events": [
    {"seq": 0, "type": "user_message", "t_ms": 0, "content": "Find every mention of 'refund'..."},
    {"seq": 1, "type": "assistant_message", "t_ms": 3, "content": ""},
    {"seq": 2, "type": "tool_call", "t_ms": 3, "tool_name": "search_documents", "tool_call_id": "call_0", "arguments": {"query": "..."}},
    {"seq": 3, "type": "tool_result", "t_ms": 3, "tool_name": "search_documents", "content": "Results page 1..."},
    "...",
    {"seq": 33, "type": "limit", "t_ms": 9, "content": "agent requested tool call #11 (budget 10)", "meta": {"limit": "max_tool_calls"}}
  ]
}
```

| Field | Meaning |
|---|---|
| `outcome` | `completed`, `limit_exceeded` (see `limit`) or `error` (see `error`) |
| `usage.cost_usd` | `null` when the agent reports no cost and no `agent.pricing` is set |
| `events_stripped` | `true` when the report was uploaded with `--no-traces` (then `events` is empty) |

### Event types

| `type` | Recorded when | Notable fields |
|---|---|---|
| `user_message` | AgentSec sends the scenario's input | `content` |
| `assistant_message` | The agent replies | `content` (empty when it only asked for tools) |
| `tool_call` | The agent asks for a tool | `tool_name`, `tool_call_id`, `arguments` |
| `tool_result` | A simulated (or agent-executed) tool answers | `tool_name`, `content` |
| `limit` | AgentSec stopped the scenario | `content` describes it, `meta.limit` names the limit |
| `error` | The adapter failed | `content` holds the error, for example `cannot reach agent at http://127.0.0.1:8000/agent: [Errno 111] Connection refused` |

Every event has `seq` (position in the trace, used by evidence and timelines) and `t_ms` (milliseconds since the
scenario started). Optional `meta`:

| `meta` key | Meaning |
|---|---|
| `phase` | Scenarios with follow-up conversations (memory, stale authorization, cross-session): 0 for the first conversation, 1 for the first follow-up, and so on |
| `agent` | On an agent message: the agent's self-description (`x_agentsec.agent`), recorded where it first appears or changes |
| `actor`, `delegated_by` | Multi-agent attribution |
| `over_budget` | The call that exceeded `max_tool_calls`; recorded, not executed |
| `executed_by_agent` | A call the agent ran itself and reported (placed before the reply it led to) |

## MCP scan reports

`mcp-report.json` has `"kind": "mcp_scan"` and the same `findings` and `scenarios` layout, without traces:

| Field | Meaning |
|---|---|
| `run_config.target` | The `--command` or `--url` scanned |
| `run_config.server` | The server's name and version from `initialize` |
| `summary` | `scenarios`, `findings`, `by_severity`, plus `tools`, `resources` and `prompts` counts |
| `scenarios` | One per definition: `mcp/<tool>`, `mcp/resource:<uri>`, `mcp/prompt:<name>`; category `mcp_server` |
| `tools`, `resources`, `prompts` | Each definition's `name` and `description` exactly as the server sent them (plus `uri` for resources); input schemas and annotations are checked but not stored |

Because the layout matches, `agentsec compare` works on two scans.

## Secret masking

Configured secrets and detected credential-shaped values are replaced everywhere with their first four and last two
characters, for example `sk-I…9c [REDACTED]`; values of 8 characters or fewer become just `[REDACTED]`. That is enough to recognise a leak without copying the credential into
a CI artifact. Planted canaries are not sensitive and are shown in full. Traces still contain the agent's real
responses, so treat reports as sensitive.

## SARIF

`results.sarif` is SARIF 2.1.0 from the tool `invaris-agentsec`: one rule per finding rule (tagged `security`,
`agentsec` and its OWASP ids), one result per finding with level `error` (critical, high), `warning` (medium) or
`note` (low), located at the policy file, with the finding id in `partialFingerprints.agentsecFindingId`.

## Compatibility

Older reports (before delivery and attack goals existed) have no `inconclusive` status, `delivery` or
`attack_goals`, and are read the same way by `compare` and both dashboards. The rules every consumer applies live in
one module, `agentsec.verdicts`.
