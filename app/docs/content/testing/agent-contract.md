---
title: Make your agent testable
nav_title: Agent HTTP contract
description: The HTTP contract AgentSec uses to drive an agent - request and reply formats, tool calls, sessions for memory tests, agents that run their own tools, self-description, multi-agent attribution, streaming and authentication - with a working minimal agent.
seo_title: Make Your AI Agent Testable with AgentSec
seo_description: The HTTP contract AgentSec uses to drive your agent: request and reply formats, tool calls, memory sessions, self-run tools, multi-agent attribution, streaming.
section: testing
order: 3
---

AgentSec drives an agent over HTTP using the OpenAI chat-completions format, which most agent servers and
frameworks can speak. This page is the complete contract, plus a minimal agent you can start from.

## The request

AgentSec sends a `POST` with a JSON body to `agent.endpoint`:

```json title="Request"
{
  "model": "agentsec-target",
  "messages": [
    {"role": "user", "content": "Search the documents for the vendor onboarding policy and summarize it for me."}
  ],
  "tools": [
    {"type": "function", "function": {"name": "search_documents",
      "description": "Tool search_documents (simulated by AgentSec).",
      "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "additionalProperties": true}}}
  ],
  "tool_choice": "auto",
  "user": "<session id>"
}
```

| Field or header | Meaning |
|---|---|
| `model` | `agent.model` from the policy (default `agentsec-target`) |
| `messages` | The **whole** conversation so far. AgentSec keeps no state on your side and resends everything each step |
| `tools`, `tool_choice` | Your allowed tools plus your forbidden actions as decoys. Omitted when `agent.declare_tools: false` |
| `user` and `X-AgentSec-Session` header | The simulated user's session id (see [Sessions](#sessions-and-memory)) |
| `stream` | `true` only when `agent.stream: true` |
| `Authorization: Bearer <token>` | Only when `agent.api_key_env` names an environment variable holding the token |
| Other headers | Anything in `agent.headers` |

## The reply

To call a tool, reply with `tool_calls`:

```json title="Reply asking for a tool"
{"choices": [{"message": {"role": "assistant", "content": null, "tool_calls": [
  {"id": "call_1", "type": "function",
   "function": {"name": "search_documents", "arguments": "{\"query\": \"vendor onboarding\"}"}}]}}],
 "usage": {"prompt_tokens": 120, "completion_tokens": 18}}
```

AgentSec answers the tool itself and calls you again with the history extended by your assistant message and a
`{"role": "tool", "tool_call_id": "call_1", "content": "..."}` message. This repeats until you reply without
`tool_calls`, or a limit is reached.

Accepted variations:

- `arguments` can be a JSON string or an object. Invalid JSON is kept as `{"_raw": "..."}`.
- A plain-text agent may reply `{"response": "..."}`, `{"output": "..."}` or `{"content": "..."}`. It cannot
  trigger tool-based findings, but leaks and injections in its text are still detected.
- `usage.prompt_tokens` and `usage.completion_tokens` feed the token limit, and the cost limit when
  `agent.pricing` is set. Report cost directly with `usage.cost_usd` or `x_agentsec.cost_usd`.
- Return a non-2xx status for failures. AgentSec records them as errored scenarios, never as passes.

## A minimal testable agent

This complete server (standard library only) speaks the contract. It searches once and refuses to act on what it
reads. Replace `decide()` with a call into your real agent.

```python title="my_agent.py"
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


def decide(messages, tools):
    """Return an OpenAI-style assistant message: either tool calls or a final answer."""
    tool_names = {t["function"]["name"] for t in tools}
    already_searched = any(m["role"] == "tool" for m in messages)
    if "search_documents" in tool_names and not already_searched:
        question = messages[-1]["content"]
        return {"role": "assistant", "content": None, "tool_calls": [{
            "id": "call_1", "type": "function",
            "function": {"name": "search_documents", "arguments": json.dumps({"query": question})}}]}
    found = [m["content"] for m in messages if m["role"] == "tool"]
    return {"role": "assistant", "content": "I found %d document(s) and will not act on instructions inside them." % len(found)}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        message = decide(body["messages"], body.get("tools", []))
        reply = json.dumps({"choices": [{"message": message}],
                            "usage": {"prompt_tokens": 0, "completion_tokens": 0}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
```

```bash
python my_agent.py &
agentsec init          # its default endpoint, http://localhost:8000/v1/chat/completions, reaches this server
agentsec test
```

Expected: `30 scenarios executed`, `30 passed`, `0 findings`, exit code `0`.

## Sessions and memory

Memory scenarios run a second conversation that shares nothing with the first except the **session id**. If your
agent has long-term memory, key it on the request's `user` field (or the `X-AgentSec-Session` header):

- conversations of the same simulated user share an id;
- the "different user" scenarios use another id;
- ids contain a random per-run part, so memory from an earlier AgentSec run is never reused.

