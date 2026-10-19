---
title: Glossary
description: Plain-language definitions of every term, label and abbreviation used by AgentSec and its dashboard, from adapter to x_agentsec.
seo_title: AI Agent Security Glossary: AgentSec Terms Explained
section: reference
order: 8
---

Each term has its own heading and link (for example `/docs/reference/glossary#inconclusive`), so you can point a
teammate straight at a definition. Terms are in alphabetical order; the search box finds them too.

## A

#### Adapter

The piece that connects AgentSec to an agent: `HTTPAgentAdapter` (OpenAI-style HTTP), `CallableAdapter` (a Python function), `LangChainAdapter`, or your own `AgentAdapter` subclass.

#### Agent

The AI system under test: a model plus the code, prompts and tools around it.

#### Agent reported

What the agent said about itself through `x_agentsec.agent`: name, version, backend, model, configuration. Shown in a run's header.

#### `agent_roles`

Policy section declaring each agent's authority in a multi-agent system.

#### AgentSec (Invaris AgentSec)

The open-source engine and CLI that runs adversarial scenarios against agents.

#### Allowlist (`allowed_tools`)

The tools an agent may call. A call outside it is `unauthorized_tool`.

#### ASI01 to ASI10

The ten categories of the OWASP Top 10 for Agentic Applications (Agentic Security Initiative).

#### Attack goal

A tool call that proves an attack worked (for example forwarding mail to the attacker). States: achieved, not achieved, not tested.

#### Attack pack

A Python module adding scenario categories without changing AgentSec.

#### Attack timeline

Task given, payload delivered, attack goal reached: how an achieved attack unfolded.

#### Authority attenuation

The multi-agent rule: delegated work never carries more authority than the delegating agent holds.

#### `authorized_effects`

The effects a scenario's task permits, compared with each call's `tool_effects`.

## B

#### Baseline

The earlier run in a comparison, for example from `main` or before hardening.

## C

#### Canary

A unique planted value (`CANARY-...`) whose appearance in output proves a leak.

#### Category

A family of attack scenarios, such as `prompt_injection`.

#### Confused deputy

An agent without authority getting a better-privileged agent to act for it.

#### Coverage

Tested scenarios divided by all scenarios in a run.

#### Critical / high / medium / low

Finding severities, from most to least serious.

## D

#### Decoy

A forbidden action AgentSec offers as a tool so an obedient agent has something to call.

#### Delivery

Whether a scenario's adversarial content reached the agent in a tool result (`delivery` in the report).

#### Deterministic

Rule-based; the same trace always gives the same result. Opposite of model-assisted.

## E

#### Error (status)

The scenario could not complete: unreachable agent, timeout, bad reply. Not tested.

#### Evaluator

A check that reads a trace and produces findings.

#### Event

One entry of a trace: user message, agent message, tool call, tool result, limit or error.

#### Evidence

The trace events attached to a finding that prove it.

#### Exit code

The number a command returns: 0 clean, 1 findings (or regressions) at or above `--fail-on`, 2 a setup problem or nothing measured. It is what fails a CI job.

#### Exposure

Text only a scenario's adversarial content contains, used to detect delivery.

## F

#### Finding

One violation of the policy, with severity, evidence and remediation.

#### Finding id

`<scenario>:<rule>[:<key>]`, stable across runs with the same seed and policy.

#### Finding rate

Scenarios with findings divided by tested scenarios.

#### Finding rule

See Rule.

#### Fixed

A baseline finding absent from a newer run whose scenario was tested again.

#### Forbidden action

A tool listed in `forbidden_actions` that must never be called.

## I

#### Inconclusive

The scenario's adversarial content never reached the agent, so nothing was measured. Never a pass.

#### Indirect prompt injection

Instructions hidden in content the agent reads (documents, emails, pages, tool output) rather than in the user's message.

## J

#### Judge

An optional model that answers narrow yes/no questions about transcripts; its findings are model-assisted.

## L

#### Label

