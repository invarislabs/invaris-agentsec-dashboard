---
title: Choosing a testing method
nav_title: Choose a method
description: Every way to test an AI agent with AgentSec - CLI, Python API, pytest, frameworks, MCP, email and browser agents, custom attack packs, CI, SARIF and the dashboard - and when to use each.
section: testing
order: 1
---

All methods run the same scenarios through the same evaluators and produce the same `report.json`. They differ
in how AgentSec reaches your agent and where the result goes.

## How AgentSec can reach your agent

| Your agent... | Use | Guide |
|---|---|---|
| Exposes an OpenAI-compatible chat-completions HTTP endpoint (or can be wrapped in one) | The CLI with `agent.endpoint` in the policy | [Testing with the CLI](/docs/testing/cli), [Make your agent testable](/docs/testing/agent-contract) |
| Is a Python function or object in your process | `CallableAdapter` with the Python API | [Python API](/docs/testing/python-api) |
| Is built with LangChain or LangGraph | `LangChainAdapter` | [Agent frameworks](/docs/testing/frameworks) |
| Is built with a framework that runs its own tool loop (CrewAI, AutoGen, OpenAI Agents SDK, Google ADK, smolagents...) | `CallableAdapter` plus the in-process `ToolHost` | [Agent frameworks](/docs/testing/frameworks#any-other-framework) |
| Gets its tools from MCP servers | `agentsec test --mcp-listen` (AgentSec plays the MCP server) | [MCP testing](/docs/testing/mcp#testing-an-agent-that-uses-mcp) |
| Is a team of agents (planner, workers, crews) | Any of the above, plus `agent_roles` and attribution | [Multi-agent testing](/docs/testing/multi-agent) |

## What you want to test

| Goal | Use | Guide |
|---|---|---|
| The built-in attack suite against one agent | `agentsec test` | [Testing with the CLI](/docs/testing/cli) |
| An MCP server's tool, resource and prompt definitions | `agentsec mcp scan` | [MCP testing](/docs/testing/mcp) |
| An email assistant or browser agent against indirect injection | The email and browser attack packs | [Email and browser agents](/docs/testing/email-and-browser) |
| Attacks specific to your product or domain | Your own attack pack | [Custom scenarios and attack packs](/docs/testing/attack-packs) |
| Leaks and goal hijacks that rules cannot see | The optional judge model | [Judge](/docs/testing/judge) |

## Where results go

| Goal | Use | Guide |
|---|---|---|
| Fail a unit-test suite on findings | The pytest plugin | [pytest plugin](/docs/testing/pytest) |
| Assert on results in your own code | `SecuritySuite(...).run()` and `RunResult` | [Python API](/docs/testing/python-api) |
| Gate pull requests, compare against `main`, comment on the PR | The GitHub Action | [CI and GitHub Actions](/docs/testing/ci-github-actions) |
| Findings in GitHub Code Scanning, job summaries, annotations | SARIF, Markdown, workflow annotations | [Reports, SARIF and CI output](/docs/testing/reports-and-sarif) |
| History, sharing and comparison across runs | Upload to the hosted dashboard | [Uploading to the dashboard](/docs/testing/upload) |
| Browse reports on your machine | `agentsec dashboard` | [Local dashboard](/docs/guide/local-dashboard) |

## A typical progression

1. **Local, by hand.** `agentsec init`, point the policy at your agent, `agentsec test`, read the findings in
   `report.html` or `agentsec dashboard`.
2. **In code.** Add the pytest plugin or the Python API to your test suite, gating on `high` severity.
3. **In CI.** Add the GitHub Action on pull requests, with a baseline from `main` and a PR comment.
4. **Over time.** Upload every CI run to the hosted dashboard for history and comparisons.

> [!WARNING]
> Whatever the method, run AgentSec only against test deployments with synthetic credentials and sandboxed or
> mocked tools. When your agent executes its own tools (frameworks, MCP, `x_agentsec.events`), those tools really
> run on your side, so they must be test doubles.
