---
title: Writing documentation
description: How the /docs section of the AgentSec dashboard works and how to add or update a page - files, front matter, supported Markdown, callouts, badges, code blocks, search, and the checks that keep docs accurate.
seo_description: How the AgentSec /docs site works and how to add or update a page: files, front matter, SEO metadata, Markdown, callouts, code blocks, search and checks.
section: developers
order: 9
---

These docs live in the dashboard repository and are served by the dashboard itself at `/docs`, on the same domain
and deployment. There is no separate site, build step or dependency: pages are Markdown files rendered to HTML on
the server once, when the app starts.

**What happens with a broken page.** In CI, `tests/test_docs.py` loads the docs strictly and fails on the first
malformed page, so it should never be merged. If one is deployed anyway, production stays up: the page is left out
(it answers 404), every other page is served, and the error is logged as `documentation page skipped: <file>: <reason>`.
A missing or damaged picture does not take its page out: the caption is shown without it, and the problem is logged
the same way.

## Where things are

| Path | What it is |
|---|---|
| `app/docs/content/**/*.md` | The pages. A file's path is its URL: `content/testing/cli.md` → `/docs/testing/cli`, `content/index.md` → `/docs` |
| `app/docs/site.py` | Loads pages, builds the sidebar, search index, sitemap and the page shell (metadata, layout) |
| `app/docs/markdown.py` | The Markdown renderer (a safe subset; raw HTML is shown as text) |
| `app/docs/highlight.py` | Server-side syntax highlighting (shell, YAML, JSON, Python) |
| `app/docs/assets.py` | Loads the screenshots and diagrams, checks them, and serves screenshots at `/docs/img/<file>` |
| `app/docs/images/*.webp` | Screenshots, a light and a dark file per picture (`<name>-light.webp`, `<name>-dark.webp`) |
| `app/docs/diagrams/*.svg` | Diagrams, inlined into the page and coloured by the theme |
| `scripts/docs_screenshots.py`, `scripts/docs_diagrams.py` | Regenerate the screenshots and the diagrams (not shipped in the image) |
| `app/docs/__init__.py` | Routes: `/docs`, `/docs/<page>`, `/docs/search`, `/docs/search-index.json`, `/docs/sitemap.xml`, and `/robots.txt` and `/sitemap.xml` at the site root |
| `app/static/docs.css`, `docs.js`, `theme.js` | Styles (built on the dashboard's `app.css` tokens), instant search, copy buttons, table of contents, theme |
| `tests/test_docs.py` | Checks that keep the docs correct |

## Add a page

1. Create `app/docs/content/<area>/<name>.md` with front matter:

```markdown
---
title: Testing with the CLI
nav_title: CLI
description: One sentence for search engines, link previews and the page lead.
section: testing
order: 2
---
```

| Key | Required | Meaning |
|---|---|---|
| `title` | yes | The page heading (its only `h1`); the `<title>` is this followed by the site name, "AgentSec Docs", unless `seo_title` is set |
| `description` | yes | Shown under the title, and used as the meta description and in link previews unless `seo_description` is set |
| `section` | yes | Sidebar group: `start`, `guide`, `results`, `testing`, `developers`, `reference` or `demos` |
| `order` | no | Position within the group (default 100) |
| `nav_title` | no | A shorter sidebar label |
| `seo_title` | no | The `<title>` and link-preview title, used as written (at most 65 characters, aim for 60) |
| `seo_description` | no | The meta description and link-preview text when `description` is longer than about 160 characters (at most 165) |

2. Write the content starting at `##` headings (the title is the page's only `h1`).
3. Run `pytest tests/test_docs.py` and look at it with `uvicorn app.main:create_app --factory --reload`.

The sidebar, previous/next links, search index and sitemap pick the page up automatically.

**A new demo video** goes at the top of `app/docs/content/demos/videos.md` (newest first), as its own `##`
section in the same shape as the others: a `https://youtu.be/` link, its length and month, two or three
sentences on what it shows, and a chapter table linking each timestamp (`?t=<seconds>`) to the page that
explains it. Each section gets its own anchor and search entry. The docs pages cannot embed players: their
Content-Security-Policy allows no third-party frames or scripts.

## Search engines and link previews

Every page is server-rendered HTML, so search engines read it without running JavaScript. The page shell
(`page_shell` in `app/docs/site.py`) adds, for every page:

- a `<title>` and meta description from the front matter, and a canonical URL built from `PUBLIC_URL`, so set
  `PUBLIC_URL` to the address people use (see [Configuration](/docs/reference/configuration));
- Open Graph and Twitter card tags, with `app/static/social-card.png` as the preview image (redraw it with
  `python scripts/make_social_card.py`, which needs Pillow);
- JSON-LD structured data: `Organization` and `WebSite` everywhere, `SoftwareApplication` for AgentSec on the docs
  home, and `TechArticle` plus a `BreadcrumbList` on every other page.

The search results page and the not-found page are `noindex` and have no canonical URL. `/robots.txt` lets
crawlers into the docs, keeps them out of `/api/`, `/auth/` and the docs search, and names the sitemap.

Write a title and description for the reader first: say what the page lets them do, with the words they would
search for, once each. `tests/test_docs.py` fails when two pages share a title or description, or one is too long.

## Supported Markdown

- `##`, `###`, `####` headings, each with an anchor link; add `{#custom-id}` at the end of a heading to fix its id.
- Paragraphs, `**bold**`, `*italic*`, `` `code` `` (use double backticks for code containing a backtick).
- Links must be site paths (`/docs/testing/cli#anchor`), in-page anchors (`#anchor`) or `https://` URLs;
  `http://`, protocol-relative `//host`, relative paths and `javascript:` fail the build. External links get an arrow
  and `rel="noopener noreferrer"`. The tests also only allow external links to the project's GitHub organisation,
  `genai.owasp.org`, `modelcontextprotocol.io` and `youtu.be` (demo videos); add a domain to that list in `tests/test_docs.py` when you need one.
- Lists (`-` or `1.`), nested by indentation; tables (escape a literal pipe inside a cell as `\|`); blockquotes; `---`.
- Fenced code with a language and an optional title; every block gets a Copy button:

````markdown
```yaml title="agentsec.yaml"
version: "1"
```
````

  Languages highlighted: `bash`/`shell`, `yaml`, `json`, `python`; `text` is plain; `diagram` renders a text diagram.

- Callouts, written as blockquotes:

```markdown
> [!NOTE]
> Plain information.

> [!WARNING] A custom title
> Something that can go wrong.
```

  Kinds: `NOTE`, `TIP`, `WARNING`, `IMPORTANT`, `CAUTION`.

- Link cards:

```markdown
:::cards
- [Quickstart](/docs/quickstart): Install AgentSec and run your first test.
:::
```

- Screenshots and diagrams, each with a text alternative (`alt:`, read by screen readers; describe what the
  picture shows) and a caption (inline Markdown; say what the reader should notice):

```markdown
:::figure run-verdict
alt: The top of a run page: header facts, tabs, the headline "43 findings in 35 of 35 scenarios." and a severity bar.
The header, tabs and verdict of the Quickstart's vulnerable reference agent.
:::

:::diagram verdict-decision
alt: Flowchart: did any check fire? yes, Findings. Otherwise ...
How a scenario's verdict is decided.
:::
```

  A screenshot shows the light or the dark picture to match the reader's theme (the other is never downloaded),
  loads lazily with its size reserved, and opens full size when selected. A diagram is inlined, so it follows the
  theme too.

- The dashboard's real badges, so the docs show exactly what the product shows: `{{status:inconclusive}}`,
  `{{sev:critical}}`, `{{cell:passed}}`, `{{tag:Scripted stand-in}}`, `{{kbd:Ctrl K}}`. They render as
  {{status:inconclusive}} {{sev:critical}} {{cell:passed}} {{tag:Scripted stand-in}} {{kbd:Ctrl K}}.

## Screenshots and diagrams

Every screenshot is the real dashboard showing real AgentSec reports. `scripts/docs_screenshots.py` makes them all
again: it runs the engine's reference agents (vulnerable, hardened and not running), the email attack pack and an
MCP scan of the demo server, uploads the reports to a throwaway copy of the dashboard, and photographs each view in
light and dark mode at twice the display size. Upload tokens that appear are masked. Rerun it when a view changes:

```bash
pip install playwright pillow && playwright install chromium
python scripts/docs_screenshots.py --engine ../invaris-agentsec                 # every screenshot
python scripts/docs_screenshots.py --engine ../invaris-agentsec run-verdict     # only some
python scripts/docs_diagrams.py                                                 # the diagrams
```

To add a screenshot, add a `sh.shoot(...)` line to the script (what to open and which part to keep), run it, then
use the name in a `:::figure` block. Diagrams are drawn by `scripts/docs_diagrams.py` with classes only (`d-box`,
`d-key`, `d-t`...), which `docs.css` colours; scripts, styles, links and images inside an SVG are refused.

Show a picture only where it helps the reader find or understand something on the screen. The caption says what
to notice; the text around it still explains everything, for readers who cannot see the picture.

## Keeping docs accurate

The implementation is the source of truth. `tests/test_docs.py` fails when:

- a page does not parse, lacks front matter, or links to a page or anchor that does not exist;
- two pages share a `<title>` or meta description, a title is over 65 characters, or a description over 165;
- an `agentsec` command or option from the installed engine's CLI parser is missing from the [CLI reference](/docs/reference/cli);
- a key of the engine's policy schema (`agentsec schema policy`) is missing from the [Policy reference](/docs/reference/policy);
- an API route of the dashboard is missing from the [Dashboard API](/docs/reference/api) page;
- a dashboard setting (read in `app/config.py` or listed in `.env.example`) is missing from [Configuration](/docs/reference/configuration);
- a finding rule known to the engine's OWASP mapping is missing from the [Rules reference](/docs/reference/rules);
- a built-in attack category is missing from the [Attack catalog](/docs/reference/attack-catalog);
- an `agentsec.yaml` example in the docs fails to load with the engine's policy loader;
- a "learn more" link from the dashboard (`docLink(...)` in `app.js`) points at a page or anchor that does not exist;
- the engine version the docs name differs from the one the `Dockerfile` and CI install;
- a page, screenshot or diagram would not be included in the installed package;
- a screenshot lacks its light or dark picture, a picture is not used by any page, a figure has no alt text or
  caption, an image is over 200 KB, or a diagram contains anything other than shapes and text;
- rendered pages contain inline scripts or `style` attributes (forbidden by the Content Security Policy).

The checks compare names, not wording, so rephrasing a page or refactoring code does not break them; they fail only
when something user-visible is added, renamed or removed without the docs following.

When you change behaviour, update the matching page in the same pull request. When you upgrade the engine
requirement, run the docs tests: new CLI options, policy keys or rules will be flagged.

## Writing style

- Write for someone using AgentSec for the first time, then add the detail a developer needs.
- Use the exact labels, messages and commands the product shows; copy them from the code or a real run.
- Say clearly when something is a limitation or planned, never imply it exists.
- Prefer examples from real runs (the reference agents and test fixtures) over invented output.