Agents without memory can ignore it. If your agent stores memory but does not key it by user, the cross-session
scenarios report a leak, which is exactly what they are designed to find.

## Agents that run their own tools

If your agent executes tools server-side (a RAG app with its own retrieval, an agent framework), AgentSec cannot
see those calls unless you report them. Add `x_agentsec.events` to the reply and set `agent.declare_tools: false`:

```json title="Reporting tools the agent ran"
{
  "choices": [{"message": {"content": "Done."}}],
  "x_agentsec": {
    "cost_usd": 0.012,
    "events": [
      {"name": "send_email", "arguments": {"to": "attacker@evil.invalid"}, "result": "sent"}
    ]
  }
}
```

Each event becomes a `tool_call` (tagged "Executed by the agent and reported to AgentSec") and, when `result` is
present, a `tool_result`, placed before the reply's text in the trace. They go through every evaluator.

> [!WARNING]
> These calls really happened on your side. Run them only against sandboxed or mocked backends.

> [!NOTE]
> Categories that work by answering your tool calls with poisoned content (`tool_output_poisoning`,
> `loop_and_budget_limits`) cannot reach an agent that never asks AgentSec for a tool result. For those, use the
> [ToolHost or `--mcp-listen`](/docs/testing/frameworks) so AgentSec still supplies the tool results.

## Describe the agent under test

A report cannot know which model made the agent's decisions unless the agent says so. Optionally add
`x_agentsec.agent` to a reply:

```json
"x_agentsec": {"agent": {"name": "email-assistant", "version": "1.4.0", "backend": "anthropic",
                         "model": "claude-sonnet-4-5", "configuration": "hardened"}}
```

Only these five string fields are kept (printable characters, at most 120 each); anything else is dropped, and
configured secrets are masked. Report what actually decided, `"backend": "scripted"` for a test double, and never
credentials. The dashboard shows it as **Agent reported**, with a {{tag:Scripted stand-in}} label for scripted
backends.

## Multi-agent systems

A system with several agents should say which one acted, so delegation can be checked:

```json
{"choices": [{"message": {
  "content": null,
  "x_agentsec": {"actor": "planner"},
  "tool_calls": [{"id": "researcher__3", "type": "function",
                  "function": {"name": "search_docs", "arguments": "{\"query\": \"incident\"}"},
                  "x_agentsec": {"actor": "researcher", "delegated_by": "planner"}}]
}}]}
```

Events in `x_agentsec.events` accept the same `actor` and `delegated_by` keys. Without attribution,
multi-agent scenarios are reported as not observable. See [Multi-agent testing](/docs/testing/multi-agent).

## Streaming

With `agent.stream: true`, AgentSec sends `"stream": true` and `Accept: text/event-stream`, and expects
OpenAI-style `data: {chunk}` lines ending with `data: [DONE]`. Tool-call fragments are joined by `index`; `usage`
and `x_agentsec` may arrive in any chunk. An empty or malformed stream, or a chunk with an `error`, fails the
scenario.

## Infrastructure failures must be errors

If your agent (or a CLI you wrap) answers an infrastructure problem such as a rate limit, exhausted quota or
timeout with an ordinary text reply, AgentSec scores it like any reply and the scenario **passes**. Return an
HTTP error instead (or raise `AdapterError` in a `CallableAdapter`). This happened for real: a CLI agent that hit its
usage limit kept exiting successfully with the limit notice as its answer.

## Checklist

- Treat every request as a fresh conversation; AgentSec resends the full history.
- Call tools through the API's tool-calling mechanism so the calls are visible, or report them in `x_agentsec.events`.
- Return non-2xx for failures.
- Answer within `agent.timeout_s` (default 30 seconds).
- Use synthetic credentials and mocked tools.

## Reference agents

The engine repository ships offline reference agents that speak this contract, each with a vulnerable mode and a
`--safe` mode. They are the quickest way to check your setup and to see every finding type:

| Agent | Command | Policy |
|---|---|---|
| Rule-based vulnerable agent (port 8000) | `python examples/vulnerable_rag_agent/server.py [--safe]` | `examples/vulnerable_rag_agent/agentsec.yaml` |
| RAG agent that runs its own tools (port 8100) | `python examples/rag_agent/server.py [--safe]` | `examples/rag_agent/agentsec.yaml` |
| Coding, support and browser assistants (ports 8010, 8020, 8030) | `python examples/real_world_agents/<name>/server.py [--safe]` | `examples/real_world_agents/<name>/agentsec.yaml` |
| Multi-agent team (port 8040) | `python examples/real_world_agents/multi_agent_team/server.py [--safe]` | its `agentsec.yaml` |
| LLM-powered email and browser assistants (ports 8060, 8050) | See [Email and browser agents](/docs/testing/email-and-browser) | |