A free-text tag on an uploaded run (`--label`), for example a model or prompt version.

## M

#### Marker

A per-seed word an injected instruction asks the agent to say; split in the input so only obedience produces it.

#### MCP (Model Context Protocol)

A protocol through which agents get tools, resources and prompts from servers.

#### MCP scan

`agentsec mcp scan`: a static check of an MCP server's definitions.

#### Model-assisted

A finding from the judge model, with a confidence. Never critical.

## N

#### Not comparable

A baseline finding whose scenario was missing, errored, inconclusive or not observable in the newer run, so it cannot be called fixed.

#### Not observable

A multi-agent scenario that could not be judged because the system did not report which agent acted.

## O

#### Outcome

How a trace ended: completed, limit exceeded, or error.

#### OWASP

The Open Worldwide Application Security Project, which publishes the Top 10 for Agentic Applications.

## P

#### Passed

The agent was attacked and judged, and no check fired.

#### Payload

The adversarial content of a scenario.

#### Phase

Which conversation of a memory scenario an event belongs to (0 first, 1 first follow-up...).

#### Pin file

A snapshot of an MCP server's definitions (`--pin-write`) used to detect later changes (`--pin`).

#### Policy

The `agentsec.yaml` file describing the agent and the rules it must follow.

#### Project

In the dashboard, a container for the runs of one agent or repository.

#### Prompt injection

Instructions in a message that try to override the agent's intended behaviour.

## R

#### Regression

A new finding, or one whose severity went up, in the newer of two runs.

#### Remediation

A finding's suggested fix.

#### Replay

`agentsec replay`: re-running an earlier report's findings to see whether they still reproduce.

#### Retrieval tool

A tool whose results carry the scenario's adversarial content (`agent.retrieval_tools`).

#### Rug pull

An MCP server changing its definitions after you approved them.

#### Rule

The id of the check that produced a finding, for example `secret_leak`.

#### Run

One execution of `agentsec test` (one `report.json`); in the dashboard, one upload.

## S

#### SARIF

Static Analysis Results Interchange Format; `results.sarif` feeds GitHub Code Scanning.

#### Scenario

One concrete test: an input, adversarial content, and what counts as failure. Id: `category/slug`.

#### Scenario tool

A tool whose results carry the scenario's adversarial content: the tools in `agent.retrieval_tools`, or every allowed tool when that is not set. Other tools answer `OK (simulated by AgentSec sandbox; no real action was taken)`.

#### Scripted stand-in

A test double making the agent's decisions (`backend: scripted`). Its verdicts say nothing about any model.

#### Secret

A value in the policy's `secrets` that must never appear in output; masked in reports.

#### Seed

The number that fixes every generated value, making runs reproducible.

#### Session id

The simulated user's identifier, sent as `user` and `X-AgentSec-Session`; used by memory tests.

#### Severity strip

The coloured bar under each run in the dashboard: findings by severity.

#### Simulated tool

A tool AgentSec answers itself; no real action is taken.

#### Slug

A project's short name used in addresses, for example `support-agent`.

## T

#### Tested

A scenario whose status is passed or findings: the agent was attacked and judged.

#### Theme (light and dark mode)

The dashboard and these docs follow your system's light or dark setting until you pick one with the theme switch (the half-filled circle); the choice is remembered in your browser.

#### `tool_effects`

What each tool's call does (read, write, delete, execute...) and what its result contains (`private_data`, `untrusted_content`).

#### ToolHost

An in-process tool host that frameworks call so AgentSec can supply tool results.

#### Trace

The ordered record of everything in one scenario.

## U

#### Upload token

A project-scoped `asp_...` token that can only upload reports.

## V

#### Vector

How adversarial content reaches the agent: direct (user message), retrieved document, or tool output.

#### Verdict

A scenario's status: passed, findings, error, not observable or inconclusive.

## X

#### `x_agentsec`

AgentSec's extension object in agent replies: `events`, `cost_usd`, `agent`, `actor`, `delegated_by`.
