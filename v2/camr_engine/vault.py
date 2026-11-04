"""The vault: the archive, where every moment is kept as words a person can read, one Markdown note per moment.

The folder opens in Obsidian as it is. Each note has YAML front matter (its id, day, date, room, reach, tags,
strength, pinned, asleep and links) and then the moment's words. Links between notes are ``[[note-id]]`` wikilinks,
called doors. A door strengthens when its two notes share a room or are used in the same answer, so related notes
come in together.

A note's strength fades 5% a day unless it is used, and each use adds strength back. Pinned notes never fade.
Nothing here is ever deleted: a faded note, or one whose room's notes went to sleep, keeps its words. Only a person
deletes a note, by deleting its file; the vault then forgets it. A moment's note is never written over with other
words: if its id already holds a different note (a moment the rooms lost, say after a crash), that note is first
kept under a fresh id.

The files are the truth. A hidden index beside them (``.camr-index.json``, which Obsidian ignores) only saves
re-reading every file on opening; a note changed by hand in Obsidian is read again because its file changed. While
the vault is open, ``rescan`` picks up what a person changed: new and deleted notes, and edits.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Iterable

FADE = 0.05  # strength lost per day unused
USE = 1.0  # strength a use adds
SHARE = 0.5  # what a door gains when its two notes share a room
TOGETHER = 1.0  # what a door gains when its two notes are used in the same answer
FLOOR = 0.1  # below this a note counts as faded (its words stay)
CORE = "core"  # the tag of notes that belong in the core
INDEX = ".camr-index.json"

_BAD = re.compile(r"[/\\\x00-\x1f\[\]|#^:]")  # path separators, control characters, and what breaks a wikilink
_PLAIN = re.compile(r"^[A-Za-z_][A-Za-z0-9_./-]*$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_INT = re.compile(r"^-?\d+$")
_FLOAT = re.compile(r"^-?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?$")
_LINK = re.compile(r"^\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]$")
_WORDS = {"true", "false", "yes", "no", "on", "off", "null", "~", "y", "n"}
_ORDER = ("id", "day", "date", "room", "reach", "moment", "tags", "strength", "pinned", "asleep", "used", "as_of",
          "links", "doors")
_log = logging.getLogger(__name__)


@dataclass(slots=True)
class Note:
    id: str
    text: str | None = None  # None in the index: read() fetches the words from the file
    day: int | None = None
    date: str | None = None  # ISO date, shown by Obsidian as a date
    room: int | None = None
    reach: str | None = None
    moment: int | None = None
    tags: list[str] = field(default_factory=list)
    strength: float = 1.0
    pinned: bool = False
    asleep: bool = False  # its room's notes are asleep: only these words remain
    used: int | None = None  # the last day it was used in an answer
    as_of: int | None = None  # the day ``strength`` was last brought up to date
    links: dict[str, float] = field(default_factory=dict)  # doors: the note at the other side, and how strong
    extra: dict = field(default_factory=dict)  # properties a person added by hand, kept as they are
    digest: str = ""  # a hash of the words, so a change shows without reading them

    @property
    def faded(self) -> bool:
        return not self.pinned and self.strength < FLOOR


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower() or "m"


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def _ok(nid) -> bool:
    return (isinstance(nid, str) and 0 < len(nid) <= 200 and not nid.startswith(".") and nid == nid.strip()
            and not _BAD.search(nid))


def _check(nid: str) -> str:
    """A note id is its file's name: never a path, and always something a wikilink can point at."""
    if not _ok(nid):
        raise ValueError(f"not a note id: {nid!r}")
    return nid


# YAML, only as much as front matter needs: scalars, lists of scalars, and what Obsidian writes when a person edits.

def _scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(round(v, 4))
    s = str(v)
    if (_PLAIN.match(s) and s.lower() not in _WORDS) or _DATE.match(s):
        return s
    return json.dumps(s, ensure_ascii=False)


def _value(s: str):
    s = s.strip()
    if not s:
        return None
    if s[0] == '"':
        try:
            return json.loads(s)
        except ValueError:
            return s.strip('"')
    if s[0] == "'":
        return s[1:-1].replace("''", "'") if len(s) > 1 and s[-1] == "'" else s[1:]
    if " #" in s:
        s = s.split(" #", 1)[0].rstrip()
    low = s.lower()
    if low in ("null", "~"):
        return None
    if low in ("true", "false"):
        return low == "true"
    if _INT.match(s):
        return int(s)
    if _FLOAT.match(s):
        return float(s)
    if s.startswith("[") and s.endswith("]") and not s.startswith("[["):
        try:
            got = json.loads(s)
            return got if isinstance(got, list) else [got]
        except ValueError:
            inner = s[1:-1].strip()
            return [_value(x) for x in inner.split(",")] if inner else []
    return s


