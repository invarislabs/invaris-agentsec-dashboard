---
title: Projects and upload tokens
nav_title: Projects and tokens
description: Create projects, create and revoke upload tokens, understand plan limits, and rename or delete a project in the AgentSec dashboard.
section: guide
order: 2
---

## Projects

A **project** collects the runs of one agent or one repository. Every uploaded report belongs to exactly one
project, chosen by the token used to upload it. Inside a project, runs are grouped by the agent name recorded
in the report (`agent.name` in the policy) or by the MCP server name for MCP scans, so one project can hold
several agents.

### The projects page

After signing in you land on **Projects**, which lists every project you are a member of:

| Column | Meaning |
|---|---|
| Project | Its name, and below it the **slug** used in addresses (`/#/p/<slug>`) |
| Runs | Runs currently stored |
| Latest upload | How long ago the newest run arrived, or "no runs yet" |
| Latest run | That run's severity strip and summary, prefixed with its agent name |

Select a row to open the project. The header also shows how many projects you have and your plan.

:::figure projects
alt: The Projects page listing three projects, support-agent, email-assistant and mcp-servers, each with its slug, number of runs, latest upload and the latest run's severity strip and summary.
Each project's latest run, at a glance: soft green for no findings, yellow hatching for no findings but some inconclusive scenarios, coloured segments for findings by severity.
:::


### Create a project

Type a name (up to 120 characters, for example `support-agent`) and select **Create project**. The slug is made
from the name: lowercase letters, digits and dashes, cut to 40 characters, then `-2`, `-3`... appended if it is
already taken. You become the project's **owner**.

:::figure projects-empty
alt: The Projects page of a new account: “Create your first project” with a project name field and a Create project button.
A new account starts here. Once you have projects, the same form is under **New project**, below the list.
:::


If you are at your plan's limit you get `the Free plan allows 10 projects`. Delete a project you no longer need,
or raise the limit if you run the dashboard yourself (`FREE_MAX_PROJECTS`, see
[Configuration](/docs/reference/configuration)).

## Upload tokens

An **upload token** lets the CLI or CI send reports to one project. Tokens start with `asp_`. A token:

- can only upload reports to its project; it cannot read anything, list projects or sign in;
- is shown **once**, when it is created; the server stores only its SHA-256 hash;
- can be revoked at any time, which stops uploads with it immediately;
- records when it was last used.

### Create a token

There are two places:

- On a new, empty project, the **Send your first report** steps include **Create an upload token** (named `CI`).
- In **Settings > Upload tokens**, type a name (for example `GitHub Actions`; `CI` if left empty) and select
  **Create token**.

The new token appears with **Copy it now; it will not be shown again.** Store it as a secret straight away:
as a CI secret named `AGENTSEC_TOKEN`, or in your shell with `export AGENTSEC_TOKEN=asp_...`. If you lose it,
create a new one and revoke the old one.

:::figure token-created
alt: Project settings, Upload tokens: a notice reading “New token “Local testing”. Copy it now; it will not be shown again.” above the token and a Copy button, then a table of two tokens with their first characters, creation time, last use and a Revoke button.
A token just created in **Settings > Upload tokens** (masked in this picture). Afterwards the table only ever shows its first 12 characters.
:::


> [!WARNING]
> Never paste a token into a command line argument or a file in your repository. `agentsec upload` only reads
> it from an environment variable, so it never lands in shell history or CI logs.

### The token table

| Column | Meaning |
|---|---|
| Name | The label you gave it |
| Token | The first 12 characters followed by `…`, enough to tell tokens apart |
| Created | When it was created |
| Last used | When it last uploaded a report, or "never" |
| (button) | **Revoke** revokes it immediately, with no confirmation. Uploads with it then fail with `invalid or revoked token` |

Only active tokens are listed. With 10 active tokens (the Free plan default) a new one is refused with
`the Free plan allows 10 tokens per project`; revoke one first.

## Settings

**Settings** is visible only to the project owner. Besides tokens it has:

**Plan.** What the project's owner's plan allows:

| Row | Meaning |
|---|---|
| Plan | The plan's name, for example "Free (free during launch)" |
| Run retention | Runs older than this many days are deleted by the daily clean-up job |
| Runs kept per project | Only the newest N runs are kept; the oldest are removed as new ones arrive |
| Largest report | The largest accepted report, uncompressed |
| Tokens per project | Active tokens allowed at once |
| Team members | "Not yet; planned". Projects have a single member today |

:::figure project-settings-plan
alt: The Plan panel of project settings: Free (free during launch), run retention 90 days, the newest 500 runs kept, largest report 25 MB, 10 tokens per project, team members not yet.
The Plan panel with the Free plan's defaults.
:::


**Project.** Rename the project (the slug does not change), or delete it. Deleting removes the project, its tokens
and all of its runs, and cannot be undone. To confirm, type the project's slug exactly; otherwise you see
`Type the project slug exactly to confirm.`

## Who can see what

- A project's runs are visible only to its members. Today that is its owner; team members and roles are planned.
- A project you are not a member of returns the same "not found" as one that does not exist, so its existence
  is not revealed.
- Only the owner can see Settings, create or revoke tokens, and rename or delete the project. The API also lets the
  owner delete a single run (`DELETE /api/projects/{slug}/reports/{id}`); the page has no button for it. Other
  members' attempts are refused with `only the project owner can do this`.

## Retention and limits

Plan limits are enforced on upload and by a daily clean-up job. With the default Free plan:

| Limit | Default | What happens |
|---|---|---|
| Projects per account | 10 | Creating another is refused |
| Runs kept per project | 500 | Each upload over the limit removes the oldest runs |
| Run retention | 90 days | Older runs are removed by `python -m app.maintenance prune` |
| Largest report | 25 MB uncompressed | Larger uploads are refused (HTTP 413) |
| Active tokens per project | 10 | Creating another is refused |

The retention limit is applied by a scheduled job, `python -m app.maintenance prune`, that whoever runs the
dashboard must schedule (the repository includes a daily GitHub Actions workflow for it). Without that job, old runs
stay until the per-project run limit removes them.

Download any run you want to keep longer with **Download report.json** on its page. Self-hosted deployments can
change every limit with environment variables; see [Configuration](/docs/reference/configuration).
