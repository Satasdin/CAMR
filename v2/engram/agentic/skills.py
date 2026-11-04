"""Skills: Markdown files of instructions in one folder (``~/.engram/skills`` by default), loaded only when the model
asks for one. The model sees each skill's name and one-line description in its instructions, and calls
``load_skill`` to read the whole file; so ten skills cost ten lines until one is needed.

A skill is ``<name>.md`` or ``<name>/SKILL.md``. Optional front matter gives its name and description:

    ---
    name: release-notes
    description: How to write the release notes for this project
    ---

Without it, the name is the file's and the description is the first line of text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

LIMIT = 64_000  # characters of one skill
MAX_SKILLS = 200
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)


@dataclass
class Skill:
    name: str
    description: str
    path: Path
    size: int

    def show(self) -> dict:
        return {"name": self.name, "description": self.description, "size": self.size}


def _front(text: str) -> tuple[dict[str, str], str]:
    m = _FRONT.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        k, sep, v = line.partition(":")
        if sep:
            meta[k.strip().lower()] = v.strip().strip("\"'")
    return meta, text[m.end():]


class Skills:
    def __init__(self, folder: Path):
        self.folder = Path(folder).expanduser()

    def all(self) -> list[Skill]:
        if not self.folder.is_dir():
            return []
        found: dict[str, Skill] = {}
        files = sorted(self.folder.glob("*.md")) + sorted(self.folder.glob("*/SKILL.md"))
        for f in files[:MAX_SKILLS * 2]:
            if f.is_symlink() or not f.is_file() or not f.resolve().is_relative_to(self.folder.resolve()):
                continue
            try:
                text = f.read_text(errors="replace")[:LIMIT]
            except OSError:
                continue
            meta, body = _front(text)
            name = meta.get("name") or (f.parent.name if f.name == "SKILL.md" else f.stem)
            if not _NAME.match(name) or name in found:
                continue
            first = next((x.strip("# ").strip() for x in body.splitlines() if x.strip()), "")
            found[name] = Skill(name, (meta.get("description") or first)[:200], f, f.stat().st_size)
            if len(found) >= MAX_SKILLS:
                break
        return sorted(found.values(), key=lambda s: s.name)

    def load(self, name: str) -> str:
        """The skill's instructions, without its front matter. KeyError when there is none by that name."""
        for s in self.all():
            if s.name == name:
                return _front(s.path.read_text(errors="replace")[:LIMIT])[1].strip()
        raise KeyError(name)

    def index(self, limit: int = 40) -> str:
        """One line per skill, for the model's instructions."""
        return "\n".join(f"- {s.name}: {s.description}" for s in self.all()[:limit])