def _front(lines: list[str]) -> dict:
    out: dict = {}
    key = None
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        s = raw.strip()
        if s == "-" or s.startswith("- "):
            if key is not None:
                if not isinstance(out.get(key), list):
                    out[key] = []
                out[key].append(_value(s[1:]))
            continue
        if raw[0].isspace():  # the rest of a long text value
            if key is not None and isinstance(out.get(key), str):
                out[key] = (out[key] + " " + s).strip()
            continue
        if ":" not in s:
            continue
        key, _, rest = s.partition(":")
        key, rest = key.strip(), rest.strip()
        out[key] = "" if rest in ("|", ">", "|-", ">-") else _value(rest)
    return out


def split(text: str) -> tuple[dict, str]:
    """A note file as (its front matter, its body)."""
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return _front([x.rstrip("\r") for x in lines[1:i]]), "\n".join(lines[i + 1:])
    return {}, text


def _int(v) -> int | None:
    try:
        return None if v is None or isinstance(v, bool) else int(v)
    except (TypeError, ValueError):
        return None


def _float(v, default: float) -> float:
    try:
        return default if v is None or isinstance(v, bool) else float(v)
    except (TypeError, ValueError):
        return default


def _bool(v) -> bool:
    return v if isinstance(v, bool) else str(v).strip().lower() in ("true", "yes", "1", "on")


def _list(v) -> list:
    if v is None or v == "":
        return []
    return list(v) if isinstance(v, list) else [v]


def parse(nid: str, text: str) -> Note:
    """A note from its file's text. The id is the file's name, since that is what a wikilink points at."""
    meta, body = split(text)
    words = body[1:] if body.startswith("\n") else body
    words = words[:-1] if words.endswith("\n") else words
    doors = [_float(x, SHARE) for x in _list(meta.get("doors"))]
    links: dict[str, float] = {}
    for i, x in enumerate(_list(meta.get("links"))):
        m = _LINK.match(str(x).strip())
        if m:
            links[m.group(1).strip()] = doors[i] if i < len(doors) else SHARE
    date = meta.get("date")
    return Note(id=nid, text=words, day=_int(meta.get("day")), date=None if date in (None, "") else str(date),
                room=_int(meta.get("room")), reach=None if meta.get("reach") in (None, "") else str(meta["reach"]),
                moment=_int(meta.get("moment")),
                tags=[str(t).lstrip("#") for t in _list(meta.get("tags")) if t not in (None, "")],
                strength=_float(meta.get("strength"), 1.0), pinned=_bool(meta.get("pinned", False)),
                asleep=_bool(meta.get("asleep", False)), used=_int(meta.get("used")), as_of=_int(meta.get("as_of")),
                links=links, extra={k: v for k, v in meta.items() if k not in _ORDER}, digest=_digest(words))


def render(note: Note) -> str:
    """A note as its Markdown file: front matter, then the words."""
    doors = sorted(note.links.items(), key=lambda kv: (-kv[1], kv[0]))
    meta = {"id": note.id, "day": note.day, "date": note.date, "room": note.room, "reach": note.reach,
            "moment": note.moment, "tags": list(note.tags), "strength": round(float(note.strength), 4),
            "pinned": note.pinned, "asleep": note.asleep, "used": note.used, "as_of": note.as_of,
            "links": [f"[[{k}]]" for k, _ in doors], "doors": [round(float(v), 4) for _, v in doors]}
    meta.update(note.extra)
    out = ["---"]
    for k, v in meta.items():
        if isinstance(v, (list, tuple)):
            out.append(f"{k}: []" if not v else f"{k}:")
            out += [f"  - {_scalar(x)}" for x in v]
        else:
            out.append(f"{k}: {_scalar(v)}")
    out.append("---")
    return "\n".join(out) + "\n" + (note.text or "") + "\n"


