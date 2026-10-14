"""A small, safe Markdown renderer for the documentation pages.

Why not a Markdown library: the dashboard keeps its dependencies minimal, and the docs only need a well-defined
subset. Everything is escaped; raw HTML in a page is shown as text, never rendered. Supported syntax (see
/docs/developers/writing-docs for examples):

- front matter between `---` lines (`title`, `description`, `section`, `order`, `nav_title`)
- headings `##` to `####` (the page title comes from front matter), with an optional `{#custom-id}`
- paragraphs, `**bold**`, `*italic*`, `` `code` ``, `[links](/docs/...)`, hard line breaks with a trailing `\\`
- ordered and unordered lists, nested by indentation
- tables (GitHub style), blockquotes, `---` rules
- fenced code blocks: ```` ```yaml title="agentsec.yaml" ````; language `diagram` renders a text diagram
- callouts: `> [!NOTE]`, `[!TIP]`, `[!WARNING]`, `[!IMPORTANT]`, `[!CAUTION]`, optionally followed by a title
- link cards: a `:::cards` block of `- [Title](/docs/page): description` lines, closed by `:::`
- screenshots and diagrams: `:::figure <name>` or `:::diagram <name>`, then an `alt:` line (what the picture
  shows, for screen readers) and the caption (inline Markdown), closed by `:::`. See `assets.py`
- the dashboard's own badges inline: `{{status:inconclusive}}`, `{{sev:critical}}`, `{{cell:passed}}`,
  `{{tag:Scripted stand-in}}`, `{{kbd:Ctrl K}}`
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .assets import DENSITY, Assets
from .highlight import LANGUAGE_LABELS, canonical, highlight

CALLOUTS = {"NOTE": "Note", "TIP": "Tip", "WARNING": "Warning", "IMPORTANT": "Important", "CAUTION": "Caution"}
STATUS_LABELS = {"passed": "Passed", "findings": "Findings", "error": "Error", "not_observable": "Not observable",
                 "inconclusive": "Inconclusive"}
SEVERITIES = ("critical", "high", "medium", "low")


@dataclass
class Heading:
    level: int
    id: str
    text: str


@dataclass
class Rendered:
    html: str
    headings: List[Heading] = field(default_factory=list)
    # (heading id or "" for the text before the first heading, heading text, plain text of that section)
    sections: List[Tuple[str, str, str]] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    figures: List[str] = field(default_factory=list)     # screenshot and diagram names used, e.g. "diagram:x"


def parse_front_matter(text: str) -> Tuple[Dict[str, str], str]:
    """`key: value` lines between two `---` lines at the top of the file. Values may be quoted."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("front matter is not closed with a '---' line")
    meta: Dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError("front matter line is not 'key: value': %r" % line)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        meta[key.strip()] = value
    return meta, text[end + 5:]


