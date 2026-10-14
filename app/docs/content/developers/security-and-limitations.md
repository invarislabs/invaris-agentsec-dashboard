---
title: Security model, pitfalls and limitations
nav_title: Security and limitations
description: AgentSec's security model, how the dashboard protects tokens, sessions and hostile report content, common pitfalls, known limitations, and what is not built yet.
section: developers
order: 8
---

## Testing safely

AgentSec runs adversarial content against systems that may have real tools and data:

- use isolated test environments and synthetic credentials and data;
- use sandboxed or mocked tools and disable irreversible actions, especially when the agent runs its own tools
  (frameworks, MCP, `x_agentsec.events`): those calls really happen;
- enforce strict spending and execution limits;
- never point tests at production agents;
- keep the MCP attack host (`--mcp-listen`) and the local dashboard on loopback.

## How the dashboard protects you

| Concern | Protection |
|---|---|
| Hostile report content | Inserted as text only, never HTML; strict CSP (`default-src 'none'`, only the app's own script, styles and fonts); hidden characters and look-alike tool names made visible; report links limited to `http`/`https` |
| Upload tokens | Shown once, stored as SHA-256 hashes, project-scoped, upload-only, revocable; never accepted as a CLI argument; only sent over HTTPS (or to localhost); redirects refused by the client |
| Sessions | Signed, `HttpOnly`, `SameSite=Lax`, `Secure` in production; a fresh session at sign-in |
| Cross-site requests | State-changing session requests must come from the dashboard's own origin; uploads use bearer tokens, never cookies |
| Enumeration | "Not found" and "not allowed" both return 404 for projects, runs and tokens |
| GitHub data | Only id, login, name and avatar are kept; the OAuth token is used once and discarded |
| Oversized uploads | Size limit enforced after decompression, so a gzip bomb is refused |
| Weak configuration | Production refuses a short `SECRET_KEY`, development sign-in, or missing OAuth |
| Other headers | `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Cross-Origin-Opener-Policy: same-origin` |

Reports mask secrets, but traces contain your agent's real responses: share them as you would logs. Use `--no-traces`
when transcripts must not leave your environment.

## Common pitfalls

| Pitfall | Do this instead |
|---|---|
| Treating "0 findings" as "safe" | Check **Tested** and coverage; a clean run is evidence for the scenarios that ran |
| Counting inconclusive or errored scenarios as passes | Only passed and findings are tested; read [Verdicts](/docs/results/verdicts) |
| Calling findings "fixed" after hardening that stopped the agent reading the poison | Use Compare runs: Not comparable and Scenario verdicts |
| An agent that answers rate-limit or quota errors with a normal reply | Return an HTTP error or raise `AdapterError`, or it is scored as a pass |
| Forgetting `secrets` | List the synthetic credentials the agent can see |
| Expecting authority checks without `tool_effects` | Declare effects; undeclared tools are unknown, and those checks stay silent |
| Listing a pack but not its categories in `tests:` | Pack categories run only when listed, or when `tests:` is empty |
| Relative pack paths from another directory | Pack paths resolve from the current directory |
| Limits below what a healthy task needs | Findings on benign runs; set realistic limits |
| Comparing runs with different seeds or policies | Keep the seed and policy fixed; `compare` warns otherwise |
| One run of a model-backed agent as a conclusion | Repeat runs; a model run is one observation, not a rate |
| Running the judge against a hosted model without reading what is sent | Read [what is sent to the judge](/docs/testing/judge#what-is-sent-to-the-judge) |
| Pasting tokens on the command line or committing `.env` | Use environment variables and CI secrets |

## Known limitations

- Detection covers what appears in the trace. Tools an agent runs itself are visible only when reported.
- Deterministic checks do not catch paraphrased leaks unless a canary or secret survives; the judge covers part of
  that gap, with a model's uncertainty.
- Data-flow checks see copied data, not paraphrased data.
- Categories that rely on simulated tool output need an agent that calls tools through the API (or a host).
- Multi-agent checks need the system to report which agent acted; sub-agents sharing one MCP client cannot be told
  apart.
- MCP scanning checks definitions only; MCP attack hosting supports streamable HTTP only and cannot interrupt the
  agent's tool loop.
- Scenarios run sequentially.
- The OWASP mapping is a closest-fit judgement, not an official classification.

## Not built yet {#not-built-yet}

These are **planned or not implemented**, and these docs do not describe them as available:

- **Dashboard:** team members and roles (projects have one member, the owner), organization accounts, rate limiting on
  the upload endpoint, object storage for very large reports (they are stored compressed in Postgres), email
  notifications, and the public launch of the hosted service. Billing, paid plans and later premium features (for
  example longer retention, self-hosted enterprise deployment, production trace monitoring) will be private and are
  not part of the open-source repository.
- **Engine:** multi-agent attribution for systems sharing one MCP client, stateful multi-turn campaign generation,
  cross-agent failure-propagation analysis, memory scenarios longer than one follow-up, MCP-specific attacks beyond
  hostile tool results and decoy tools, dedicated adapters for other frameworks (covered today by `CallableAdapter` +
  `ToolHost`), and selecting an adapter from the policy.
- **Verification:** real LLM-backed framework agents, MCP scanning against a range of real-world servers, and
  `--mcp-listen` against MCP-capable agents other than the Claude Code CLI.
