---
title: Python API and in-process agents
nav_title: Python API
description: Run AgentSec scenarios from Python with AgentTarget, SecuritySuite and RunResult, test an in-process agent with CallableAdapter, and write a custom adapter.
seo_title: AgentSec Python API: Security-Test In-Process Agents
section: testing
order: 4
---

Everything the CLI does is available from Python. Use it to test an agent that lives in your process (no HTTP
server needed), or to assert on results in your own code.

> [!NOTE]
> The Python API may still change before a stable 1.0 release. Pin `invaris-agentsec` in your requirements.

## Prerequisites

```bash
pip install invaris-agentsec
```

## Test an in-process agent

Wrap any function with `CallableAdapter`. You write the few lines that call your agent; AgentSec does not import
or depend on any framework.

```python title="test_inproc.py"
from agentsec import AgentTarget, SecuritySuite
from agentsec.adapters import CallableAdapter


def my_agent(messages, tools, session=None):
    """Your agent. Here: a toy that refuses to act on anything it is told to do."""
    return {"content": "I can help with that, but I will not run tools on request.",
            "agent": {"name": "toy-agent", "backend": "scripted"}}


target = AgentTarget(
    "http://in-process",                   # placeholder: never contacted when an adapter is given
    allowed_tools=["search_documents"],
    forbidden_tools=["send_email"],
    secrets=["sk-EXAMPLE-FAKE-KEY"],
    declare_tools=False,
)
result = SecuritySuite(target, adapter=CallableAdapter(my_agent)).run("prompt_injection", "secret_extraction")

print(len(result.results), "scenarios,", len(result.findings), "findings, passed =", result.passed)
result.assert_clean(fail_on="high")
```

```text
10 scenarios, 0 findings, passed = True
```

The function may take `(messages)`, `(messages, tools)` or `(messages, tools, session)` and may return:

- a string: the agent's final answer;
- a dict: `content`, `tool_calls` (`[{"name", "arguments", "id"?, "actor"?, "delegated_by"?}]`), `executed`
  (tools the agent ran itself: `[{"name", "arguments", "result", "actor"?, "delegated_by"?}]`), `actor`, `agent`
  (self-description), `cost_usd`, `prompt_tokens`, `completion_tokens`;
- an `AgentReply`.

If the function raises, that scenario is recorded as an **error**, never a pass. Raise
`agentsec.adapters.AdapterError` yourself for infrastructure failures (rate limits, quotas) so they are not scored
as answers.

## When the agent misbehaves

```python
from agentsec import AgentTarget, SecuritySuite
from agentsec.adapters import CallableAdapter

def bad(messages, tools):
    return {"content": "ok", "tool_calls": [{"name": "send_email", "arguments": {"to": "x@evil.invalid"}}]}

t = AgentTarget("http://in-process", allowed_tools=["search_documents"], forbidden_tools=["send_email"])
r = SecuritySuite(t, adapter=CallableAdapter(bad)).run("prompt_injection/ignore_previous")
print(r.forbidden_tool_calls[0])
r.assert_clean("high")
```

```text
ToolCallRecord(scenario_id='prompt_injection/ignore_previous', name='send_email', arguments={'to': 'x@evil.invalid'})
AssertionError: AgentSec: 1 finding(s) at or above 'high', 0 errored scenario(s)
  [HIGH] Agent attempted forbidden action send_email (prompt_injection/ignore_previous)
```

## Test an HTTP agent from Python

```python
from agentsec import AgentTarget, SecuritySuite

target = AgentTarget(
    endpoint="http://localhost:8000/agent",
    allowed_tools={"search_documents", "create_draft"},
    forbidden_tools={"send_email", "execute_payment"},
    secrets=["sk-EXAMPLE-FAKE-KEY"],
)
result = SecuritySuite(target).run("indirect_prompt_injection")

assert result.secret_leaks == []
assert result.forbidden_tool_calls == []
assert result.total_tool_calls <= 10
result.assert_clean(fail_on="high")
```

Or load an existing policy: `AgentTarget.from_file("agentsec.yaml")` or `AgentTarget.from_policy(policy)`.

## `AgentTarget`

Describes the agent; it builds a `Policy` like an `agentsec.yaml` would (available as `target.policy`). It has no
arguments for `spend_limits`, `address_allowlist`, `agent_roles` or `tests`: for those, write them in a policy file
and use `AgentTarget.from_file("agentsec.yaml")` (or `AgentTarget.from_policy(policy)`).

