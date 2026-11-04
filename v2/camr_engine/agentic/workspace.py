"""The workspace: the one folder the agent may read and write, chosen by the person on the Code screen.

Every path the model names is checked before anything is touched:
- it must stay inside the folder once ``..`` and symlinks are followed, so ``../x``, ``/etc/passwd`` and a link
  pointing out are all refused;
- nothing is written inside ``.git`` (nor a file named ``.git``) or to files that run commands by themselves
  (``.envrc``, ``.vscode/tasks.json``), and a write never follows a symlink at its last step. Names are compared
  ignoring case and invisible characters, since the Mac's disk does: ``.GIT/config`` is ``.git/config`` there;
- files that look like secrets (``.env``, keys, ``.netrc``) are neither read nor written;
- reads and writes have size limits, and binary files are not read.

The folder itself cannot be the whole disk, the home folder, or a folder of keys and settings (``~/.ssh``,
``~/.config``, ``~/Library`` and the like), nor camr's own memory folder, nor hold or sit inside the folders the
app keeps for itself (``keep_out``: the Code screen's settings and the memory's reaches).

A search by regular expression runs with the ``regex`` package, which takes a time limit and lets the app's other
threads run meanwhile, so a pattern that backtracks for ever stops after a few seconds instead of freezing the app.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import re
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:  # a time limit per match, and the app's other threads keep running (Python's re has neither)
    import regex as _regex
except ImportError:  # pragma: no cover (installed with mlx-lm)
    _regex = None

READ_LIMIT = 256_000  # characters of one file the model reads at once
WRITE_LIMIT = 1_000_000  # bytes of one file the model writes
EDITOR_LIMIT = 2_000_000  # bytes of one file the editor opens
LIST_LIMIT = 400
TREE_LIMIT = 3000
SEARCH_LIMIT = 100
SEARCH_FILE_LIMIT = 1_000_000  # bigger files are skipped by search
LINE_LIMIT = 2000  # longer lines are skipped by a regular-expression search
SEARCH_S = 3.0  # a regular-expression search stops after this long

SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache", ".ruff_cache",
        ".tox", ".DS_Store", ".idea", ".next", "dist", "build", ".cache"}
SECRET = re.compile(r"^(\.env(?!\.(example|sample|template|dist)$)(\..*)?|\.netrc|\.npmrc|\.pypirc|\.pgpass|"
                    r"id_(rsa|dsa|ecdsa|ed25519)(\.pub)?|.*\.(pem|key|p12|pfx|keychain|kdbx))$", re.I)
_SENSITIVE = (".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker", ".config", ".camr", ".netrc", "Library",
              ".Trash")


class Outside(ValueError):
    """A path the workspace refuses, with the reason in plain words."""


def folded(name: str) -> str:
    """A file name as a case-blind disk sees it: case folded, and invisible (format) characters dropped, so
    ``.GIT``, ``.Git`` and ``.g\\u200cit`` all read as ``.git``."""
    name = unicodedata.normalize("NFKC", name)
    return "".join(c for c in name if unicodedata.category(c) != "Cf").casefold()


def check_root(path: str | os.PathLike, keep_out: Iterable[str | os.PathLike] = ()) -> Path:
    """The folder a person chose, resolved, or Outside when it cannot be a workspace. ``keep_out`` are folders the
    app keeps for itself: a workspace may neither hold one nor sit inside one."""
    p = Path(path).expanduser()
    if not str(path).strip() or not p.is_absolute():
        raise Outside("choose the workspace by its full path, such as ~/Desktop/project")
    p = p.resolve()
    if not p.is_dir():
        raise Outside(f"there is no folder at {p}")
    home = Path.home().resolve()
    if p == Path(p.anchor) or p == home or p in home.parents:
        raise Outside("choose a project folder, not the whole disk or the home folder")
    for name in _SENSITIVE:
        d = (home / name).resolve()
        if p == d or p.is_relative_to(d):
            raise Outside(f"{d} holds keys or settings, so it cannot be a workspace")
    for d in (Path("/System"), Path("/usr"), Path("/bin"), Path("/sbin"), Path("/etc"), Path("/private/etc"),
              Path("/Library")):
        if p == d or p.is_relative_to(d):
            raise Outside(f"{d} belongs to the system, so it cannot be a workspace")
    for k in keep_out:
        d = Path(k).expanduser().resolve()
        if p == d or p.is_relative_to(d) or d.is_relative_to(p):
            raise Outside(f"{d} holds the app's own settings or memory, so the workspace can neither be it, be "
                          "inside it, nor hold it")
    return p


class _Slow(Exception):
    """A regular-expression search ran out of time."""


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()[:16]


@dataclass
class Wrote:
    path: str  # relative to the workspace
    before: str | None  # the file's text before (None: it is new)
    after: str
    bytes: int


class Workspace:
    def __init__(self, root: str | os.PathLike, keep_out: Iterable[str | os.PathLike] = ()):
        self.root = check_root(root, keep_out)

    @property
    def name(self) -> str:
        return self.root.name

    # -- paths

    def path(self, rel: str, *, write: bool = False) -> Path:
        """The file ``rel`` names, inside the workspace, or Outside. An absolute path is taken only when it is
        inside the workspace already."""
        if not isinstance(rel, str):
            raise Outside("a path is text")
        rel = rel.strip()
        if not rel or len(rel) > 1024 or "\0" in rel:
            raise Outside("give a path inside the workspace")
        p = Path(rel).expanduser() if rel.startswith("~") else Path(rel)
        joined = Path(os.path.normpath(p if p.is_absolute() else self.root / p))
        if not (joined == self.root or joined.is_relative_to(self.root)):
            raise Outside(f"{rel} is outside the workspace")
        real = joined.resolve()  # follows every symlink on the way, even to a file not there yet
        if not (real == self.root or real.is_relative_to(self.root)):
            raise Outside(f"{rel} leads outside the workspace")
        parts = real.relative_to(self.root).parts
        if SECRET.match(real.name):
            raise Outside(f"{real.name} looks like a file of secrets, so the agent leaves it alone")
        if write:
            if not parts:
                raise Outside("give a file to write, not the workspace itself")
            low = tuple(folded(x) for x in parts)
            if ".git" in low:  # the folder, or a file of that name pointing git elsewhere
                raise Outside("the agent does not write inside .git, nor a file named .git")
            if low[-1] == ".envrc" or low[-2:] == (".vscode", "tasks.json"):
                raise Outside(f"{rel} would run commands by itself when the folder is opened; change it yourself")
            if joined.is_symlink():
                raise Outside(f"{rel} is a symlink; write to the file it names instead")
        return real

    def rel(self, p: Path) -> str:
        r = p.relative_to(self.root).as_posix()
        return r or "."

    # -- reading

    def text(self, rel: str, limit: int = EDITOR_LIMIT) -> tuple[str, str]:
        """(relative path, the whole file's text), for the editor."""
        p = self.path(rel)
        if not p.is_file():
            raise Outside(f"there is no file {rel}")
        if p.stat().st_size > limit:
            raise Outside(f"{rel} is larger than {limit // 1_000_000} MB")
        data = p.read_bytes()
        if b"\0" in data[:8192]:
            raise Outside(f"{rel} is not a text file")
        return self.rel(p), data.decode("utf-8", "replace")

    def read(self, rel: str, start: int = 1, lines: int | None = None, limit: int = READ_LIMIT) -> dict:
        """A file for the model, numbered from line ``start``: ``N│ text`` per line, at most ``limit`` characters (a
        single line longer than that is cut)."""
        path, text = self.text(rel)
        rows = text.splitlines()
        start = max(1, int(start or 1))
        end = len(rows) if not lines else min(len(rows), start - 1 + max(1, int(lines)))
        out, size = [], 0
        for n in range(start, end + 1):
            row = f"{n:>5}│ {rows[n - 1]}"
            if size + len(row) > limit:
                if not out:  # one line longer than the whole limit: its start, and how much is left out
                    out.append(row[:limit] + f"… ({len(row) - limit:,} more characters on this line)")
                    end = n
                else:
                    end = n - 1
                break
            out.append(row)
            size += len(row) + 1
        return {"path": path, "text": "\n".join(out), "from": start, "to": end, "lines": len(rows),
                "truncated": end < len(rows)}

    def listing(self, rel: str = ".", depth: int = 2, limit: int = LIST_LIMIT) -> dict:
        """The folder's files and folders, ``depth`` levels down, skipping caches and ``.git``."""
        top = self.path(rel or ".")
        if not top.is_dir():
            raise Outside(f"there is no folder {rel}")
        depth = max(1, min(int(depth or 2), 6))
        rows: list[str] = []
        more = False

        def walk(d: Path, level: int) -> None:
            nonlocal more
            try:
                kids = sorted(d.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            except OSError:
                return
            for k in kids:
                if k.name in SKIP:
                    continue
                if len(rows) >= limit:
                    more = True
                    return
                is_dir = k.is_dir() and not k.is_symlink()
                rows.append(f"{'  ' * (level - 1)}{k.name}{'/' if is_dir else ''}")
                if is_dir and level < depth:
                    walk(k, level + 1)

        walk(top, 1)
        return {"path": self.rel(top), "text": "\n".join(rows) or "(empty)", "entries": len(rows), "more": more}

    def tree(self, limit: int = TREE_LIMIT) -> list[dict]:
        """Every file and folder for the editor's file list: ``{path, dir, size}``, folders first at each level."""
        out: list[dict] = []

        def walk(d: Path) -> None:
            try:
                kids = sorted(d.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            except OSError:
                return
            for k in kids:
                if len(out) >= limit or k.name in SKIP or k.is_symlink():
                    continue
                if k.is_dir():
                    out.append({"path": self.rel(k), "dir": True})
                    walk(k)
                elif k.is_file():
                    out.append({"path": self.rel(k), "dir": False, "size": k.stat().st_size,
                                "secret": bool(SECRET.match(k.name))})

        walk(self.root)
        return out

    def search(self, pattern: str, rel: str = ".", glob: str | None = None, regex: bool = False,
               limit: int = SEARCH_LIMIT) -> dict:
        """Lines holding ``pattern`` (plain text, ignoring case; a regular expression when ``regex``, the whole
        search stopped after SEARCH_S seconds)."""
        if not isinstance(pattern, str) or not pattern or len(pattern) > 200:
            raise Outside("search for some text, at most 200 characters")
        if regex:
            if _regex is None:
                raise Outside("a search by regular expression is not available here; search for plain text")
            try:
                rx = _regex.compile(pattern)
            except (_regex.error, ValueError, TypeError) as e:
                raise Outside(f"not a regular expression: {e}") from None
            deadline = time.monotonic() + SEARCH_S

            def hit(line: str) -> bool:
                if len(line) > LINE_LIMIT:
                    return False
                left = deadline - time.monotonic()
                if left <= 0:
                    raise _Slow
                try:
                    return rx.search(line, timeout=left, concurrent=True) is not None
                except TimeoutError:
                    raise _Slow from None
        else:
            low = pattern.lower()

            def hit(line: str) -> bool:
                return low in line.lower()
        top = self.path(rel or ".")
        files = [top] if top.is_file() else []
        if top.is_dir():
            for d, dirs, names in os.walk(top):
                dirs[:] = sorted(x for x in dirs if x not in SKIP and not Path(d, x).is_symlink())
                for n in sorted(names):
                    if n in SKIP or SECRET.match(n) or (glob and not fnmatch.fnmatch(n, glob)):
                        continue
                    files.append(Path(d, n))
        found, more, slow = [], False, False
        for f in files:
            try:
                if f.is_symlink() or f.stat().st_size > SEARCH_FILE_LIMIT:
                    continue
                data = f.read_bytes()
            except OSError:
                continue
            if b"\0" in data[:8192]:
                continue
            try:
                for n, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
                    if hit(line):
                        if len(found) >= limit:
                            more = True
                            break
                        found.append({"path": self.rel(f), "line": n, "text": line.strip()[:240]})
            except _Slow:
                more = slow = True
            if more:
                break
        text = "\n".join(f"{x['path']}:{x['line']}: {x['text']}" for x in found) or "no matches"
        if slow:
            text += (f"\n… the search stopped after {SEARCH_S:g} s: the pattern is too slow to match; try a plainer "
                     "one, or plain text")
        return {"matches": found, "text": text, "more": more, "slow": slow}

    # -- writing

    def write(self, rel: str, text: str) -> Wrote:
        """Write a whole file (made with its folders when new). Atomic: a new file is written beside it and moved
        into place, which never follows a symlink."""
        if not isinstance(text, str):
            raise Outside("the content of a file is text")
        data = text.encode("utf-8")
        if len(data) > WRITE_LIMIT:
            raise Outside(f"a file the agent writes is at most {WRITE_LIMIT // 1_000_000} MB")
        p = self.path(rel, write=True)
        if p.is_dir():
            raise Outside(f"{rel} is a folder")
        before = None
        if p.exists():
            try:
                before = self.text(self.rel(p))[1]
            except Outside:
                raise Outside(f"{rel} is not a text file the agent may replace") from None
        parent = p.parent
        parent.mkdir(parents=True, exist_ok=True)
        if not parent.resolve().is_relative_to(self.root):
            raise Outside(f"{rel} leads outside the workspace")
        mode = p.stat().st_mode & 0o777 if p.exists() else 0o644
        fd, tmp = tempfile.mkstemp(dir=parent, prefix=".camr-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.chmod(tmp, mode)
            os.replace(tmp, p)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return Wrote(self.rel(p), before, text, len(data))

    def edit(self, rel: str, old: str, new: str) -> Wrote:
        """Replace the one place ``old`` appears with ``new``. ``old`` must appear exactly once."""
        if not isinstance(old, str) or not isinstance(new, str) or not old:
            raise Outside("edit needs the exact text to replace and its replacement")
        path, text = self.text(rel)
        n = text.count(old)
        if n == 0:
            raise Outside(f"that text is not in {path}; read the file and copy it exactly")
        if n > 1:
            raise Outside(f"that text is in {path} {n} times; include more lines so it is found once")
        return self.write(path, text.replace(old, new, 1))
