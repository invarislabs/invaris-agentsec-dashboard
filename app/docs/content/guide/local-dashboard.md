---
title: The local dashboard
nav_title: Local dashboard
description: Browse AgentSec report files on your own machine with agentsec dashboard - options, what it shows, its security model, and how it differs from the hosted dashboard.
section: guide
order: 9
---

`agentsec dashboard` is a read-only web viewer that ships with the AgentSec engine. It shows the same report
views as the hosted dashboard (overview, findings, scenarios and traces, policy, MCP scans, comparison) for
report files on your disk. Nothing is uploaded, there is no account, and it never contacts your agent.

```bash
agentsec test --policy agentsec.yaml        # writes .agentsec/report.json
agentsec dashboard                          # http://127.0.0.1:8710/
```

## Options

| Option | Default | Meaning |
|---|---|---|
| `PATH ...` | current directory | Report files or directories to search. Directories are searched recursively, six levels deep, for files named `report.json` and `mcp-report.json`, skipping `.git`, `node_modules`, virtual environments, `build`, `dist` and similar. A file passed explicitly can have any name |
| `--host` | `127.0.0.1` | Address to listen on. Anything other than `127.0.0.1`, `localhost` or `::1` prints a warning: there is no login |
| `--port` | `8710` | Port; `0` picks a free one |
| `--open` | off | Open it in your browser |
| `-v`, `--verbose` | off | Log each request |

New and rewritten reports appear while the page is open. Because `agentsec test` overwrites `report.json`,
keep runs you want to compare in their own directories:

```bash
agentsec test --out .agentsec/baseline
# ... change the agent ...
agentsec test --out .agentsec/current
agentsec dashboard .agentsec
```

## Local or hosted?

| | Local `agentsec dashboard` | Hosted dashboard |
|---|---|---|
| Where reports live | Files on your disk | Uploaded, stored per project (compressed, in Postgres) |
| Accounts | None, one user, one process | GitHub sign-in, projects, upload tokens |
| History | Whatever files you keep | Every upload, with a findings-per-run chart, branches, commits and CI links |
| Sharing | Send the file | Share a link with project members |
| Network | Listens on 127.0.0.1 by default | A web service |
| Report views and verdict rules | Same | Same (both use AgentSec's own `agentsec.verdicts` and `agentsec.compare`) |

## Security

- It listens on `127.0.0.1` by default and warns when told to listen on anything but a loopback address.
- It answers `GET` and `HEAD` only and serves reports by an opaque id, never by a path from the request.
- It rejects requests whose `Host` header is not the address it listens on, so a web page you visit cannot read your
  reports through DNS rebinding. A wildcard bind (`0.0.0.0` or `::`) accepts any `Host`: one more reason to keep the
  default.
- Report text is inserted as text, never HTML, under a strict Content Security Policy, and hidden characters are
  shown as visible marks, exactly like the hosted dashboard.

## Errors

| Message | Meaning |
|---|---|
| `error: no such file or directory: <path>` | A path you passed does not exist |
| `error: cannot listen on <host>:<port>: ... (choose another port with --port)` | The port is taken; use `--port 0` for a free one |
