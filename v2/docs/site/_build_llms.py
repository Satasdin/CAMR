"""Write llms-full.txt: every page llms.txt lists under "## Docs", in that order, in one file for agents.

    .venv/bin/python docs/site/_build_llms.py

Run it again after changing a page. Links between pages are rewritten as paths from the v2 folder, where
llms-full.txt sits, so they still point at the right files. Web links and anchors stay as they are.
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path

V2 = Path(__file__).resolve().parents[2]
LIST = V2 / "llms.txt"
OUT = V2 / "llms-full.txt"
_ENTRY = re.compile(r"^- \[[^\]]+\]\(([^)\s]+)\)")
_LINK = re.compile(r"(\]\()([^)\s]+)(\))")
_WEB = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def pages(listing: str) -> list[str]:
    """The paths listed under "## Docs", in order."""
    out, inside = [], False
    for line in listing.splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## Docs"
            continue
        m = _ENTRY.match(line) if inside else None
        if m:
            out.append(m.group(1))
    return out


def rebase(text: str, page: str) -> str:
    """The relative links in ``page`` (a path from v2), made relative to v2 instead."""
    base = posixpath.dirname(page)

    def fix(m: re.Match) -> str:
        target = m.group(2)
        if _WEB.match(target) or target.startswith(("#", "/")):
            return m.group(0)
        path, hash_, anchor = target.partition("#")
        return f"{m.group(1)}{posixpath.normpath(posixpath.join(base, path))}{hash_}{anchor}{m.group(3)}"

    return _LINK.sub(fix, text)


def build() -> str:
    """llms.txt's title and summary, then each page with the path it came from."""
    listing = LIST.read_text(encoding="utf-8")
    parts = [listing.split("\n## ", 1)[0].rstrip()]
    for page in pages(listing):
        body = (V2 / page).read_text(encoding="utf-8").strip()
        parts.append(f"---\n\nSource: {page}\n\n{rebase(body, page)}")
    return "\n\n".join(parts) + "\n"


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"{OUT.name}: {len(pages(LIST.read_text(encoding='utf-8')))} pages")
