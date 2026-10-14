---
title: Policy tab and MCP scans
description: The Policy tab of a run in the AgentSec dashboard, and how MCP server scan reports are shown - definitions, checks, and rescanning.
section: guide
order: 7
---

## The Policy tab

The **Policy** tab shows the policy exactly as it was run, read from the report (never from your current
`agentsec.yaml`). Secret values are never in a report; only how many there were.

**Agent**

| Row | Meaning |
|---|---|
| Name, Endpoint, Model | `agent.name`, `agent.endpoint`, `agent.model` |
| Declares tools | "Yes, allowed tools plus forbidden actions as decoys" (`declare_tools: true`) or "No" |
| Streaming | Whether AgentSec requested a streamed reply (`agent.stream`) |
| Timeout | Per-request timeout in seconds |
| Retrieval tools | Tools whose results carry the adversarial content, when set |
| API key env | The name of the environment variable holding the agent's token, never its value; "not set" when unused |

**Tools.** Every allowed tool and every forbidden action, with **Allowed** or {{sev:critical}} **Forbidden**, and
its declared `tool_effects` as tags. The note reads "Undeclared effects mean the authority checks stay silent for
that tool." or, without an allowlist, "No allowed_tools: every non-forbidden tool is permitted."

**Agent roles** (multi-agent policies only): each agent's effects, tools and whom it can delegate to.

**Limits**, and **Spend limits** and **Address allowlist** when the policy sets them (the allowlist shows only
how many addresses it holds).

**Tests**

| Row | Meaning |
|---|---|
| Categories | The `tests` list, or "all built-in categories" when it was empty |
| Attack packs | Packs listed under `attack_packs` |
| Judge | The judge model and endpoint and its checks, when configured |
| Secrets | "N configured secrets; values are never written to reports" |
| Policy file hash | SHA-256 of the policy file; two runs with the same hash ran the same policy |

Every field is explained in the [Policy reference](/docs/reference/policy).

## MCP scans

`agentsec mcp scan` checks an MCP server's tool, resource and prompt **definitions** for poisoning, hidden
characters, shadowing and changes, without calling anything. Upload its `mcp-report.json` like any report:

```bash
agentsec mcp scan --command "python my_server.py" --out .agentsec
agentsec upload .agentsec/mcp-report.json --server https://<your dashboard>
```

An MCP scan's page has three tabs: **Overview**, **Findings** and **Definitions**. The header shows the
**Server version** and the **Target** (the scanned command or URL).

### Overview

- The headline: "N findings across X of Y definitions." or "No static check matched the server's definitions."
- The explanation: the scan listed the server's tools, resources and prompts and checked their definitions
  without calling, reading or fetching any of them. Static checks cover known patterns; a clean scan is not proof
  the server is safe.
- Counts: **Tools**, **Resources**, **Prompts**, **Findings**, and a severity bar.
- **Definitions**: the first 50 definitions with their kind (tool, resource, prompt, or removed), worst severity
  (or {{status:passed}} **Clean**) and number of findings. Descriptions are shown exactly as the server sent
  them, with hidden characters made visible.
- **Checks that fired**, and **OWASP agentic categories** (mostly ASI04, supply chain).
- **Scan again**: the command to rescan the same target. If the target is a command, read it before you run it:
  it starts the server. Pin the definitions with `--pin-write` and compare later scans with `--pin` to catch
  definitions that change after you approved them ("rug pulls").

### Definitions tab

Each definition with its kind, its **Name** (resources only, which have a URI and a name), its
**Description as the server sends it** ("No description." when it has none, "No longer listed by the server." for
one that disappeared since the pin) and the **Findings** against it ("No check matched this definition.").

### Findings

MCP findings use the same tab as agent tests, with three differences: "What the agent did" becomes
**What the check found**; **Checked** shows the text that matched; and instead of a scenario the detail names the
**Definition**. **Reproduce** gives the scan command recorded in the report (`agentsec mcp scan --command ...` or
`--url ...`), with "This command is the scan target recorded in the report. Read it before you run it." for a
command, because rescanning starts that server. With no findings the tab says "No static check matched these
definitions. The checks cover known patterns; this is not proof the server is safe." The rules are listed in the [Rules reference](/docs/reference/rules#mcp-scan-rules)
and explained in [MCP testing](/docs/testing/mcp).
