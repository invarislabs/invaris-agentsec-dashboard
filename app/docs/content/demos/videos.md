---
title: Demo videos
description: Recorded demos of AgentSec and its dashboard, with chapters and links to the docs pages that explain each part in detail.
seo_title: AgentSec Demo Videos: AI Agent Security Testing in Action
seo_description: Watch AgentSec attack an AI agent: a finding opened in full, inconclusive results, baseline vs hardened comparison, OWASP mapping and CI.
section: demos
order: 1
---

Each video lists its chapters, so you can jump straight to the part you need, next to the page that explains it.
Newest first.

## AgentSec in two minutes {#two-minute-demo}

[Watch on YouTube](https://youtu.be/WkLoWVwetOc) · about 2 minutes · October 2026

AgentSec attacks the deliberately vulnerable reference agent that ships with it (not a real system), opens one
finding in full, explains why a scenario where nothing was measured is reported as inconclusive rather than
passed, and compares the baseline agent with a hardened one.

| Time | Chapter | Read more |
|---|---|---|
| [0:00](https://youtu.be/WkLoWVwetOc) | One poisoned document, every permission | [Quickstart](/docs/quickstart) |
| [0:15](https://youtu.be/WkLoWVwetOc?t=15) | 42 findings across 34 scenarios | [Run overview](/docs/guide/run-overview) |
| [0:32](https://youtu.be/WkLoWVwetOc?t=32) | A summarisation request that ended in a payment | [Scenarios and traces](/docs/guide/scenarios-and-traces) |
| [0:55](https://youtu.be/WkLoWVwetOc?t=55) | Why we refuse to call this test "passed" | [Verdicts](/docs/results/verdicts) |
| [1:17](https://youtu.be/WkLoWVwetOc?t=77) | Baseline vs hardened: what actually got fixed | [Compare runs](/docs/guide/compare) |
| [1:43](https://youtu.be/WkLoWVwetOc?t=103) | OWASP mapping and CI | [Findings and severity](/docs/results/findings-and-severity), [CI with GitHub Actions](/docs/testing/ci-github-actions) |
| [2:02](https://youtu.be/WkLoWVwetOc?t=122) | It's open source and live today | [Contributing](/docs/developers/contributing-and-deploying) |

To run the same attack yourself, follow the [Quickstart](/docs/quickstart): it starts with
`pip install invaris-agentsec`.
