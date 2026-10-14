---
title: Dashboard tour
description: How the hosted AgentSec dashboard is organised - signing in, the sidebar, projects, runs, live updates, themes and keyboard shortcuts.
section: guide
order: 1
---

The hosted dashboard keeps every AgentSec report you upload, organised by project, and shows the same report
views as the local `agentsec dashboard`, plus history across runs and comparisons in the browser. It never
runs tests itself and never contacts your agent: it only shows what the uploaded `report.json` files record.

:::diagram report-to-dashboard
alt: Diagram: on your machine or in CI, agentsec test writes .agentsec/report.json, and agentsec upload or the GitHub Action sends it over HTTPS with a Bearer upload token. The hosted dashboard checks the token, reads the body within the plan's size limit after decompression, checks, summarises and stores the report, trims the project to its plan, and the run appears in the project.
How reports reach the dashboard. It never runs tests or contacts your agent; it stores and shows the reports you upload.
:::

## Signing in

Open the dashboard's URL. The sign-in page offers:

- **Continue with GitHub**: the normal way in. Only your GitHub id, login, name and avatar are stored; the
  GitHub access token is used once to read your profile and then discarded.
- **Development sign-in (AGENTSEC_DEV_LOGIN is on)**: only on servers started in development mode. Type any
  username made of letters, digits and dashes. Never enabled in production (the server refuses to start).

:::figure signin
alt: The AgentSec sign-in page: the heading “Sign in to your security dashboard”, a short description and a “Continue with GitHub” button, with links to the documentation and the Quickstart.
The sign-in page of a server with GitHub sign-in, as production runs it.
:::


Messages you may see:

| Message | Meaning and what to do |
|---|---|
| The sign-in link expired or was opened in another browser. Try again. | The OAuth `state` check failed, usually a stale tab. Start again from the sign-in page |
| GitHub did not complete the sign-in. Try again. | GitHub rejected or did not return the authorization. Try again; check the OAuth app settings if it persists |
| Sign-in is not configured on this server. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET. | The server has neither GitHub OAuth nor development sign-in. See [Configuration](/docs/reference/configuration) |

Sessions last 14 days by default (`SESSION_DAYS`). **Sign out** is at the bottom of the sidebar.

## The layout

The page has a sidebar on the left and the current view on the right. On narrow screens the sidebar is hidden
behind the **Menu** button in the top bar.

:::figure dashboard-layout
alt: A run page with seven numbered markers: 1, the documentation and theme buttons; 2, the project selector; 3, the project's views (Runs and history, Compare runs, Settings); 4, the run list grouped by agent; 5, your account and Sign out; 6, the run's tabs; 7, the Help for this tab link.
The layout, here on a run's page: **1** documentation and theme switch, **2** project selector, **3** the project's views, **4** its runs grouped by agent, each with a summary and a severity strip, **5** your account, **6** the run's tabs, **7** help for the current tab.
:::


**Top of the sidebar.** The AgentSec logo (back to all projects), a book icon titled **Documentation** that opens
these docs, and the theme switch, which toggles between light and dark mode. Your choice is remembered in this
browser and shared with the documentation; until you choose, both follow your system's light or dark setting. On a
phone the top bar has **Docs** and **Menu** buttons instead.

**Navigation.** On the projects list the sidebar shows **All projects** and one entry per project. Inside a
project it shows:

- a **project selector** to jump between projects (or back to **All projects**);
- **Runs and history**, the [project page](/docs/guide/runs-and-history);
- **Compare runs**, the [comparison view](/docs/guide/compare);
- **Settings**, only for the project's owner ([Projects and tokens](/docs/guide/projects-and-tokens)).

**Run list.** Below the navigation, the project's newest 120 runs are grouped by the agent name (or MCP server
name) in the report, newest first, up to 25 runs per group ("No runs uploaded yet." before the first upload). Each group header shows the name and the number of runs, or
"MCP scan". Each run shows:

- a one-line **summary**, for example `2 critical, 5 high, 1 inconclusive`, `All 35 scenarios passed`,
  `No findings in 8 scenarios; 1 inconclusive`, or `35 scenarios errored`;
- how long ago it was uploaded;
- its label, branch and short commit (or "uploaded" and a date when none were recorded);
- a **severity strip**: one coloured segment per severity, sized by the number of findings.

| Strip | Meaning |
|---|---|
| Red, orange, yellow, grey-blue segments | Findings by severity: critical, high, medium, low |
| Solid soft green | No findings |
| Solid soft purple | Every scenario errored, nothing was tested |
| Yellow hatching | No findings, but some scenarios were inconclusive |

**Your account.** The bottom of the sidebar shows your avatar, name, plan (for example "Free plan") and
**Sign out**.

## Live updates

While a project is open and the browser tab is visible, the dashboard checks for new uploads every 10 seconds.
When a run arrives, a notice appears in the corner, for example
**New run uploaded: support-agent (hardened main 0123abc)**: the agent name, then the run's label, branch and short
commit (or "uploaded" and its date when none were recorded). It has **Open** and **Dismiss** buttons and closes by
itself after 12 seconds; if several runs arrive at once it names the newest. The project page and the comparison view
refresh by themselves.

:::figure upload-toast
alt: A notice in the corner of a project page reading “New run uploaded: vulnerable-rag-agent (hardened main)” with Open and Dismiss buttons.
A run arriving while its project is open. It has a label and a branch but no commit, so the notice shows those two.
:::


## Links you can share

Every view has its own address, including filters, for example a run's findings filtered to critical
severity. Copy the browser's address bar to share exactly what you see with a teammate who has access to the
project. Today a project has one member, its owner; team members are planned (see
[limitations](/docs/developers/security-and-limitations#not-built-yet)).

## Getting help from any page

Most sections of the dashboard have a small underlined link next to their title ("Legend", "What the verdicts mean",
"What each rule means", "Help for this tab"...) that opens the matching page of this documentation.

## Keyboard shortcuts

| Keys | Where | Action |
|---|---|---|
| {{kbd:j}} / {{kbd:k}} | Findings, Scenarios and Definitions tabs | Next / previous item in the list |
| {{kbd:Enter}} | A focused bar of the findings-per-run chart | Open that run |
| {{kbd:/}} or {{kbd:Ctrl K}} | Documentation | Search the docs |

## Hostile content is shown safely

Reports contain the adversarial payloads AgentSec sent and whatever your agent replied. The dashboard treats
all of it as hostile:

- report text is always inserted as plain text, never interpreted as HTML;
- invisible and control characters (zero-width spaces, bidirectional overrides, tag characters) are shown as
  visible marks such as `U+200B`, so hidden instructions can be seen;
- non-ASCII letters in tool names are marked with their code point, so a look-alike tool name (a Cyrillic "е"
  in `sеnd_email`) cannot pass for the real one;
- links that come from a report (for example a CI link) are only shown when they are `http` or `https`.

## When something goes wrong

| You see | Meaning |
|---|---|
| Project not found | The project was deleted, or you are not a member. Not found and not allowed look the same on purpose |
| This could not be opened | A run or project request failed; the message underneath gives the reason |
| The dashboard did not respond | The server could not be reached. On a free host that sleeps when idle, wait a minute and reload |
