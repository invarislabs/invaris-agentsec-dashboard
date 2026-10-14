---
title: Data models
description: The AgentSec dashboard's database tables (users, projects, memberships, upload tokens, reports) and the engine's core data models (Policy, Scenario, Trace, Finding, ScenarioResult) and how they map to JSON.
section: developers
order: 3
---

## Dashboard database

Defined in `app/models.py` (SQLAlchemy 2), migrated with Alembic. Ids are 32-character hex UUIDs, except `memberships.id`, an auto-increment integer.

```diagram
 users 1 ──< memberships >── 1 projects 1 ──< api_tokens
   │                              │
   └── owner_id ──────────────────┤
                                  └──< reports (token_id → api_tokens, ON DELETE SET NULL)
```

### `users`

| Column | Notes |
|---|---|
| `id` | Primary key |
| `github_id` | Unique; null for development sign-ins |
| `login` | Unique. If a GitHub login is reused by another account, the old one is renamed `<login>-<github_id>` |
| `name`, `avatar_url` | From GitHub |
| `plan` | `free` today |
| `created_at`, `last_login_at` | |

### `projects` and `memberships`

| Table | Columns |
|---|---|
| `projects` | `id`, `slug` (unique), `name`, `owner_id` → users (cascade), `created_at` |
| `memberships` | `id`, `project_id`, `user_id` (unique together), `role` (`owner`), `created_at` |

Access checks join through `memberships`; a project has one membership (its owner) until team members exist.
Deleting a project cascades to its memberships, tokens and reports.

### `api_tokens`

| Column | Notes |
|---|---|
| `project_id` | The only project it can upload to |
| `name` | Label |
| `prefix` | First 12 characters, for display |
| `token_hash` | SHA-256 of the token, unique. The token itself is never stored |
| `created_by`, `created_at`, `last_used_at`, `revoked_at` | Revoked tokens stay as rows with `revoked_at` set |

### `reports`

One uploaded `report.json` or `mcp-report.json`. Summary columns are copied out at upload so lists and the history
chart never decompress the document. Index: `(project_id, uploaded_at)`.

| Column | Source |
|---|---|
| `project_id`, `token_id`, `uploaded_at` | The upload |
| `kind` | `test` or `mcp_scan` |
| `name`, `target` | Agent or server name; endpoint or scan target |
| `generated_at`, `agentsec_version`, `seed`, `policy_path`, `policy_sha256` | From the report |
| `scenarios`, `passed`, `with_findings`, `errors`, `not_observable` | `summary` |
| `inconclusive` | Scenarios not delivered (migration 0002 back-fills old rows); null for MCP scans |
| `findings`, `critical`, `high`, `medium`, `low` | Counts |
| `branch`, `commit`, `ci_url`, `repository`, `label` | Upload metadata |
| `traces_stripped` | Uploaded with `--no-traces` |
| `size_bytes` | Uncompressed size |
| `content` | The full report JSON, gzip-compressed |

## Engine data models

### `Policy` (`agentsec/policies/schema.py`)

`Policy(agent: AgentConfig, allowed_tools, forbidden_actions, secrets, limits: Limits, spend_limits, address_allowlist,
tool_effects, agent_roles, tests, attack_packs, judge: JudgeConfig, version, source_sha256)`. Built by `load_policy`
/ `parse_policy` (strict: unknown keys raise `PolicyError`), or by `AgentTarget` in Python.
`to_report_dict()` is what lands in `run_config.policy`, without secret values.

### `Scenario` (`agentsec/attacks/base.py`)

The fields are listed in [Attack packs](/docs/testing/attack-packs#scenario-fields). Related: `Followup` (later
conversations), `AttackGoal`, `ScenarioContext` (seeded helpers), and the `ToolResponder` signature
`(tool_name, arguments, call_index) -> str`.

### `Trace` and `Event` (`agentsec/traces/schema.py`)

A trace has `scenario_id`, `outcome`, `limit`, `error`, `duration_s`, `usage` and ordered `events`. An event has
`seq`, `type`, `t_ms` and, depending on type, `content`, `tool_name`, `tool_call_id`, `arguments`, `meta`.
`trace.of_type("tool_call")` filters events. JSON shape: [Report format](/docs/reference/report-format#traces).

### `Finding` (`agentsec/evaluators/base.py`)

`Finding(rule, scenario_id, category, severity, title, policy_violated, observed_action, input, evidence, remediation,
key="", source="deterministic", confidence=None, sensitive=[])`. Its id is `scenario_id:rule[:key]`. Values in
`sensitive` are masked in reports. `excerpt(trace, *seqs)` builds evidence from trace events.

### `ScenarioResult` and `SuiteResult` (`agentsec/runners/local.py`)

`ScenarioResult(scenario, trace, findings)` with the computed `status`; `SuiteResult(policy, seed, results, warnings)`
with `findings`. The Python API wraps a `SuiteResult` in `RunResult`.

### Adapter types (`agentsec/adapters/base.py`)

`AgentReply(content, tool_calls: [ToolCall], prompt_tokens, completion_tokens, cost_usd, executed, actor, agent)` and
`ToolCall(id, name, arguments, actor=None, delegated_by=None)`. `AdapterError` marks a scenario as errored.

## How the JSON fits together

| JSON | Produced from |
|---|---|
| `report.json` top level and `summary` | `agentsec/reports/json_report.py` from a `SuiteResult` |
| `findings[]` | `Finding` objects, masked, with `owasp` added by `agentsec/owasp.py` |
| `scenarios[].status` | `ScenarioResult.status` |
| `scenarios[].delivery`, `attack_goals` | `agentsec/evaluators/goals.py` |
| Dashboard run entry | `agentsec.dashboard.index.summarize_entry` plus upload columns (`app/reports.py:entry`) |
| Dashboard insights | `agentsec.dashboard.insights.insights` (filled in by `app/insights.py` for older engines) |
