"""Screenshots and diagrams used by the documentation pages.

- Screenshots live in `images/` as WebP pairs, `<name>-light.webp` and `<name>-dark.webp`, captured from the real
  dashboard by `scripts/docs_screenshots.py`. Pages show the one matching the reader's theme; the other is never
  downloaded (it is lazy-loaded and hidden).
- Diagrams live in `diagrams/<name>.svg`. They are inlined into the page and coloured by docs.css classes, so they
  follow the theme too. They are our own files, but are still checked here: no scripts, event handlers, style
  attributes, links or embedded documents.

Both are read once, when the docs are loaded. Images are served by /docs/img/<file>, only for files listed here.
"""
from __future__ import annotations

import hashlib
import os
import re
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGES = os.path.join(HERE, "images")
DIAGRAMS = os.path.join(HERE, "diagrams")

IMAGE_NAME = re.compile(r"^([a-z0-9]+(?:-[a-z0-9]+)*)-(light|dark)\.webp$")
DIAGRAM_NAME = re.compile(r"^([a-z0-9]+(?:-[a-z0-9]+)*)\.svg$")
# Pictures are stored at twice their display size so they stay sharp on high-density screens.
DENSITY = 2


@dataclass
class Image:
    file: str
    path: str
    width: int          # pixels in the file
    height: int
    version: str        # content hash, appended to the URL so browsers may cache the file forever

    @property
    def url(self) -> str:
        return "/docs/img/%s?v=%s" % (self.file, self.version)


@dataclass
class Assets:
    images: Dict[str, Image] = field(default_factory=dict)      # by file name
    diagrams: Dict[str, str] = field(default_factory=dict)      # by name: sanitised <svg> markup

    def screenshot(self, name: str) -> Tuple[Image, Image]:
        light, dark = self.images.get(name + "-light.webp"), self.images.get(name + "-dark.webp")
        if not light or not dark:
            raise ValueError("screenshot %r needs images/%s-light.webp and images/%s-dark.webp" % (name, name, name))
        if (light.width, light.height) != (dark.width, dark.height):
            raise ValueError("screenshot %r: the light and dark images differ in size" % name)
        return light, dark

    def diagram(self, name: str) -> str:
        if name not in self.diagrams:
            raise ValueError("diagram %r needs diagrams/%s.svg" % (name, name))
        return self.diagrams[name]


def webp_size(data: bytes) -> Tuple[int, int]:
    """Width and height of a WebP file, from its header (lossy, lossless or extended)."""
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("not a WebP file")
    chunk = data[12:16]
    if chunk == b"VP8 ":
        if data[23:26] != b"\x9d\x01\x2a":
            raise ValueError("damaged WebP (VP8) header")
        w, h = struct.unpack("<HH", data[26:30])
        return w & 0x3FFF, h & 0x3FFF
    if chunk == b"VP8L":
        if data[20] != 0x2F:
            raise ValueError("damaged WebP (VP8L) header")
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8X":
        return int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
    raise ValueError("unknown WebP chunk %r" % chunk)


_SVG_FORBIDDEN = [
    (re.compile(r"<\s*script", re.I), "a script"),
    (re.compile(r"<\s*foreignObject", re.I), "foreignObject"),
    (re.compile(r"<\s*(?:image|use|a|iframe|object|embed|style)\b", re.I), "an element that loads or styles content"),
    (re.compile(r"\son[a-z]+\s*=", re.I), "an event handler"),
    (re.compile(r"\sstyle\s*=", re.I), "a style attribute (the Content Security Policy forbids them)"),
    (re.compile(r"href\s*=", re.I), "a link"),
    (re.compile(r"<!(?:DOCTYPE|ENTITY)", re.I), "a DOCTYPE or entity"),
    (re.compile(r"url\s*\(\s*(?!#)", re.I), "a url() reference to another document"),
]


def clean_svg(text: str, name: str) -> str:
    text = re.sub(r"<\?xml[^>]*\?>", "", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()
    if not text.startswith("<svg") or not text.endswith("</svg>"):
        raise ValueError("diagram %r must be a single <svg> element" % name)
    for pattern, what in _SVG_FORBIDDEN:
        if pattern.search(text):
            raise ValueError("diagram %r contains %s" % (name, what))
    if "viewBox" not in text.split(">", 1)[0]:
        raise ValueError("diagram %r needs a viewBox" % name)
    # decorative for assistive technology: the figure carries the description
    return text.replace("<svg", '<svg aria-hidden="true" focusable="false"', 1)


def load_assets(images: str = IMAGES, diagrams: str = DIAGRAMS, errors: Optional[List[str]] = None) -> Assets:
    """Read every image header and diagram. A misnamed or damaged file raises ValueError, or, when an `errors` list
    is given (the running dashboard), is left out and described there."""
    assets = Assets()

    def bad(msg: str) -> None:
        if errors is None:
            raise ValueError(msg)
        errors.append(msg)

    if os.path.isdir(images):
        for fname in sorted(os.listdir(images)):
            if fname.startswith("."):
                continue
            if not IMAGE_NAME.match(fname):
                bad("images/%s: name it <name>-light.webp or <name>-dark.webp" % fname)
                continue
            path = os.path.join(images, fname)
            try:
                with open(path, "rb") as fh:
                    data = fh.read()
                w, h = webp_size(data)
            except (OSError, ValueError) as exc:
                bad("images/%s: %s" % (fname, exc))
                continue
            assets.images[fname] = Image(fname, path, w, h, hashlib.sha256(data).hexdigest()[:12])
    if os.path.isdir(diagrams):
        for fname in sorted(os.listdir(diagrams)):
            if fname.startswith("."):
                continue
            m = DIAGRAM_NAME.match(fname)
            if not m:
                bad("diagrams/%s: name it <name>.svg" % fname)
                continue
            try:
                with open(os.path.join(diagrams, fname), encoding="utf-8") as fh:
                    assets.diagrams[m.group(1)] = clean_svg(fh.read(), m.group(1))
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                bad("diagrams/%s: %s" % (fname, exc))
    return assets
