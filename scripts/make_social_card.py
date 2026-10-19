"""Draw app/static/social-card.png, the 1200x630 picture link previews and search results show for /docs pages.

Run it again after changing the brand mark or the wording below:

    pip install pillow          # only needed for this script, not by the dashboard
    python scripts/make_social_card.py

It uses the IBM Plex fonts the dashboard already bundles, so the card matches the site.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "app" / "static" / "fonts"
OUT = ROOT / "app" / "static" / "social-card.png"

W, H = 1200, 630
BG, INK, MUTED, LINE = "#0e1116", "#e5e7eb", "#a2aab7", "#242a34"
MARK, MARK_CELL, MARK_HOT = "#2f3dc4", "#8b93e0", "#ff8a65"

LABEL = "AgentSec Docs"
TITLE = "Security testing for AI agents"
SUBTITLE = "Open-source adversarial tests, from your terminal to CI"
TOPICS = ["Prompt injection", "Tool misuse", "Data leaks", "Memory poisoning", "MCP security",
          "OWASP agentic risks"]
FOOTER = "Invaris Labs"


def font(weight: int, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / ("ibm-plex-sans-latin-%d-normal.woff2" % weight)), size)


def mark(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> None:
    """The AgentSec mark (app/static/mark.svg): a 3x3 grid with one highlighted cell."""
    s = size / 24.0
    draw.rounded_rectangle([x, y, x + size, y + size], radius=round(6 * s), fill=MARK)
    for row in range(3):
        for col in range(3):
            cx, cy = x + (5 + 5 * col) * s, y + (5 + 5 * row) * s
            hot = (row, col) == (1, 2)
            draw.rounded_rectangle([cx, cy, cx + 4 * s, cy + 4 * s], radius=round(s),
                                   fill=MARK_HOT if hot else MARK_CELL)


def main() -> None:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    pad = 80
    mark(d, pad, pad, 96)
    d.text((pad + 124, pad + 48), LABEL, font=font(600, 44), fill=INK, anchor="lm")
    d.text((pad, 268), TITLE, font=font(600, 68), fill=INK, anchor="ls")
    d.text((pad, 330), SUBTITLE, font=font(400, 38), fill=MUTED, anchor="ls")

    # Topic chips, wrapped onto as many rows as they need.
    x, y, chip_font = pad, 400, font(500, 26)
    for topic in TOPICS:
        w = d.textlength(topic, font=chip_font) + 36
        if x + w > W - pad:
            x, y = pad, y + 62
        d.rounded_rectangle([x, y, x + w, y + 46], radius=23, outline=LINE, width=2)
        d.text((x + w / 2, y + 23), topic, font=chip_font, fill=INK, anchor="mm")
        x += w + 14

    d.line([pad, H - 92, W - pad, H - 92], fill=LINE, width=2)
    d.text((pad, H - 52), FOOTER, font=font(500, 28), fill=MUTED, anchor="ls")
    d.text((W - pad, H - 52), "Apache-2.0", font=font(400, 28), fill=MUTED, anchor="rs")
    img.save(OUT, optimize=True)
    print("wrote %s (%d bytes)" % (OUT.relative_to(ROOT), OUT.stat().st_size))


if __name__ == "__main__":
    main()
