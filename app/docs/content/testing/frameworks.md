---
title: Agent frameworks and simulated tools
nav_title: Agent frameworks
description: Test LangChain, LangGraph, CrewAI, AutoGen, OpenAI Agents SDK, Google ADK and smolagents agents with AgentSec, using LangChainAdapter, CallableAdapter and the in-process ToolHost that simulates tools.
seo_title: Security Testing for LangChain, CrewAI and AutoGen Agents
seo_description: Test LangChain, LangGraph, CrewAI, AutoGen, OpenAI Agents SDK, Google ADK and smolagents agents with AgentSec's LangChainAdapter, CallableAdapter and ToolHost.
section: testing
order: 6
---

Most agents are built with a framework that runs its own tool loop. AgentSec has three ways in, none of which
needs an HTTP server, and none of which makes AgentSec depend on the framework.

| Your agent | Use |
|---|---|
| LangChain or LangGraph | `LangChainAdapter` |
| Any framework that runs its own tool loop | `CallableAdapter` + `ToolHost` (AgentSec supplies the tool results) |
| Any agent you can call as a function and that reports what it did | `CallableAdapter` alone |

## How tools are simulated

AgentSec never executes a real tool. When it drives the tool loop (HTTP agents with declared tools), it answers
each tool call itself. When your framework drives the loop, the same answers come from a **host** the framework's
tools call into:

- `ToolHost`, in-process, for frameworks;
- `MCPAttackHost`, over MCP, for agents connected with `--mcp-listen` (see [MCP testing](/docs/testing/mcp)).

Either way, scenario tools (`agent.retrieval_tools`, or every allowed tool when that is not set) return the
scenario's adversarial content, other tools return
`OK (simulated by AgentSec sandbox; no real action was taken)`, and every call is recorded as executed by the
agent, before the reply it led to.

## LangChain and LangGraph

```python
from agentsec.api import AgentTarget, SecuritySuite
from agentsec.integrations import LangChainAdapter

agent = build_my_agent()          # a LangGraph graph, create_react_agent(...), create_agent(...) or AgentExecutor

target = AgentTarget("http://in-process",          # placeholder, never contacted
                     allowed_tools=["search_documents"], forbidden_tools=["send_email"],
                     secrets=["sk-test-123"], declare_tools=False)
result = SecuritySuite(target, adapter=LangChainAdapter(agent)).run()
result.assert_clean(fail_on="high")
```

What the adapter does:

- calls `agent.invoke({"messages": [...]})` (LangGraph) or `agent.invoke({"input": ...})` (`AgentExecutor`),
  whichever the agent accepts;
- passes AgentSec's session id as `config["configurable"]["thread_id"]`, so a checkpointer keeps memory per
  simulated user (memory scenarios rely on this; disable with `use_session_as_thread=False`);
- reports the tool calls the agent actually made (from the returned messages or `intermediate_steps`) as executed
  calls, and reads token usage from `usage_metadata` when present.

> [!WARNING]
> Here the framework runs the tools, so **your tools must be sandboxed test doubles**. A `send_email` tool in a
> test agent must not send real email.

Adversarial content reaches such an agent only through the user message and whatever your test doubles return.
To have AgentSec deliver poisoned tool results, use a `ToolHost` (below), `--mcp-listen`, or expose the agent over
HTTP with tools declared.

## Any other framework: `ToolHost` {#any-other-framework}

Give the framework tools that call AgentSec's in-process `ToolHost`. The host answers each call from the running
scenario and records it, so every evaluator applies:

```python
from agentsec.adapters import CallableAdapter
from agentsec.integrations import ToolHost
from agentsec.policies import load_policy
from agentsec.runners import run_suite

policy = load_policy("agentsec.yaml")            # with agent.declare_tools: false
host = ToolHost(policy)
tools = {name: host.tool(name) for name in host.tool_names()}   # plain callables: fn(**arguments) -> str
agent = build_my_agent(tools)                     # wrap them as the framework's tools

suite = run_suite(policy, CallableAdapter(lambda messages: agent.run(messages[-1]["content"])), host=host)
```

- `host.tool_names()` lists the policy's allowed tools, forbidden actions (as decoys) and retrieval tools.
- `host.tool(name)` returns a callable; `host.tool(name, actor="researcher")` binds it to one agent of a team so
  calls are attributed.
- The host only sees calls the framework **executes**: a call to a tool the framework does not have is refused by
  the framework and never reaches the host.

Working wrappers for LangChain, LangGraph, CrewAI, AutoGen AgentChat, the OpenAI Agents SDK, Google ADK and
smolagents are in the engine repository under
[benchmarks/framework-compat/frameworks](https://github.com/invarislabs/invaris-agentsec/tree/main/benchmarks/framework-compat/frameworks),
with results in [MATRIX.md](https://github.com/invarislabs/invaris-agentsec/blob/main/benchmarks/framework-compat/MATRIX.md).
They were run with a scripted model, not an LLM.

## Plain `CallableAdapter`

If your agent can return what it did, wrap it directly (see [Python API](/docs/testing/python-api)):

```python
def my_agent(messages, tools):
    answer = run_my_framework_agent(messages)
    return {"content": answer.text,
            "executed": [{"name": c.name, "arguments": c.args, "result": c.output} for c in answer.tool_calls]}
```

## Other routes

- Expose the agent through an OpenAI-compatible HTTP endpoint (many frameworks and servers can) and use the CLI.
- Make it use MCP servers and test it with [`--mcp-listen`](/docs/testing/mcp#testing-an-agent-that-uses-mcp).

## What has been verified

LangGraph (`create_react_agent`, with and without a checkpointer) with a scripted model, and the framework wrappers
above with a scripted model. Real LLM-backed framework agents, `AgentExecutor` itself, and other LangChain
versions than the one in the engine's CI have not been verified.
