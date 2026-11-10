#!/usr/bin/env python3
"""Keeps only the references that the chapters cite, as APA requires. Writes chapters3/7-references.md in place and
saves the full verified list beside it as research/all-references.md."""
import re
from pathlib import Path

here = Path(__file__).resolve().parent
chapters = here / "chapters3"
text = "\n".join((chapters / name).read_text() for name in ("0-front.md", "1-introduction.md", "2-literature.md", "3-methodology.md",
                                                           "4-design.md", "5-implementation.md", "8-appendices.md"))
source = chapters / "7-references.md"
full = here / "research" / "all-references.md"
if not full.exists():
    full.write_text(source.read_text())
lines = full.read_text().split("\n")
kept, dropped = [], []
for line in lines:
    if not line.startswith("@ "):
        kept.append(line)
        continue
    entry = line[2:]
    year = re.search(r"\((\d{4}[a-z]?|n\.d\.(?:-[a-z])?)", entry)
    first = re.split(r",| \(|\. \(", entry, maxsplit=1)[0].strip().strip("*")
    if not year:
        kept.append(line)
        continue
    stamp = re.escape(year.group(1))
    name = re.escape(first)
    cited = re.search(name + r"[^\n()]{0,90}?[(, ]\s*" + stamp, text) or re.search(name + r"[^\n]{0,60}?" + stamp, text)
    (kept if cited else dropped).append(line)
source.write_text("\n".join(kept))
print(len([l for l in kept if l.startswith("@ ")]), "kept;", len(dropped), "dropped")