def slugify(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[`*\[\]()]", "", text).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "section"


def plain(text: str) -> str:
    """Inline Markdown reduced to the words a reader sees (for search and heading text)."""
    text = re.sub(r"\{\{(?:status|sev|cell|tag|kbd):([^}]*)\}\}", lambda m: m.group(1).replace("_", " "), text)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[`*]", "", text)
    return re.sub(r"\s+", " ", text).strip()


# ----------------------------------------------------------------------------------------------- inline

def is_external(url: str) -> bool:
    return url.startswith("https://")


def check_link(url: str) -> None:
    """Internal links are site paths (/docs/..., /) or #anchors; external links are https:// only. Anything else
    (javascript:, data:, http://, protocol-relative //host, relative paths) is refused when the page is built."""
    if is_external(url):
        return
    if url.startswith("#") or (url.startswith("/") and not url.startswith("//")):
        if any(c in url for c in "\\\"'<> "):
            raise ValueError("link %r contains a character that is not allowed in a link" % url)
        return
    raise ValueError("link %r must be a site path (/docs/...), an #anchor or an https:// URL" % url)


_CODE = re.compile(r"(`+)(.+?)\1")
_LINK = re.compile(r"\[((?:[^\[\]]|\[[^\]]*\])+)\]\(([^)\s]+)\)")
_BADGE = re.compile(r"\{\{(status|sev|cell|tag|kbd):([^}]+)\}\}")


class Inline:
    def __init__(self, links: List[str]):
        self.links = links

    def render(self, text: str) -> str:
        stash: List[str] = []
        text = self._markup(text.replace("\x00", ""), stash)
        for _ in range(8):            # placeholders nest at most a few levels (a link label holding code)
            if "\x00" not in text:
                break
            text = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], text)
        return text

    def _markup(self, text: str, stash: List[str]) -> str:
        """Inline Markdown to HTML, with code, badges and links held as placeholders in `stash` (shared with
        nested calls, so a link label that contains code resolves against the same list)."""
        def keep(fragment: str) -> str:
            stash.append(fragment)
            return "\x00%d\x00" % (len(stash) - 1)

        text = _CODE.sub(lambda m: keep("<code>%s</code>" % html.escape(m.group(2).strip(" ") or m.group(2),
                                                                         quote=False)), text)
        text = _BADGE.sub(lambda m: keep(self._badge(m.group(1), m.group(2).strip())), text)
        text = _LINK.sub(lambda m: keep(self._link(m.group(1), m.group(2), stash)), text)
        text = html.escape(text, quote=False)
        text = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"<em>\1</em>", text)
        return text.replace(" \\\n", "<br>\n")

    def _link(self, label: str, url: str, stash: List[str]) -> str:
        self.links.append(url)
        inner = self._markup(label, stash)
        href = html.escape(url, quote=True)
        if is_external(url):
            return '<a class="ext" href="%s" rel="noopener noreferrer">%s</a>' % (href, inner)
        check_link(url)
        return '<a href="%s">%s</a>' % (href, inner)

    @staticmethod
    def _badge(kind: str, value: str) -> str:
        v = html.escape(value, quote=True)
        if kind == "status":
            if value not in STATUS_LABELS:
                raise ValueError("unknown status badge %r" % value)
            return '<span class="status %s">%s</span>' % (v, STATUS_LABELS[value])
        if kind == "sev":
            if value not in SEVERITIES:
                raise ValueError("unknown severity badge %r" % value)
            return '<span class="sev %s">%s</span>' % (v, value.capitalize())
        if kind == "cell":
            if value not in SEVERITIES + tuple(STATUS_LABELS):
                raise ValueError("unknown cell badge %r" % value)
            return '<i class="cell dx-cell %s" aria-hidden="true"></i>' % v
        if kind == "kbd":
            return " ".join("<kbd>%s</kbd>" % html.escape(k, quote=False) for k in value.split())
        return '<span class="tag">%s</span>' % html.escape(value, quote=False)


# ----------------------------------------------------------------------------------------------- blocks

