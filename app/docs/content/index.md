---
title: AgentSec documentation
nav_title: Introduction
description: AgentSec is open-source AI agent security testing: red-team your agent for prompt injection, tool misuse, data leaks and memory poisoning from the CLI or CI.
seo_title: AgentSec Docs: AI Agent Security Testing and Red Teaming
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

- **Prompt injection**: instructions hidden in a message, document, email or web page take over the agent
  ([direct](/docs/reference/attack-catalog#prompt-injection) and
  [indirect](/docs/reference/attack-catalog#indirect-prompt-injection) scenarios).
- **Tool misuse**: the agent calls a tool it should never call, or calls an allowed tool with dangerous arguments
  ([unauthorized tool use](/docs/reference/attack-catalog#unauthorized-tool-use)).
- **Data leaks**: secrets, credentials or restricted documents end up in the agent's reply or in a tool call
  ([secret extraction](/docs/reference/attack-catalog#secret-extraction)).
- **Memory poisoning**: a planted instruction survives into a later conversation, or one user's data leaks to another
  ([memory poisoning](/docs/reference/attack-catalog#memory-poisoning)).
- **Runaway behavior**: endless retry loops and unbounded tool use that burn time and money
  ([loop and budget limits](/docs/reference/attack-catalog#loop-and-budget-limits)).
- **Authority problems**: actions the current task never authorized, cross-account actions, and multi-agent
  delegation that escalates privileges ([multi-agent testing](/docs/testing/multi-agent)).

AgentSec makes these failures reproducible (every run is seeded), visible (full traces) and checkable in CI
(exit codes, SARIF, pull-request comparisons). Findings are mapped to the
[OWASP Top 10 for Agentic Applications](/docs/results/findings-and-severity#owasp-categories) (ASI01 to ASI10), and
`agentsec mcp scan` checks MCP servers for tool poisoning and rug pulls ([MCP security testing](/docs/testing/mcp)).

### Automated red teaming, not a replacement for a penetration test

AgentSec automates the repeatable part of AI agent red teaming: a fixed, seeded set of attack scenarios (plus any
[attack packs](/docs/testing/attack-packs) you write), checked by deterministic rules, that you can rerun on every
change. It finds the failures its scenarios and rules describe; a clean run means those scenarios did not succeed,
not that the agent is secure against everything. Manual red teaming and penetration testing still find what no
fixed suite covers. See [Verdicts](/docs/results/verdicts) for exactly what a passing scenario proves.

## The pieces

:::cards
- [AgentSec engine and CLI](/docs/testing/cli): The `agentsec` command and Python package. Runs the attacks, evaluates traces and writes reports.
- [Hosted dashboard](/docs/guide/dashboard-tour): This web app. Keeps every uploaded run per project, with history, comparisons and full traces.
- [Local dashboard](/docs/guide/local-dashboard): `agentsec dashboard`, a read-only viewer for report files on your own machine.
- [GitHub Action](/docs/testing/ci-github-actions): Runs AgentSec in CI, comments on pull requests and uploads to the dashboard.
:::

:::diagram how-a-run-flows
alt: Diagram: the policy drives the AgentSec engine, which sends attacks and simulated tool results to your agent and records its replies and tool calls. The trace goes through evaluators to findings and one verdict per scenario, written as reports that reach the terminal and CI, the local dashboard, or the hosted dashboard through agentsec upload.
How a run flows: AgentSec attacks your agent as your policy describes, evaluates what it did, and writes reports you read in the terminal, in CI or in a dashboard.
:::

## Where to start

:::cards
- [Quickstart](/docs/quickstart): Install AgentSec, attack the bundled vulnerable agent, and see the results in the dashboard in about ten minutes.
- [How AgentSec works](/docs/concepts): Policies, scenarios, traces, findings and verdicts, explained in plain language.
- [Choose a testing method](/docs/testing/overview): CLI, Python, pytest, frameworks, MCP, email and browser agents, CI.
- [Understand your results](/docs/results/verdicts): What passed, findings, error, not observable and inconclusive mean, and what to do next.
- [Attack catalog](/docs/reference/attack-catalog): Every built-in attack scenario, from prompt injection to memory poisoning.
- [MCP security testing](/docs/testing/mcp): Scan MCP servers for tool poisoning, and test agents that use MCP.
- [CLI reference](/docs/reference/cli): Every `agentsec` command and option.
- [Developer guide](/docs/developers/architecture): How the engine and this dashboard fit together, and how to extend them.
- [Demo videos](/docs/demos/videos): Watch AgentSec attack an agent, open a finding and compare baseline with hardened, in two minutes.
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
