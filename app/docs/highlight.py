"""Syntax highlighting for documentation code blocks, done on the server.

Small regex tokenizers for the languages the docs use (shell, YAML, JSON, Python, plus plain text). The output
is escaped HTML with `<span class="tk-...">` tokens and nothing else, so it is safe under the dashboard's strict
Content Security Policy and readable without JavaScript. Unknown languages are escaped and left unhighlighted.
"""
from __future__ import annotations

import html
import re
from typing import Dict, List, Pattern, Tuple

_PY_KEYWORDS = ("False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|"
                "finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|"
                "with|yield")

# Each language is an ordered list of (token class, pattern). The first alternative that matches at a position
# wins, so put comments and strings before anything that could match inside them.
_RULES: Dict[str, List[Tuple[str, str]]] = {
    "bash": [
        ("comment", r"(?:(?<=\s)|^)#[^\n]*"),
        ("string", r"'[^'\n]*'|\"(?:\\.|[^\"\\\n])*\""),
        ("var", r"\$\{[^}\n]*\}|\$[A-Za-z_][A-Za-z0-9_]*"),
        ("cmd", r"^[ \t]*(?:\$ )?[A-Za-z_.][\w./-]*"),
        ("flag", r"(?<![\w-])--?[A-Za-z][\w-]*"),
        ("op", r"&&|\|\||[|&;<>]"),
    ],
    "yaml": [
        ("comment", r"(?:(?<=\s)|^)#[^\n]*"),
        ("key", r"^[ \t]*(?:- )?[\w.\-\"']+(?=:(?:\s|$))"),
        ("string", r"'[^'\n]*'|\"(?:\\.|[^\"\\\n])*\""),
        ("literal", r"\b(?:true|false|null|yes|no)\b"),
        ("number", r"(?<![\w.])-?\d+(?:\.\d+)?\b"),
        ("var", r"\$\{\{[^}\n]*\}\}"),
    ],
    "json": [
        ("key", r"\"(?:\\.|[^\"\\\n])*\"(?=\s*:)"),
        ("string", r"\"(?:\\.|[^\"\\\n])*\""),
        ("literal", r"\b(?:true|false|null)\b"),
        ("number", r"-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b"),
    ],
    "python": [
        ("comment", r"#[^\n]*"),
        ("string", r"(?:[rRbBuUfF]{0,2})(?:\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*')"),
        ("decorator", r"^[ \t]*@[\w.]+"),
        ("keyword", r"\b(?:%s)\b" % _PY_KEYWORDS),
        ("func", r"(?<=\bdef )[A-Za-z_]\w*|(?<=\bclass )[A-Za-z_]\w*"),
        ("number", r"\b\d+(?:\.\d+)?\b"),
    ],
}
_ALIASES = {"sh": "bash", "shell": "bash", "console": "bash", "zsh": "bash", "yml": "yaml", "py": "python",
            "jsonc": "json", "env": "bash", "dotenv": "bash"}
_COMPILED: Dict[str, Pattern[str]] = {}

LANGUAGE_LABELS = {"bash": "Shell", "yaml": "YAML", "json": "JSON", "python": "Python", "text": "Text",
                   "http": "HTTP", "diagram": "Diagram"}


def canonical(lang: str) -> str:
    lang = (lang or "").strip().lower()
    return _ALIASES.get(lang, lang or "text")


def _pattern(lang: str) -> Pattern[str]:
    if lang not in _COMPILED:
        parts = ["(?P<%s>%s)" % (name.replace("-", "_") + "__%d" % i, rx) for i, (name, rx) in enumerate(_RULES[lang])]
        _COMPILED[lang] = re.compile("|".join(parts), re.MULTILINE)
    return _COMPILED[lang]


def highlight(code: str, lang: str) -> str:
    """Escaped HTML for `code`, with token spans when the language is known."""
    lang = canonical(lang)
    if lang not in _RULES:
        return html.escape(code, quote=False)
    out, last = [], 0
    for m in _pattern(lang).finditer(code):
        if m.start() == m.end():
            continue
        out.append(html.escape(code[last:m.start()], quote=False))
        kind = m.lastgroup.split("__")[0]
        out.append('<span class="tk-%s">%s</span>' % (kind, html.escape(m.group(0), quote=False)))
        last = m.end()
    out.append(html.escape(code[last:], quote=False))
    return "".join(out)


__all__ = ["LANGUAGE_LABELS", "canonical", "highlight"]
