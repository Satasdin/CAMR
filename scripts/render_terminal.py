"""Render captured terminal output as a screenshot-style PNG (dark theme).

The text must be real output captured from a command, e.g.

    (echo '$ camr --help'; camr --help) > help.txt
    python scripts/render_terminal.py help.txt docs/figures/setup/terminal_help.png --title "camr --help"

Lines starting with "$ " are drawn as the prompt line; everything else is output.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
BG, BAR, FG, PROMPT, MUTED = "#0f1115", "#1c1f26", "#d7dae0", "#1baf7a", "#8a91a0"


def render(text: str, out: Path, title: str = "", max_lines: int = 60, size: int = 15) -> None:
    lines = text.rstrip("\n").splitlines()
    if len(lines) > max_lines:  # keep head and tail, mark the cut honestly
        lines = lines[: max_lines - 6] + [f"… ({len(lines) - max_lines + 5} lines omitted) …"] + lines[-5:]
    font, bold = ImageFont.truetype(FONT, size), ImageFont.truetype(FONT_BOLD, size)
    cw = font.getbbox("M")[2]
    lh = int(size * 1.45)
    width = max(80, max(len(line) for line in lines) + 4) * cw
    height = 44 + 20 + lh * len(lines) + 20
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width, 36], fill=BAR)
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):  # window buttons
        d.ellipse([14 + i * 22, 12, 26 + i * 22, 24], fill=c)
    if title:
        d.text((width // 2, 18), title, font=font, fill=MUTED, anchor="mm")
    y = 56
    for line in lines:
        if line.startswith("$ "):
            d.text((2 * cw, y), "$", font=bold, fill=PROMPT)
            d.text((4 * cw, y), line[2:], font=bold, fill=FG)
        else:
            d.text((2 * cw, y), line, font=font, fill=MUTED if line.startswith("…") else FG)
        y += lh
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("text_file")
    ap.add_argument("out")
    ap.add_argument("--title", default="")
    ap.add_argument("--max-lines", type=int, default=60)
    a = ap.parse_args()
    render(Path(a.text_file).read_text(), Path(a.out), a.title, a.max_lines)


if __name__ == "__main__":
    main()
