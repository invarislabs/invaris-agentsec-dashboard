---
title: AgentSec documentation
nav_title: Introduction
description: Learn how to test AI agents for security failures with AgentSec, read the results in the dashboard, and integrate testing into your CLI, code and CI.
section: start
order: 1
---

## What AgentSec is

**AgentSec** (Invaris AgentSec) is an open-source tool that tests AI agents the way an attacker would. It
pretends to be a hostile environment around your agent: it sends adversarial user messages, answers your
agent's tool calls with poisoned documents and booby-trapped tool output, and runs follow-up conversations to
see whether poisoned or private information survives in the agent's memory. Every step is recorded, and
deterministic checks compare what the agent *did* against a policy you write: which tools it may call, which
actions it must never take, which secrets must never appear, and how many steps, calls, tokens, seconds and
dollars it may spend.

Each violation becomes a **finding** with its evidence: the input, the action the agent took, the policy it
broke, the trace events that prove it, and a suggested fix. There is no opaque risk score.

## What problems it solves

AI agents read untrusted text (emails, web pages, retrieved documents, tool results) and then act with real
tools. That combination creates failures that ordinary unit tests do not catch:

- **Prompt injection**: instructions hidden in a message, document, email or web page take over the agent.
- **Tool misuse**: the agent calls a tool it should never call, or calls an allowed tool with dangerous arguments.
- **Data leaks**: secrets, credentials or restricted documents end up in the agent's reply or in a tool call.
- **Memory poisoning**: a planted instruction survives into a later conversation, or one user's data leaks to another.
- **Runaway behavior**: endless retry loops and unbounded tool use that burn time and money.
- **Authority problems**: actions the current task never authorized, cross-account actions, and multi-agent
  delegation that escalates privileges.

AgentSec makes these failures reproducible (every run is seeded), visible (full traces) and checkable in CI
(exit codes, SARIF, pull-request comparisons).

## The pieces

:::cards
- [AgentSec engine and CLI](/docs/testing/cli): The `agentsec` command and Python package. Runs the attacks, evaluates traces and writes reports.
- [Hosted dashboard](/docs/guide/dashboard-tour): This web app. Keeps every uploaded run per project, with history, comparisons and full traces.
- [Local dashboard](/docs/guide/local-dashboard): `agentsec dashboard`, a read-only viewer for report files on your own machine.
- [GitHub Action](/docs/testing/ci-github-actions): Runs AgentSec in CI, comments on pull requests and uploads to the dashboard.
:::

```diagram title="How a run flows"
  agentsec.yaml (your policy)
        │
        ▼
  ┌───────────────┐   adversarial messages,      ┌───────────────┐
  │ AgentSec      │   simulated tool results ──▶ │ Your agent     │
  │ engine        │ ◀── replies and tool calls   │ (HTTP, Python, │
  └──────┬────────┘                              │  MCP, ...)     │
         │ traces → evaluators → findings        └───────────────┘
         ▼
  report.json / report.html / summary.md / results.sarif
         │
         ├──▶ agentsec dashboard   (local, read-only)
         └──▶ agentsec upload ───▶ hosted dashboard (this app): history, comparison, sharing
```

## Where to start

:::cards
- [Quickstart](/docs/quickstart): Install AgentSec, attack the bundled vulnerable agent, and see the results in the dashboard in about ten minutes.
- [How AgentSec works](/docs/concepts): Policies, scenarios, traces, findings and verdicts, explained in plain language.
- [Choose a testing method](/docs/testing/overview): CLI, Python, pytest, frameworks, MCP, email and browser agents, CI.
- [Understand your results](/docs/results/verdicts): What passed, findings, error, not observable and inconclusive mean, and what to do next.
- [CLI reference](/docs/reference/cli): Every `agentsec` command and option.
- [Developer guide](/docs/developers/architecture): How the engine and this dashboard fit together, and how to extend them.
:::

> [!WARNING] Test environments only
> AgentSec sends adversarial content to the agent you point it at. Only test deployments that use synthetic
> credentials and sandboxed or mocked tools. Never point it at a production agent that can act on real
> systems or data.

## What is built today

These docs describe what exists in **AgentSec 0.9.0** and **dashboard 0.2.0**, verified against their source
code. Planned work is called out explicitly as planned, for example on
[Security and limitations](/docs/developers/security-and-limitations#not-built-yet). The engine's own
documentation lives in its repository at [invarislabs/invaris-agentsec](https://github.com/invarislabs/invaris-agentsec/tree/main/docs),
and the dashboard's source is at [invarislabs/invaris-agentsec-dashboard](https://github.com/invarislabs/invaris-agentsec-dashboard).
Both are open source under the Apache License 2.0.