_HEADING = re.compile(r"^(#{2,4})\s+(.+?)\s*(?:\{#([a-z0-9-]+)\})?\s*$")
_FENCE = re.compile(r"^(\s*)(```+)\s*([\w+-]*)\s*(?:title=\"([^\"]*)\")?\s*$")
_LIST = re.compile(r"^(\s*)([-*]|\d+[.)])\s+(.*)$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


_FIGURE = re.compile(r"^:::(figure|diagram)\s+([a-z0-9]+(?:-[a-z0-9]+)*)\s*$")


class Renderer:
    def __init__(self, assets: Optional[Assets] = None, strict: bool = True,
                 problems: Optional[List[str]] = None) -> None:
        self.assets = assets
        self.strict = strict
        self.problems = problems if problems is not None else []
        self.figures: List[str] = []
        self.links: List[str] = []
        self.inline = Inline(self.links)
        self.headings: List[Heading] = []
        self.ids: Dict[str, int] = {}
        self.sections: List[List[str]] = [["", "", ""]]   # id, title, text

    def _text(self, s: str) -> None:
        self.sections[-1][2] += " " + plain(s)

    def _unique(self, slug: str) -> str:
        n = self.ids.get(slug, 0)
        self.ids[slug] = n + 1
        return slug if n == 0 else "%s-%d" % (slug, n + 1)

    def render(self, text: str) -> Rendered:
        lines = text.replace("\r\n", "\n").replace("\t", "    ").split("\n")
        body = self.blocks(lines, top=True)
        sections = [(s[0], s[1], re.sub(r"\s+", " ", s[2]).strip()) for s in self.sections
                    if s[1] or s[2].strip()]
        return Rendered(body, self.headings, sections, self.links, self.figures)

    def blocks(self, lines: List[str], top: bool = False) -> str:
        out: List[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            m = _FENCE.match(line)
            if m:
                i = self._fence(lines, i, m, out)
                continue
            m = _HEADING.match(line)
            if m and top:
                level, raw, custom = len(m.group(1)), m.group(2), m.group(3)
                hid = self._unique(custom or slugify(plain(raw)))
                txt = plain(raw)
                self.headings.append(Heading(level, hid, txt))
                self.sections.append([hid, txt, ""])   # every heading is its own search result
                out.append('<h%d id="%s">%s<a class="dx-anchor" href="#%s" aria-label="Link to this section">#</a></h%d>'
                           % (level, hid, self.inline.render(raw), hid, level))
                i += 1
                continue
            if line.strip() == ":::cards":
                i = self._cards(lines, i, out)
                continue
            m = _FIGURE.match(line.strip())
            if m:
                i = self._figure(lines, i, m.group(1), m.group(2), out)
                continue
            if line.strip().startswith(":::"):
                raise ValueError("unknown block %r (use :::cards, :::figure <name> or :::diagram <name>)" % line.strip())
            if re.match(r"^\s*(-{3,}|\*{3,})\s*$", line):
                out.append("<hr>")
                i += 1
                continue
            if line.lstrip().startswith(">"):
                i = self._quote(lines, i, out)
                continue
            if "|" in line and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1]):
                i = self._table(lines, i, out)
                continue
            if _LIST.match(line):
                i = self._list(lines, i, out)
                continue
            i = self._paragraph(lines, i, out)
        return "\n".join(out)

    def _fence(self, lines: List[str], i: int, m: "re.Match[str]", out: List[str]) -> int:
        indent, ticks, lang, title = len(m.group(1)), m.group(2), m.group(3), m.group(4)
        body: List[str] = []
        i += 1
        while i < len(lines) and lines[i].strip() != ticks:
            body.append(lines[i][indent:] if lines[i][:indent].strip() == "" else lines[i])
            i += 1
        if i >= len(lines):
            raise ValueError("code block opened with %s is never closed" % ticks)
        code = "\n".join(body)
        self._text(code)
        lang = canonical(lang)
        label = title or LANGUAGE_LABELS.get(lang, lang.upper())
        cls = "dx-code dx-diagram" if lang == "diagram" else "dx-code"
        out.append('<figure class="%s"><figcaption><span>%s</span>'
                   '<button class="btn small dx-copy" type="button" hidden>Copy</button></figcaption>'
                   '<pre><code class="lang-%s">%s</code></pre></figure>'
                   % (cls, html.escape(label, quote=False), html.escape(lang, quote=True), highlight(code, lang)))
        return i + 1

    def _cards(self, lines: List[str], i: int, out: List[str]) -> int:
        i += 1
        cards = []
        while i < len(lines) and lines[i].strip() != ":::":
            m = re.match(r"^\s*-\s*\[([^\]]+)\]\(([^)]+)\)\s*:?\s*(.*)$", lines[i])
            if m:
                check_link(m.group(2))
                self.links.append(m.group(2))
                self._text(m.group(1) + " " + m.group(3))
                cards.append('<a class="dx-card" href="%s"><strong>%s</strong><span>%s</span></a>'
                             % (html.escape(m.group(2), quote=True), html.escape(m.group(1), quote=False),
                                self.inline.render(m.group(3))))
            elif lines[i].strip():
                raise ValueError("a :::cards line must look like '- [Title](/docs/page): text', got %r" % lines[i])
            i += 1
        if i >= len(lines):
            raise ValueError(":::cards block is never closed with ':::'")
        out.append('<div class="dx-cards">%s</div>' % "".join(cards))
        return i + 1

    def _figure(self, lines: List[str], i: int, kind: str, name: str, out: List[str]) -> int:
        """A screenshot (light and dark pair, lazy-loaded, click to enlarge) or an inline SVG diagram."""
        start = lines[i].strip()
        i += 1
        body: List[str] = []
        while i < len(lines) and lines[i].strip() != ":::":
            body.append(lines[i].strip())
            i += 1
        if i >= len(lines):
            raise ValueError("%s block is never closed with ':::'" % start)
        if not body or not body[0].startswith("alt:") or len(body[0][4:].strip()) < 12:
            raise ValueError("%s: the first line must be 'alt: <what the picture shows>' (12+ characters)" % start)
        alt = body[0][4:].strip()
        caption = "\n".join(l for l in body[1:]).strip()
        if not caption:
            raise ValueError("%s needs a caption after the alt line" % start)
        self._text(caption)
        cap = self.inline.render(caption)
        alt_attr = html.escape(alt, quote=True)
        self.figures.append("%s:%s" % (kind, name))
        try:
            if self.assets is None:
                raise ValueError("%s: pictures can only be rendered with the docs assets loaded" % start)
            if kind == "diagram":
                self.assets.diagram(name)
            else:
                self.assets.screenshot(name)
        except ValueError as exc:
            if self.strict:
                raise
            # production: keep the page, show the caption without the picture, and report the problem
            self.problems.append(str(exc))
            out.append('<figure class="dx-figure dx-missing"><p class="dx-missing-note" role="note">%s</p>'
                       '<figcaption>%s</figcaption></figure>' % (alt_attr, cap))
            return i + 1
        if kind == "diagram":
            svg = self.assets.diagram(name)
            out.append('<figure class="dx-figure dx-fig-diagram"><div class="dx-svg" role="img" aria-label="%s">%s</div>'
                       '<figcaption>%s</figcaption></figure>' % (alt_attr, svg, cap))
        else:
            light, dark = self.assets.screenshot(name)
            w, h = max(1, light.width // DENSITY), max(1, light.height // DENSITY)

            def img(im, cls: str) -> str:
                return ('<img class="%s" src="%s" alt="%s" width="%d" height="%d" loading="lazy" decoding="async">'
                        % (cls, html.escape(im.url, quote=True), alt_attr, w, h))
            out.append('<figure class="dx-figure dx-shot"><a class="dx-zoom" href="%s" data-dark="%s">%s%s'
                       '<span class="dx-zoom-hint">Enlarge</span></a><figcaption>%s</figcaption></figure>'
                       % (html.escape(light.url, quote=True), html.escape(dark.url, quote=True),
                          img(light, "dx-light"), img(dark, "dx-dark"), cap))
        return i + 1

    def _quote(self, lines: List[str], i: int, out: List[str]) -> int:
        inner: List[str] = []
        while i < len(lines) and lines[i].lstrip().startswith(">"):
            inner.append(re.sub(r"^\s*> ?", "", lines[i]))
            i += 1
        m = re.match(r"^\[!(\w+)\]\s*(.*)$", inner[0].strip()) if inner else None
        if m and m.group(1).upper() in CALLOUTS:
            kind = m.group(1).upper()
            title = m.group(2).strip() or CALLOUTS[kind]
            self._text(title)
            out.append('<aside class="dx-callout dx-%s"><p class="dx-callout-title">%s</p>%s</aside>'
                       % (kind.lower(), self.inline.render(title), self.blocks(inner[1:])))
        else:
            out.append("<blockquote>%s</blockquote>" % self.blocks(inner))
        return i

    def _table(self, lines: List[str], i: int, out: List[str]) -> int:
        def cells(row: str) -> List[str]:
            row = row.strip()
            if row.startswith("|"):
                row = row[1:]
            if row.endswith("|") and not row.endswith("\\|"):
                row = row[:-1]
            return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", row)]

        head = cells(lines[i])
        aligns = []
        for c in cells(lines[i + 1]):
            aligns.append("num" if c.endswith(":") and not c.startswith(":") else "")
        rows = []
        i += 2
        while i < len(lines) and lines[i].strip() and "|" in lines[i]:
            rows.append(cells(lines[i]))
            i += 1
        for r in [head] + rows:
            self._text(" ".join(r))

        def td(tag: str, k: int, c: str) -> str:
            cls = ' class="num"' if k < len(aligns) and aligns[k] else ""
            return "<%s%s>%s</%s>" % (tag, cls, self.inline.render(c), tag)

        thead = "<tr>%s</tr>" % "".join(td("th", k, c) for k, c in enumerate(head))
        tbody = "".join("<tr>%s</tr>" % "".join(td("td", k, c) for k, c in enumerate(r)) for r in rows)
        out.append('<div class="dx-table"><table><thead>%s</thead><tbody>%s</tbody></table></div>' % (thead, tbody))
        return i

    def _list(self, lines: List[str], i: int, out: List[str]) -> int:
        first = _LIST.match(lines[i])
        base = len(first.group(1))
        ordered = first.group(2)[0].isdigit()
        start = int(first.group(2)[:-1]) if ordered else 1
        items: List[List[str]] = []
        while i < len(lines):
            line = lines[i]
            m = _LIST.match(line)
            if m and len(m.group(1)) == base and (m.group(2)[0].isdigit()) == ordered:
                items.append([m.group(3)])
                i += 1
                continue
            if not line.strip():
                nxt = lines[i + 1] if i + 1 < len(lines) else ""
                if nxt.strip() and (len(nxt) - len(nxt.lstrip())) > base:
                    items[-1].append("")
                    i += 1
                    continue
                break
            if (len(line) - len(line.lstrip())) > base:
                items[-1].append(line)
                i += 1
                continue
            break
        rendered = []
        for item in items:
            text_lines, rest = [item[0]], []
            for k, l in enumerate(item[1:], 1):
                if _LIST.match(l) or _FENCE.match(l) or not l.strip() or l.lstrip().startswith(">"):
                    rest = item[k:]
                    break
                text_lines.append(l.strip())
            self._text(" ".join(text_lines))
            inner = self.inline.render("\n".join(text_lines))
            if rest:
                pad = min((len(l) - len(l.lstrip()) for l in rest if l.strip()), default=0)
                inner += self.blocks([l[pad:] for l in rest])
            rendered.append("<li>%s</li>" % inner)
        tag = "ol" if ordered else "ul"
        attr = ' start="%d"' % start if ordered and start != 1 else ""
        out.append("<%s%s>%s</%s>" % (tag, attr, "".join(rendered), tag))
        return i

    def _paragraph(self, lines: List[str], i: int, out: List[str]) -> int:
        buf: List[str] = []
        while i < len(lines) and lines[i].strip():
            line = lines[i]
            if buf and (_HEADING.match(line) or _FENCE.match(line) or _LIST.match(line)
                        or line.lstrip().startswith(">") or line.strip().startswith(":::")):
                break
            buf.append(line.strip() if not line.endswith(" \\") else line.strip()[:-1].rstrip() + " \\")
            i += 1
        text = "\n".join(buf)
        self._text(text.replace(" \\\n", " "))
        out.append("<p>%s</p>" % self.inline.render(text))
        return i


def render(text: str, assets: Optional[Assets] = None, strict: bool = True,
           problems: Optional[List[str]] = None) -> Rendered:
    return Renderer(assets, strict, problems).render(text)


def first_paragraph(text: Optional[str]) -> str:
    return plain((text or "").strip().split("\n\n")[0])


__all__ = ["Heading", "Rendered", "parse_front_matter", "plain", "render", "slugify"]
