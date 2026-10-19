---
title: The pytest plugin
nav_title: pytest plugin
description: Turn AgentSec scenarios into pytest tests with the built-in plugin - options, fixtures, skips for untested categories, and failure output.
seo_title: AI Agent Security Tests in pytest with AgentSec
section: testing
order: 5
---

Installing AgentSec registers a pytest plugin (through the `pytest11` entry point). No `conftest.py` setup is
needed. Use it when you want security scenarios to pass or fail alongside your unit tests.

## Prerequisites

- AgentSec installed in the same environment as pytest (`pip install invaris-agentsec`; after upgrading a
  development checkout, reinstall with `pip install -e .` so the entry point is registered).
- A policy file and a running agent, as for the CLI.

## Write the test

```python title="tests/test_agent_security.py"
import pytest
from agentsec import CATEGORIES


@pytest.mark.agentsec
@pytest.mark.parametrize("category", CATEGORIES)
def test_agent_resists(category, agentsec_run):
    agentsec_run(category, fail_on="high")
```

## Run it

```bash
pytest --agentsec-policy agentsec.yaml --agentsec-seed 0 -rs
```

Against the [minimal agent](/docs/testing/agent-contract#a-minimal-testable-agent) and the `agentsec init` policy
this gives:

```text
9 passed, 4 skipped
SKIPPED ... AgentSec: action_without_authorization built no scenarios for this policy (its prerequisites, e.g. tool_effects or agent_roles, are not declared)
...
```

The plugin runs exactly the categories you pass to `agentsec_run`, regardless of the policy's `tests:` list, so the
test above runs all 13 built-in categories. The four skipped categories need `tool_effects` or `agent_roles` in the
policy. Skipping (rather than passing)
makes it visible that nothing was tested.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--agentsec-policy PATH` | `agentsec.yaml` | Policy used by the fixtures |
| `--agentsec-seed N` | `0` | Seed for reproducible scenarios |

## Fixtures

| Fixture | Scope | Provides |
|---|---|---|
| `agentsec_policy` | session | The loaded `Policy`. A bad or missing file fails the test with the loader's message |
| `agentsec_target` | session | An `AgentTarget` built from the policy |
| `agentsec_suite` | session | A `SecuritySuite` using the seed option (HTTP adapter) |
| `agentsec_run` | function | `run(*names, fail_on="low")`: runs the categories or scenario ids, asserts, returns the `RunResult` |

`agentsec_run`:

1. raises `AssertionError` (fails the test) when a finding at or above `fail_on` exists, or any scenario errored;
2. **skips** the test when the category built no scenarios for the policy, when every scenario was not observable,
   or when every scenario was inconclusive or not observable;
3. **warns** when only some scenarios were inconclusive;
4. otherwise returns the `RunResult` so you can assert more.

The `agentsec` marker is registered for your own use, for example `pytest -m agentsec`.

## Failure output

```text
AssertionError: AgentSec: 6 finding(s) at or above 'high', 0 errored scenario(s)
  [CRITICAL] Indirect prompt injection triggered send_email (indirect_prompt_injection/plain_appended)
  ...
```

## In-process agents under pytest

The default fixtures use the HTTP adapter. For an in-process or framework agent, build the suite in your own
fixture:

```python title="tests/conftest.py"
import pytest
from agentsec import AgentTarget, SecuritySuite
from agentsec.adapters import CallableAdapter
from my_app import my_agent


@pytest.fixture(scope="session")
def suite():
    target = AgentTarget.from_file("agentsec.yaml")
    return SecuritySuite(target, adapter=CallableAdapter(my_agent))
```

```python title="tests/test_security.py"
def test_no_injection(suite):
    suite.run("prompt_injection").assert_clean(fail_on="high")
```

## When to use it

Use the plugin for pass/fail gating inside an existing test suite. Each `agentsec_run` call is a fresh run and
writes no report files; use the CLI (or `write_reports`, see [Python API](/docs/testing/python-api#lower-level-run-suite-and-reports))
when you also want the HTML report, SARIF or an upload to the dashboard.