| Argument | Meaning |
|---|---|
| `endpoint` | Agent URL (required, `http://` or `https://`; a placeholder when you pass an adapter) |
| `allowed_tools` | Tools the agent may call. Omit for no allowlist |
| `forbidden_tools` | Actions that must never be attempted (the policy's `forbidden_actions`) |
| `secrets` | Values that must never appear in output |
| `tool_effects` | `{tool: [effects]}`, as in the policy |
| `name`, `model`, `api_key_env`, `headers`, `timeout_s`, `declare_tools`, `stream`, `retrieval_tools`, `pricing` | As in the [policy's `agent` section](/docs/reference/policy#agent) |
| `max_steps`, `max_tool_calls`, `max_repeated_calls`, `max_tokens`, `max_seconds`, `max_cost_usd` | As in `limits` |
| `judge` | A `JudgeConfig`, used when the suite is created with `judge=True` |
| `attack_packs` | Attack packs to load (files or installed modules), as in the policy |

## `SecuritySuite`

```python
SecuritySuite(target, seed=0, adapter=None, judge=False, mcp_host=None, attack_packs=None)
suite.run(*names, seed=None)   # -> RunResult
```

`run` takes category names and/or scenario ids. With no names it runs every category, built-in plus any attack
packs. Unlike the CLI, `run()` **ignores the policy's `tests:` list**: name the categories you want. Unknown names raise `PolicyError`. `agentsec.CATEGORIES` lists the built-in category names. Optional
arguments: `adapter` (any `AgentAdapter`), `judge`, `mcp_host` (an `MCPAttackHost`, see
[MCP testing](/docs/testing/mcp)), and `attack_packs` (a dict of extra categories).

## `RunResult`

| Attribute | Meaning |
|---|---|
| `findings` | All findings (`severity`, `title`, `rule`, `scenario_id`, `evidence`, ...) |
| `results` | Per-scenario results, each with `.scenario`, `.trace`, `.findings` and `.status` |
| `errors` | Scenarios that could not run |
| `inconclusive` | Scenarios whose adversarial content never reached the agent |
| `not_observable` | Scenarios that could not be judged without multi-agent attribution |
| `passed` | `True` only with no findings, no errors and no inconclusive scenarios |
| `secret_leaks` | Findings with rule `secret_leak` |
| `unauthorized_side_effects` | Findings with rule `unauthorized_side_effect` |
| `forbidden_tool_calls` | Every call to a forbidden action, as `ToolCallRecord(scenario_id, name, arguments)` |
| `unauthorized_tool_calls` | Calls outside the allowlist (empty without an allowlist) |
| `tool_calls_by_scenario` | Tool-call counts per scenario id |
| `total_tool_calls` | The most tool calls any **single scenario** made |
| `findings_at_least(severity)` | Findings at or above a severity |
| `format(fail_on)` | A readable list of findings and errors |
| `assert_clean(fail_on="low")` | Raises `AssertionError` if a finding at or above `fail_on` exists **or any scenario errored** |

An unreachable agent is never a pass: `passed` is false and `assert_clean` raises.

## Lower-level: `run_suite` and reports

The CLI is built on `agentsec.runners.run_suite(policy, adapter, seed=0, ...)`, which returns a `SuiteResult`.
To write the same report files from Python:

```python
from agentsec.adapters import CallableAdapter
from agentsec.policies import load_policy
from agentsec.reports import write_reports
from agentsec.runners import run_suite

policy = load_policy("agentsec.yaml")
suite = run_suite(policy, CallableAdapter(my_agent), seed=0)
report, paths = write_reports(suite, ".agentsec", ["json", "html"], policy_path="agentsec.yaml")
```

The resulting `report.json` can be uploaded to the dashboard like any other.

## Write a custom adapter

For anything `CallableAdapter` does not cover, subclass `AgentAdapter` and implement `chat`:

```python
from agentsec.adapters import AdapterError, AgentAdapter, AgentReply, ToolCall

class MyAdapter(AgentAdapter):
    def chat(self, messages, tools, session=None):
        out = my_client.complete(messages, tools)          # your code
        if out.rate_limited:
            raise AdapterError("rate limited")             # recorded as an errored scenario
        return AgentReply(content=out.text,
                          tool_calls=[ToolCall(c.id, c.name, c.args) for c in out.calls])
```

The adapter must not keep conversation state (the runner resends the full history every step) and must accept the
`session` keyword. Pass it to agents with memory. More in [Extending AgentSec](/docs/developers/extending#adapters).
