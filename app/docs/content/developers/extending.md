---
title: Extending AgentSec and the dashboard
nav_title: Extending
description: How to add adapters, scenarios, categories, evaluators, MCP checks and schema changes to the AgentSec engine, and API endpoints, views and plan limits to the dashboard.
section: developers
order: 5
---

Extensions that do not need changes to AgentSec itself (your own scenarios, evaluators and judge checks) belong in an
[attack pack](/docs/testing/attack-packs). This page covers contributing to the engine and the dashboard.

## Engine

### Adapters {#adapters}

Subclass `AgentAdapter` in `agentsec/adapters/` and implement `chat(messages, tools, session=None) -> AgentReply`.
Raise `AdapterError` for anything the runner should record as an errored scenario. Do not keep conversation state:
the runner resends the full history every step. Pass `session` to agents with memory. Adapters are constructed in
`agentsec/cli/main.py`; selecting one from the policy (for example an `agent.type` key) is **not implemented** and
would be a small loader and CLI change. For most in-process agents `CallableAdapter` is enough.

### Scenarios and categories

- **A scenario in an existing category:** add a `Scenario` to the list returned by that module's `build(ctx)` in
  `agentsec/attacks/`. Use `ctx.marker`, `ctx.canary`, `ctx.forbidden` and `ctx.retrieval_tool` to stay
  reproducible and policy-driven. Set `vector` carefully: it decides severity.
- **A new category:** create `agentsec/attacks/my_category.py` with `build(ctx)`, register it in `CATEGORIES` in
  `agentsec/attacks/__init__.py`, document it, add tests, and (if the reference agent should fail it) teach
  `examples/vulnerable_rag_agent/server.py` the behaviour and its safe mode the defence.
- A category that depends on policy information (like `action_without_authorization`) should build **no scenarios**
  when the policy has not declared it, never guess from tool names.

### Evaluators

```python
from agentsec.evaluators.base import Evaluator, Finding, excerpt

class MyEvaluator(Evaluator):
    name = "my_check"

    def evaluate(self, scenario, trace, policy):
        findings = []
        for ev in trace.of_type("assistant_message"):
            if "something bad" in (ev.content or ""):
                findings.append(Finding(rule="my_rule", key="", scenario_id=scenario.id, category=scenario.category,
                                        severity="high", title="Human-readable title",
                                        policy_violated="which rule was broken", observed_action="what happened",
                                        input=scenario.user_message, evidence=excerpt(trace, ev.seq),
                                        remediation="How to fix it"))
        return findings
```

Add it to `DEFAULT_EVALUATORS` in `agentsec/evaluators/__init__.py` and map the rule in `agentsec/owasp.py`.
Base checks on the trace only, give each finding a `key` when a scenario can produce several, put secrets in
`sensitive` so they are masked, and write a test with a case that must **not** be flagged.

### MCP checks

Add rules in `agentsec/mcp/checks.py` with an `mcp_` id, map them in `agentsec/owasp.py`, and cover them in
`tests/test_mcp.py` with a definition that must be flagged and a near miss that must not. Keep patterns narrow.

### Policy or trace schema

Update the dataclasses and loader, the JSON Schema file (`policy.schema.json` or `trace.schema.json`) and the tests;
`tests/test_schemas.py` checks they agree. Breaking changes bump the schema version.

### Conventions

Evaluators deterministic and side-effect free; never execute real tool actions; synthetic credentials and reserved
domains (`example.com`, `.invalid`) in scenarios; runtime dependencies kept to PyYAML.

## Dashboard

### Add an API endpoint

Add a route to `app/api.py` (session-authenticated, under `/api`) using the existing dependencies:

```python
@router.get("/projects/{slug}/summary")
def project_summary(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_for(slug, user, db)                 # 404 unless the user is a member; role="owner" to restrict
    rows = store.list_reports(db, p, limit=50)
    return {"runs": len(rows), "findings": sum(r.findings for r in rows)}
```

- Always resolve projects through `project_for`, so "not found" and "not allowed" stay indistinguishable.
- State-changing routes are protected by the same-origin middleware automatically; token-authenticated automation
  belongs under `/api/v1/` like `ingest.py`.
- Read plan limits from `app/plans.py`, never hard-code them.
- Add tests in `tests/` and document the endpoint in [Dashboard API](/docs/reference/api); `tests/test_docs.py` fails
  when a route is missing from that page.

### Add or change a view

The page is `app/static/app.js`, hash-routed (`#/p/<slug>/r/<id>/<tab>`). Build DOM with the `h()` helper, which
inserts strings as text and marks hidden characters; never use `innerHTML` with report data. Keep labels identical
to the local `agentsec dashboard` where views are shared, and update the matching page in the
[Using the dashboard](/docs/guide/dashboard-tour) section.

### Report logic

Summaries, insights, verdicts and comparisons come from the engine (`agentsec.dashboard`, `agentsec.verdicts`,
`agentsec.compare`). Change them in the engine so the CLI, the local and the hosted dashboard stay identical, then
raise the engine requirement in `pyproject.toml`, the `Dockerfile` and CI together.

### Plans

A new plan is a new entry in `app/plans.py` (and billing elsewhere); endpoints ask `plan_named()`. Premium features
planned for later will be private and are not part of the open-source repository.

### Documentation

Add or edit Markdown under `app/docs/content/`; see [Writing documentation](/docs/developers/writing-docs).