class Vault:
    """A folder of notes. ``reach`` (for example ``global`` or ``project:tally``) is written on every note and
    names its ids, so notes from different reaches never share a name."""

    def __init__(self, path: Path, *, reach: str | None = None):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.reach = reach
        self.prefix = _slug(reach) if reach else "m"
        self.version = 0  # goes up on every change, so the core can tell when to look again
        self.epoch: dt.date | None = None  # the date of day 0, learnt from notes written with both
        self.moved: dict[str, str] = {}  # a moment's note id -> the fresh id its older, different words went to
        self._notes: dict[str, Note] = {}
        self._files: dict[str, tuple[int, int]] = {}  # id -> (mtime_ns, size) when last read or written
        self._tags: dict[str, set[str]] = {}
        self._folder: int | None = None  # the folder's mtime when last listed, so a look can skip listing it
        self._load()

    # -- reading

    def file(self, nid: str) -> Path:
        return self.path / f"{_check(nid)}.md"

    def moment_id(self, mid: int) -> str:
        return f"{self.prefix}-{mid:06d}"

    def __contains__(self, nid: str) -> bool:
        return nid in self._notes

    def __len__(self) -> int:
        return len(self._notes)

    def get(self, nid: str) -> Note | None:
        """A note's properties, without its words (read-only)."""
        return self._notes.get(nid)

    def read(self, nid: str) -> Note | None:
        """A note with its words, read from its file; None when a person deleted the file (the note is forgotten)."""
        path = self.file(nid)
        try:
            note = parse(nid, path.read_text(encoding="utf-8"))
            st = path.stat()
        except FileNotFoundError:
            self._forget(nid)
            return None
        if self._files.get(nid) != (st.st_mtime_ns, st.st_size):  # new to the index, or changed by hand
            self._keep(note, path)
        return note

    def notes(self, *, tag: str | None = None, room: int | None = None) -> list[Note]:
        """Every note's properties (read-only), by id; only those with ``tag`` or in ``room`` when given."""
        ids = sorted(self._tags.get(tag, ())) if tag is not None else sorted(self._notes)
        out = [self._notes[i] for i in ids]
        return out if room is None else [n for n in out if n.room == room]

    def neighbours(self, nid: str, n: int | None = None) -> list[tuple[str, float]]:
        """The notes behind a note's doors, strongest door first."""
        note = self._notes.get(nid)
        if note is None:
            return []
        doors = sorted(((k, v) for k, v in note.links.items() if k in self._notes), key=lambda kv: (-kv[1], kv[0]))
        return doors if n is None else doors[:n]

    def strength(self, nid: str) -> float:
        note = self._notes.get(nid)
        return 0.0 if note is None else note.strength

    def day_of(self, date: dt.date) -> int | None:
        """The day number of ``date``, counted as the notes count their days (None before any note has a day)."""
        if self.epoch is not None:
            return (date - self.epoch).days
        days = [n.day for n in self._notes.values() if n.day is not None]
        return max(days) if days else None

    def disk_bytes(self) -> int:
        return sum(size for _, size in self._files.values())

    # -- writing

    def write(self, text: str, *, day: int | None = None, date: dt.date | str | None = None, room: int | None = None,
              moment: int | None = None, tags: Iterable[str] = (), pinned: bool = False, nid: str | None = None
              ) -> Note:
        """A new note holding ``text`` (a moment's words when ``moment`` is given). Its id is the moment's, or
        ``nid``, or the next free one. A moment's id that already holds other words keeps them under a fresh id
        first (see ``moved``)."""
        if nid is None:
            nid = self.moment_id(moment) if moment is not None else self._free()
            if moment is not None:
                self._set_aside(nid, text)
        date = date.isoformat() if isinstance(date, dt.date) else date
        note = Note(id=_check(nid), text=text, day=day, date=date, room=room, reach=self.reach, moment=moment,
                    tags=[t.lstrip("#") for t in tags], pinned=pinned, as_of=day, digest=_digest(text))
        self._save(note)
        return note

    def link(self, a: str, b: str, by: float = SHARE) -> None:
        """Strengthen the door between two notes, both ways."""
        self.link_many(a, [b], by)

    def link_many(self, a: str, others: Iterable[str], by: float = SHARE) -> None:
        """Strengthen the doors from ``a`` to each of ``others``, both ways, rewriting each note once."""
        others = [o for o in dict.fromkeys(others) if o != a and o in self._notes]
        if a not in self._notes or not others:
            return
        note = self._fresh(a)
        if note is None:
            return
        there = []
        for o in others:
            other = self._fresh(o)
            if other is None:  # its file was deleted: no door to it
                continue
            other.links[a] = other.links.get(a, 0.0) + by
            self._save(other)
            there.append(o)
        for o in there:
            note.links[o] = note.links.get(o, 0.0) + by
        if there:
            self._save(note)

    def use(self, nids: Iterable[str], day: int) -> None:
        """Notes used in one answer on ``day``: each gains strength, and the doors between them strengthen."""
        notes = [self._fresh(n) for n in dict.fromkeys(nids) if n in self._notes]
        notes = [n for n in notes if n is not None]  # a deleted file is skipped
        for note in notes:
            self._age(note, day)
            note.strength = round(note.strength + USE, 4)
            note.used = day
            for other in notes:
                if other.id != note.id:
                    note.links[other.id] = note.links.get(other.id, 0.0) + TOGETHER
            self._save(note)

    def fade(self, today: int) -> int:
        """Bring every note's strength up to ``today``: 5% a day since it was last used or faded. Pinned notes keep
        theirs. Returns how many notes changed."""
        changed = 0
        for nid in list(self._notes):
            meta = self._notes[nid]
            if meta.pinned or (meta.as_of if meta.as_of is not None else meta.day) is None:
                continue
            if today <= (meta.as_of if meta.as_of is not None else meta.day):
                continue
            note = self._fresh(nid)
            if note is not None and self._age(note, today):
                self._save(note)
                changed += 1
        return changed

    def update(self, nid: str, **changes) -> Note | None:
        """Change a note's properties (tags, pinned, asleep, room, ...); its words stay as they are. None when its
        file was deleted."""
        names = {f.name for f in fields(Note)} - {"id", "text", "digest", "extra"}
        bad = set(changes) - names
        if bad:
            raise ValueError(f"not note properties: {sorted(bad)}")
        note = self._fresh(nid)
        if note is None:
            return None
        for k, v in changes.items():
            setattr(note, k, list(v) if k == "tags" else v)
        self._save(note)
        return note

    def pin(self, nid: str, on: bool = True) -> Note | None:
        return self.update(nid, pinned=on)

    def tag(self, nid: str, *tags: str) -> Note | None:
        note = self._fresh(nid)
        if note is None:
            return None
        return self.update(nid, tags=list(dict.fromkeys(note.tags + [t.lstrip("#") for t in tags])))

    def untag(self, nid: str, *tags: str) -> Note | None:
        note = self._fresh(nid)
        if note is None:
            return None
        return self.update(nid, tags=[t for t in note.tags if t not in tags])

    def save(self) -> None:
        """Save the index, so the next opening need not read every note again."""
        index = {"reach": self.reach, "epoch": self.epoch.isoformat() if self.epoch else None,
                 "notes": {nid: {**{k: v for k, v in asdict(n).items() if k != "text"}, "file": list(self._files[nid])}
                           for nid, n in self._notes.items() if nid in self._files}}
        tmp = self.path / f"{INDEX}.tmp"
        before = self._stamp()
        tmp.write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, self.path / INDEX)
        self._ours(before)

    def close(self) -> None:
        self.save()

    def rescan(self, *, full: bool = False, tag: str | None = CORE) -> bool:
        """Pick up what a person changed by hand while the vault is open. Returns True when anything changed.

        Cheap by default, so it can run before every answer: one look at the folder's time finds new and deleted
        notes (the folder is listed only when something other than the vault changed it), and only the files of
        notes tagged ``tag`` are checked for edits. ``full`` lists the folder and checks every note's file, for a
        nap or a person asking."""
        start = self.version
        now = self._stamp()
        if full or now != self._folder:
            self._folder = now  # taken before listing, so a change made while listing shows next time
            names = set(self._names())
            for nid in [n for n in self._notes if n not in names]:
                self._forget(nid)
            for nid in sorted(names - self._notes.keys()):
                try:
                    self.read(nid)
                except (OSError, UnicodeDecodeError):
                    continue
        check = list(self._notes) if full else sorted(self._tags.get(tag, ())) if tag is not None else []
        for nid in check:
            try:
                st = self.file(nid).stat()
            except FileNotFoundError:
                self._forget(nid)
                continue
            if self._files.get(nid) != (st.st_mtime_ns, st.st_size):
                try:
                    self.read(nid)
                except (OSError, UnicodeDecodeError):
                    continue
        return self.version != start

    # -- inside

    def _free(self) -> str:
        k = len(self._notes) + 1
        while f"{self.prefix}-note-{k:04d}" in self._notes or self.file(f"{self.prefix}-note-{k:04d}").exists():
            k += 1
        return f"{self.prefix}-note-{k:04d}"

    def _set_aside(self, nid: str, text: str) -> None:
        """Before a moment's note is written: when its file already holds other words, keep them under a fresh id
        (its moment and room cleared, since those numbers now belong to the new moment) instead of writing over
        them."""
        try:
            old = parse(nid, self.file(nid).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        if old.digest == _digest(text):
            return
        k = 1
        while f"{nid}-{k}" in self._notes or self.file(f"{nid}-{k}").exists():
            k += 1
        old.id, old.moment, old.room = f"{nid}-{k}", None, None
        old.extra = {**old.extra, "moved_from": nid}
        self._save(old)
        self.moved[nid] = old.id
        _log.warning("vault %s: note %s already held other words; kept them as %s", self.path, nid, old.id)

    def _forget(self, nid: str) -> None:
        """A note whose file is gone: drop it from the index."""
        note = self._notes.pop(nid, None)
        self._files.pop(nid, None)
        if note is not None:
            for t in note.tags:
                self._tags.get(t, set()).discard(nid)
            self.version += 1

    def _names(self) -> list[str]:
        """The ids of the note files in the folder."""
        out = []
        with os.scandir(self.path) as it:
            for entry in it:
                if entry.name.endswith(".md") and not entry.name.startswith(".") and entry.is_file():
                    if _ok(entry.name[:-3]):
                        out.append(entry.name[:-3])
        return out

    def _stamp(self) -> int | None:
        try:
            return self.path.stat().st_mtime_ns
        except FileNotFoundError:
            return None

    def _ours(self, before: int | None) -> None:
        """After the vault itself wrote into the folder: when nothing else had changed it since it was last listed,
        the next look need not list it again."""
        if before == self._folder:
            self._folder = self._stamp()

    @staticmethod
    def _age(note: Note, today: int) -> bool:
        start = note.as_of if note.as_of is not None else note.day
        if start is None or today <= start:
            if start is None:
                note.as_of = today
            return False
        if not note.pinned:
            note.strength = round(note.strength * (1 - FADE) ** (today - start), 4)
        note.as_of = today
        return True

    def _fresh(self, nid: str) -> Note | None:
        """The note as its file says now (a person may have changed or made it), words included; None when there is
        no file."""
        return self.read(nid)

    def _keep(self, note: Note, path: Path) -> None:
        st = path.stat()
        old = self._notes.get(note.id)
        if old is not None:
            for t in old.tags:
                self._tags.get(t, set()).discard(note.id)
        meta = Note(**{f.name: getattr(note, f.name) for f in fields(Note)})
        meta.text, meta.tags, meta.links, meta.extra = None, list(note.tags), dict(note.links), dict(note.extra)
        self._notes[note.id] = meta
        self._files[note.id] = (st.st_mtime_ns, st.st_size)
        for t in meta.tags:
            self._tags.setdefault(t, set()).add(note.id)
        if self.epoch is None and note.day is not None and note.date:
            try:
                self.epoch = dt.date.fromisoformat(note.date) - dt.timedelta(days=note.day)
            except ValueError:
                pass
        self.version += 1

    def _save(self, note: Note) -> None:
        path = self.file(note.id)
        tmp = self.path / f".{note.id}.md.tmp"
        before = self._stamp()
        tmp.write_text(render(note), encoding="utf-8")
        os.replace(tmp, path)
        self._keep(note, path)
        self._ours(before)

    def _load(self) -> None:
        self._folder = self._stamp()
        saved = {}
        index = self.path / INDEX
        if index.exists():
            try:
                got = json.loads(index.read_text(encoding="utf-8"))
                saved = got.get("notes", {})
                if got.get("epoch"):
                    self.epoch = dt.date.fromisoformat(got["epoch"])
            except (ValueError, OSError):
                saved = {}
        for nid in self._names():
            try:
                st = self.file(nid).stat()
            except FileNotFoundError:
                continue
            row = saved.get(nid)
            if row is not None and tuple(row.get("file", ())) == (st.st_mtime_ns, st.st_size):
                meta = {k: v for k, v in row.items() if k != "file"}
                note = Note(**{f.name: meta[f.name] for f in fields(Note) if f.name in meta})
                note.text = None
                self._notes[nid] = note
                self._files[nid] = (st.st_mtime_ns, st.st_size)
                for t in note.tags:
                    self._tags.setdefault(t, set()).add(nid)
            else:
                try:
                    self.read(nid)
                except (OSError, UnicodeDecodeError):
                    continue
        if self.epoch is None:
            for n in self._notes.values():
                if n.day is not None and n.date:
                    try:
                        self.epoch = dt.date.fromisoformat(n.date) - dt.timedelta(days=n.day)
                        break
                    except ValueError:
                        continue
