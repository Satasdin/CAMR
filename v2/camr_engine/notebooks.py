"""Python notebooks and scripts in the project folder, run in a Python of their own.

The kernel's Python is a separate virtual environment at ``~/.camr/kernels/py`` (``ensure_kernel_env``), never the
engine's: what a notebook imports or breaks there cannot touch the app. The engine never imports jupyter_client: it
starts ``kernel_runner.py`` with the kernel's Python and talks to it one JSON line at a time.

A notebook is an ordinary Jupyter file (nbformat 4.5). Its cells are written as plain code and Markdown
(``write``), changed one at a time (``edit_cell``), and run one at a time or all in order (``Notebooks.run``) with a
time limit per cell (CELL_S) and per whole run (RUN_S). What each cell printed, showed (tables as HTML, charts as PNG)
or raised is kept in the file, as Jupyter keeps it. Every path goes through the Workspace, so a notebook is always a
file of the project.

Locked down (``sandbox_profile``): the runner, its kernel and a script run under macOS ``sandbox-exec`` with a
profile that refuses every network connection (the kernel talks to the runner over Unix sockets in its own temp
folder, the one kind of socket allowed, and only there), refuses writes outside the project folder, the kernel's temp
folder and its font cache, and refuses reads of the folders that hold keys and the app's own memory. Their
environment is a short list made here, so the engine's keys (an API key in its environment) never reach them. When
``sandbox-exec`` cannot run (``sandbox_works``), a notebook still runs with only the time limits and the working
folder, and every result says ``sandboxed: false``.
"""

from __future__ import annotations

import base64
import json
import os
import queue
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

PACKAGES = ("ipykernel", "jupyter_client", "nbformat", "numpy", "pandas", "matplotlib")
CELL_S = 60.0  # one cell, at most
RUN_S = 300.0  # a whole run of the notebook, at most
SCRIPT_S = 120.0  # a .py script, at most
START_S = 90.0  # for a kernel to start
IDLE_S = 900.0  # a kernel nobody used for this long is shut down
MAX_KERNELS = 4  # kernels alive at once; the one used longest ago goes first
NOTEBOOK_LIMIT = 8_000_000  # bytes of one .ipynb (outputs included)
MAX_CELLS = 200
CELL_CHARS = 60_000  # of one cell's source
TEXT_SHOWN = 1500  # characters of one cell's output the model reads back
RUNNER = Path(__file__).resolve().parent / "kernel_runner.py"
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_SENSITIVE_READS = (".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker", ".netrc", ".pgpass", ".camr/app",
                    ".camr/code", "Library/Keychains", "Library/Cookies", "Library/Mail", "Library/Messages")


# -- the kernel's Python

def kernel_env() -> Path:
    return Path(os.environ.get("CAMR_KERNEL_ENV") or Path.home() / ".camr" / "kernels" / "py")


def kernel_python() -> Path:
    return kernel_env() / "bin" / "python"


def _versions(py: Path) -> dict[str, str] | None:
    code = ("import json, importlib.metadata as m, sys; out = {'python': sys.version.split()[0]}\n"
            f"for p in {list(PACKAGES)!r}:\n"
            "    try: out[p] = m.version(p)\n"
            "    except m.PackageNotFoundError: out[p] = None\n"
            "print(json.dumps(out))")
    try:
        got = subprocess.run([str(py), "-I", "-c", code], capture_output=True, text=True, timeout=60)
        return json.loads(got.stdout) if got.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def _base_python() -> str:
    """A Python 3 to make the environment from: the one the engine itself was made from (not the engine's venv)."""
    for p in (getattr(sys, "_base_executable", None), Path(sys.base_prefix) / "bin" / "python3"):
        if p and Path(p).exists():
            return str(p)
    return shutil.which("python3") or "python3"


def kernel_ready() -> bool:
    return kernel_python().exists()


def ensure_kernel_env(*, log=print) -> dict:
    """Make the kernel's Python with its packages, once. Idempotent: an environment that already has every package
    is left alone. Returns ``{"path", "made", "versions"}``; raises RuntimeError when it cannot be made."""
    env, py = kernel_env(), kernel_python()
    have = _versions(py) if py.exists() else None
    if have and all(have.get(p) for p in PACKAGES):
        return {"path": str(env), "made": False, "versions": have}
    env.parent.mkdir(parents=True, exist_ok=True)
    uv = shutil.which("uv") or next((str(p) for p in (Path.home() / ".local/bin/uv",) if p.exists()), None)
    steps = ([[uv, "venv", "--python", _base_python(), str(env)],
              [uv, "pip", "install", "--python", str(py), *PACKAGES]] if uv else
             [[_base_python(), "-m", "venv", str(env)],
              [str(py), "-m", "pip", "install", "--disable-pip-version-check", *PACKAGES]])
    if py.exists():  # an environment missing some packages: only install
        steps = steps[1:]
    for cmd in steps:
        log("$ " + " ".join(cmd))
        got = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if got.returncode != 0:
            raise RuntimeError(f"{cmd[0]} failed: {(got.stderr or got.stdout)[-2000:]}")
    have = _versions(py)
    if not have or not all(have.get(p) for p in PACKAGES):
        raise RuntimeError(f"the kernel environment at {env} is missing packages: {have}")
    return {"path": str(env), "made": True, "versions": have}


def cache_dir() -> Path:
    d = kernel_env().parent / "cache"
    (d / "mpl").mkdir(parents=True, exist_ok=True)
    return d


# -- the sandbox

def _q(p: str | Path) -> str:
    return json.dumps(str(p))  # a quoted string in the profile's own syntax (same escapes as JSON for paths)


def sandbox_profile(project: Path, tmp: Path) -> str:
    """No network at all but Unix sockets inside ``tmp``; writes only inside the project, ``tmp`` and the font
    cache; no reads of the folders of keys and the app's memory."""
    home = Path.home().resolve()
    writable = [Path(project).resolve(), Path(tmp).resolve(), cache_dir().resolve()]
    unreadable = [home / s for s in _SENSITIVE_READS]
    return "\n".join([
        "(version 1)",
        "(allow default)",
        "(deny network*)",
        f"(allow network* (local unix-socket (subpath {_q(Path(tmp).resolve())})))",
        f"(allow network* (remote unix-socket (subpath {_q(Path(tmp).resolve())})))",
        "(deny file-write*)",
        "(allow file-write* " + " ".join(f"(subpath {_q(p)})" for p in writable)
        + ' (literal "/dev/null") (literal "/dev/zero") (literal "/dev/dtracehelper") (regex #"^/dev/tty")'
          ' (regex #"^/dev/fd/"))',
        "(deny file-read* " + " ".join(f"(subpath {_q(p)})" for p in unreadable) + ")",
    ])


_sandbox_ok: bool | None = None


def sandbox_works() -> bool:
    """Whether ``sandbox-exec`` runs here (it is on every Mac, but deprecated and could go)."""
    global _sandbox_ok
    if _sandbox_ok is None:
        if os.environ.get("CAMR_NO_SANDBOX") or sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").exists():
            _sandbox_ok = False
        else:
            try:
                got = subprocess.run(["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)(deny network*)",
                                      "/usr/bin/true"], capture_output=True, timeout=10)
                _sandbox_ok = got.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                _sandbox_ok = False
    return _sandbox_ok


def _env(tmp: Path, *, backend: str) -> dict:
    """The few variables a notebook gets: none of the engine's own (its keys among them)."""
    keep = {k: os.environ[k] for k in ("LANG", "LC_ALL", "LC_CTYPE", "USER", "LOGNAME") if k in os.environ}
    return {**keep, "HOME": str(Path.home()), "PATH": f"{kernel_env() / 'bin'}:/usr/bin:/bin",
            "TMPDIR": str(tmp) + "/", "MPLCONFIGDIR": str(cache_dir() / "mpl"), "MPLBACKEND": backend,
            "IPYTHONDIR": str(tmp / "ipython"), "JUPYTER_RUNTIME_DIR": str(tmp / "runtime"),
            "JUPYTER_CONFIG_DIR": str(tmp / "config"), "JUPYTER_PLATFORM_DIRS": "1",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1", "VIRTUAL_ENV": str(kernel_env())}


def _locked(cmd: list[str], project: Path, tmp: Path) -> list[str]:
    if not sandbox_works():
        return cmd
    return ["/usr/bin/sandbox-exec", "-p", sandbox_profile(project, tmp), *cmd]


# -- the file

def _new_id() -> str:
    return secrets.token_hex(4)


def _source(cell: dict) -> str:
    s = cell.get("source", "")
    return "".join(s) if isinstance(s, list) else str(s)


def make_cell(kind: str, source: str) -> dict:
    kind = "markdown" if str(kind).lower() in ("markdown", "md", "text") else "code"
    source = str(source)[:CELL_CHARS]
    if kind == "markdown":
        return {"cell_type": "markdown", "id": _new_id(), "metadata": {}, "source": source}
    return {"cell_type": "code", "id": _new_id(), "metadata": {}, "execution_count": None, "outputs": [],
            "source": source}


def cells_from(spec) -> list[dict]:
    """Cells from what the model wrote: a list of ``{kind, source}`` (or of plain strings, each a code cell; a string
    starting with ``#`` and holding no code is read as Markdown only when the kind says so)."""
    if isinstance(spec, str):
        try:
            spec = json.loads(spec)
        except ValueError:
            raise ValueError("cells is a list of {kind, source}") from None
    if not isinstance(spec, list) or not spec:
        raise ValueError("cells is a list of {kind, source}, at least one")
    if len(spec) > MAX_CELLS:
        raise ValueError(f"a notebook has at most {MAX_CELLS} cells")
    out = []
    for c in spec:
        if isinstance(c, str):
            out.append(make_cell("code", c))
        elif isinstance(c, dict):
            kind = c.get("kind") or c.get("cell_type") or c.get("type") or "code"
            src = c.get("source", c.get("code", c.get("text", "")))
            out.append(make_cell(kind, "".join(src) if isinstance(src, list) else src))
        else:
            raise ValueError("each cell is {kind, source}")
    return out


def new_notebook(cells: list[dict]) -> dict:
    return {"cells": cells, "metadata": {
        "kernelspec": {"display_name": "Python 3 (CAMR)", "language": "python", "name": "python3"},
        "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def _check(rel: str, suffix: str) -> None:
    if not str(rel).lower().endswith(suffix):
        raise ValueError(f"{rel} is not a {suffix} file")


def load(ws, rel: str) -> dict:
    """The notebook at ``rel`` (inside the workspace), its sources as plain strings."""
    _check(rel, ".ipynb")
    p = ws.path(rel)
    if not p.is_file():
        raise ValueError(f"there is no notebook {rel}")
    if p.stat().st_size > NOTEBOOK_LIMIT:
        raise ValueError(f"{rel} is larger than {NOTEBOOK_LIMIT // 1_000_000} MB")
    try:
        nb = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        raise ValueError(f"{rel} is not a notebook (not JSON)") from None
    if not isinstance(nb, dict) or not isinstance(nb.get("cells"), list):
        raise ValueError(f"{rel} is not a notebook (no cells)")
    for c in nb["cells"]:
        c["source"] = _source(c)
        c.setdefault("id", _new_id())
        c.setdefault("metadata", {})
        if c.get("cell_type") == "code":
            c.setdefault("outputs", [])
            c.setdefault("execution_count", None)
            for o in c["outputs"]:
                if o.get("output_type") == "stream" and isinstance(o.get("text"), list):
                    o["text"] = "".join(o["text"])
                for k, v in (o.get("data") or {}).items():
                    if isinstance(v, list):
                        o["data"][k] = "".join(v)
    nb.setdefault("metadata", {})
    nb["nbformat"], nb["nbformat_minor"] = 4, max(5, int(nb.get("nbformat_minor") or 5))
    return nb


def save(ws, rel: str, nb: dict):
    """Write the notebook, atomically, through the workspace's path check. Returns the Workspace's Wrote."""
    from camr_engine.agentic.workspace import Wrote

    _check(rel, ".ipynb")
    p = ws.path(rel, write=True)
    text = json.dumps(nb, indent=1, ensure_ascii=False) + "\n"
    data = text.encode("utf-8")
    if len(data) > NOTEBOOK_LIMIT:
        raise ValueError(f"the notebook would be larger than {NOTEBOOK_LIMIT // 1_000_000} MB: print less")
    before = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.parent.resolve().is_relative_to(ws.root):
        raise ValueError(f"{rel} leads outside the workspace")
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".camr-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return Wrote(ws.rel(p), before, text, len(data))


def write(ws, rel: str, cells) -> tuple[dict, object]:
    """A new notebook (or all of an old one) from cells written as plain text. Returns (notebook, Wrote)."""
    nb = new_notebook(cells_from(cells))
    return nb, save(ws, rel, nb)


def edit_cell(ws, rel: str, index: int, source: str | None = None, *, kind: str | None = None,
              op: str = "edit") -> tuple[dict, object]:
    """Change one cell: ``op`` "edit" (its source, and its kind when given; its outputs are cleared, as they no longer
    match), "insert" (a new cell at ``index``; at the end when index is the number of cells) or "delete"."""
    nb = load(ws, rel)
    cells = nb["cells"]
    if not isinstance(index, int) or isinstance(index, bool):
        raise ValueError("index is a whole number")
    if op == "insert":
        if not 0 <= index <= len(cells) or len(cells) >= MAX_CELLS:
            raise ValueError(f"index must be 0 to {len(cells)}")
        cells.insert(index, make_cell(kind or "code", source or ""))
    elif op == "delete":
        if not 0 <= index < len(cells):
            raise ValueError(f"there is no cell {index}; the notebook has {len(cells)} (0 to {len(cells) - 1})")
        cells.pop(index)
    elif op == "edit":
        if not 0 <= index < len(cells):
            raise ValueError(f"there is no cell {index}; the notebook has {len(cells)} (0 to {len(cells) - 1})")
        if source is None:
            raise ValueError("give the cell's new source")
        old = cells[index]
        new = make_cell(kind or old.get("cell_type", "code"), source)
        new["id"] = old.get("id") or new["id"]
        cells[index] = new
    else:
        raise ValueError("op is edit, insert or delete")
    return nb, save(ws, rel, nb)


# -- how it reads

def _plain(text: str) -> str:
    return _ANSI.sub("", text)


def output_text(o: dict, limit: int = TEXT_SHOWN) -> str:
    """One output as plain text: what was printed, the value, a table's text, or the error's last lines."""
    t = o.get("output_type")
    if t == "stream":
        s = _plain(o.get("text", ""))
    elif t == "error":  # the frame in the notebook's own cell (where to fix it), then the error itself
        tb = [_plain(x) for x in o.get("traceback") or []]
        mine = [x for x in tb if x.lstrip().startswith(("Cell In[", "Input In ["))]
        if mine:
            s = mine[-1].strip("\n")
        else:
            lines = "\n".join(tb[:-1]).splitlines()
            s = "\n".join(lines[-8:])
        s = (s + "\n" if s else "") + f"{o.get('ename')}: {o.get('evalue')}"
    else:
        data = o.get("data") or {}
        if "image/png" in data or "image/jpeg" in data or "image/svg+xml" in data:
            s = "[a chart/image was shown]"
            plain = str(data.get("text/plain", ""))
            if plain and not plain.startswith("<Figure"):
                s += " " + plain
        else:
            s = str(data.get("text/plain") or data.get("text/markdown") or _html_text(str(data.get("text/html", ""))))
    s = s.strip("\n")
    return s if len(s) <= limit else s[:limit // 3] + f"\n… {len(s) - limit:,} characters left out …\n" + s[-(limit * 2 // 3):]


def _html_text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def cell_errors(cell: dict) -> list[dict]:
    return [o for o in cell.get("outputs") or [] if o.get("output_type") == "error"]


def text_view(nb: dict, which: list[int] | None = None, *, sources: bool = False, limit: int = TEXT_SHOWN) -> str:
    """The notebook as the model reads it back: each cell's number, kind and how it ran, then its outputs."""
    lines = []
    for i, c in enumerate(nb["cells"]):
        if which is not None and i not in which:
            continue
        if c.get("cell_type") != "code":
            head = _source(c).strip().splitlines()[:1]
            lines.append(f"[{i}] markdown: {head[0][:100] if head else ''}")
            continue
        errs = cell_errors(c)
        state = ("error" if errs else "ok") if c.get("execution_count") is not None or c.get("outputs") else "not run"
        lines.append(f"[{i}] code, {state}" + (":" if c.get("outputs") or sources else ""))
        if sources:
            lines += ["    " + x for x in _source(c).splitlines()]
            if c.get("outputs"):
                lines.append("  output:")
        for o in c.get("outputs") or []:
            lines += ["    " + x for x in output_text(o, limit).splitlines()]
    return "\n".join(lines) or "(the notebook has no cells)"


def view(nb: dict) -> dict:
    """The notebook for the app: each cell's kind, source and outputs, images as base64 PNG (as the file holds them)
    and tables as rows when an HTML table is simple enough to read."""
    cells = []
    for i, c in enumerate(nb["cells"]):
        outs = []
        for o in c.get("outputs") or []:
            t = o.get("output_type")
            if t == "stream":
                outs.append({"kind": "text", "name": o.get("name", "stdout"), "text": _plain(o.get("text", ""))})
            elif t == "error":
                outs.append({"kind": "error", "ename": o.get("ename", ""), "evalue": o.get("evalue", ""),
                             "text": output_text(o, 6000)})
            else:
                data = o.get("data") or {}
                if "image/png" in data or "image/jpeg" in data:
                    key = "image/png" if "image/png" in data else "image/jpeg"
                    outs.append({"kind": "image", "mime": key, "base64": str(data[key]).replace("\n", "")})
                elif "text/html" in data and (rows := html_table(str(data["text/html"]))):
                    outs.append({"kind": "table", "rows": rows, "text": str(data.get("text/plain", ""))})
                else:
                    outs.append({"kind": "text", "name": "result",
                                 "text": str(data.get("text/plain") or data.get("text/markdown")
                                             or _html_text(str(data.get("text/html", ""))))})
        cells.append({"index": i, "id": c.get("id"), "kind": "markdown" if c.get("cell_type") == "markdown" else "code",
                      "source": _source(c), "count": c.get("execution_count"), "outputs": outs})
    return {"cells": cells}


_ROW = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(r"<t([hd])\b[^>]*>(.*?)</t[hd]>", re.S | re.I)


def html_table(html: str, max_rows: int = 60) -> list[list[str]] | None:
    """A simple HTML table (as pandas shows a DataFrame) as rows of text; None when it is not one."""
    if "<table" not in html.lower():
        return None
    rows = []
    for r in _ROW.findall(html)[:max_rows + 1]:
        cells = [_html_text(x[1]) for x in _CELL.findall(r)]
        if cells:
            rows.append(cells)
    return rows or None


# -- running

class Failed(RuntimeError):
    """The kernel could not start or stopped answering."""


class Kernel:
    """One kernel for one notebook: the runner process (kernel's Python, sandboxed) and its kernel."""

    def __init__(self, project: Path):
        if not kernel_ready():
            raise Failed(f"the notebook Python is not set up yet ({kernel_env()}); run ensure_kernel_env")
        self.project = Path(project).resolve()
        self.tmp = Path(tempfile.mkdtemp(prefix="camrk-", dir="/private/tmp" if sys.platform == "darwin" else None))
        for d in ("ipython", "runtime", "config"):
            (self.tmp / d).mkdir()
        self.sandboxed = sandbox_works()
        cmd = _locked([str(kernel_python()), "-I", str(RUNNER), str(self.project), str(self.tmp)], self.project,
                      self.tmp)
        self.proc = subprocess.Popen(cmd, cwd=self.project, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=open(self.tmp / "runner.log", "ab"),  # noqa: SIM115
                                     env=_env(self.tmp, backend="module://matplotlib_inline.backend_inline"),
                                     text=True, bufsize=1, start_new_session=True)
        self.lines: queue.Queue = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self.lock = threading.Lock()
        self.used = time.monotonic()
        got = self._answer(START_S)
        if not got.get("ready"):
            self.close()
            raise Failed("the kernel did not start: " + str(got.get("error") or self._log()))

    def _read(self) -> None:
        for line in self.proc.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def _log(self) -> str:
        try:
            return (self.tmp / "runner.log").read_text(errors="replace")[-1500:]
        except OSError:
            return ""

    def _answer(self, wait_s: float) -> dict:
        try:
            line = self.lines.get(timeout=wait_s)
        except queue.Empty:
            self.close()
            raise Failed(f"the kernel did not answer in {wait_s:.0f} s, so it was shut down") from None
        if line is None:
            raise Failed("the kernel stopped: " + self._log())
        try:
            return json.loads(line)
        except ValueError:
            return {"status": "error", "error": line[:500]}

    def _ask(self, req: dict, wait_s: float) -> dict:
        if not self.alive:
            raise Failed("the kernel has stopped")
        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()
        return self._answer(wait_s)

    @property
    def alive(self) -> bool:
        return self.proc.poll() is None

    def run(self, code: str, timeout: float = CELL_S) -> dict:
        with self.lock:
            self.used = time.monotonic()
            try:
                grace = min(5.0, max(1.0, timeout / 4))  # after the interrupt, before the kernel is restarted
                return self._ask({"op": "run", "code": code, "timeout": timeout, "grace": grace}, timeout + 90)
            finally:
                self.used = time.monotonic()

    def restart(self) -> None:
        with self.lock:
            self._ask({"op": "restart"}, START_S)

    def interrupt(self) -> None:
        if self.alive:
            try:
                os.kill(self.proc.pid, signal.SIGUSR1)
            except OSError:
                pass

    def close(self) -> None:
        if self.alive:
            try:
                self.proc.stdin.write('{"op": "quit"}\n')
                self.proc.stdin.flush()
                self.proc.wait(5)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass
        if self.alive:
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except OSError:
                pass
        shutil.rmtree(self.tmp, ignore_errors=True)


class Notebooks:
    """Every notebook's kernel and its run in progress, by the notebook's full path: one per app, shared by the agent's
    tools and the app's routes, so Stop in the app stops the agent's run too."""

    def __init__(self):
        self.lock = threading.Lock()
        self.kernels: dict[str, Kernel] = {}
        self.runs: dict[str, dict] = {}  # path -> {"state", "cell", "done", "error", "started", "ended", ...}
        self.cancels: dict[str, threading.Event] = {}
        self.file_locks: dict[str, threading.Lock] = {}

    def _file_lock(self, key: str) -> threading.Lock:
        with self.lock:
            return self.file_locks.setdefault(key, threading.Lock())

    def kernel(self, key: str, project: Path, *, fresh: bool = False) -> Kernel:
        with self.lock:
            now = time.monotonic()
            for k, kern in list(self.kernels.items()):  # idle ones go
                if k != key and (not kern.alive or now - kern.used > IDLE_S) and not kern.lock.locked():
                    self.kernels.pop(k).close()
            k = self.kernels.get(key)
            if k is not None and (fresh or not k.alive):
                self.kernels.pop(key).close()
                k = None
            if k is None:
                while len(self.kernels) >= MAX_KERNELS:
                    old = min((x for x in self.kernels if not self.kernels[x].lock.locked()),
                              key=lambda x: self.kernels[x].used, default=None)
                    if old is None:
                        break
                    self.kernels.pop(old).close()
        if k is None:
            k = Kernel(project)  # outside the lock: it takes seconds
            with self.lock:
                self.kernels[key] = k
        return k

    def state(self, ws, rel: str) -> dict:
        key = str(ws.path(rel))
        with self.lock:
            r = self.runs.get(key)
            return dict(r) if r else {"state": "idle"}

    def busy(self, ws, rel: str) -> bool:
        return self.state(ws, rel).get("state") == "running"

    def stop(self, ws, rel: str) -> dict:
        key = str(ws.path(rel))
        with self.lock:
            ev, k = self.cancels.get(key), self.kernels.get(key)
        if ev is not None:
            ev.set()
        if k is not None:
            k.interrupt()
        return self.state(ws, rel)

    def shutdown(self, ws=None, rel: str | None = None) -> None:
        with self.lock:
            keys = [str(ws.path(rel))] if ws is not None and rel else list(self.kernels)
            gone = [self.kernels.pop(k) for k in keys if k in self.kernels]
        for k in gone:
            k.close()

    def run(self, ws, rel: str, which: int | None = None, *, cell_s: float = CELL_S, run_s: float = RUN_S,
            cancel: threading.Event | None = None, on_cell: Callable[[int, dict], None] | None = None,
            _claimed: bool = False) -> dict:
        """Run one cell (``which``) in the notebook's kernel as it is, or every code cell in order in a fresh kernel
        (``which`` None), stopping at the first cell that fails. Each cell's outputs go into the file as soon as it
        ends (merged into the file as it is then, by the cell's id, so an edit made meanwhile is kept). Returns
        ``{"state", "ran", "failed", "seconds", "sandboxed", "notebook"}``."""
        key = str(ws.path(rel))
        nb = load(ws, rel)
        code = [i for i, c in enumerate(nb["cells"]) if c.get("cell_type") == "code"]
        if which is not None:
            if not 0 <= which < len(nb["cells"]):
                raise ValueError(f"there is no cell {which}; the notebook has {len(nb['cells'])}")
            if which not in code:
                raise ValueError(f"cell {which} is Markdown, which does not run")
            todo = [which]
        else:
            todo = code
        ev = threading.Event()
        with self.lock:
            if self.runs.get(key, {}).get("state") == "running" and not _claimed:
                raise RuntimeError(f"{rel} is running already; stop it first")
            self.runs[key] = {"state": "running", "cell": None, "done": [], "todo": list(todo), "error": None,
                              "started": time.time(), "ended": None, "path": rel}
            self.cancels[key] = ev
        t0 = time.monotonic()
        ran, failed, state, err = [], None, "done", None
        try:
            kern = self.kernel(key, ws.root, fresh=which is None)
            if which is None:  # a fresh kernel: clear every cell's outputs first, so none is stale
                with self._file_lock(key):
                    cur = load(ws, rel)
                    for c in cur["cells"]:
                        if c.get("cell_type") == "code":
                            c["outputs"], c["execution_count"] = [], None
                    save(ws, rel, cur)
            for i in todo:
                if ev.is_set() or (cancel is not None and cancel.is_set()):
                    state = "stopped"
                    break
                left = run_s - (time.monotonic() - t0)
                if left <= 1:
                    state, err = "timeout", f"the whole run passed its limit of {run_s:g} s"
                    break
                with self.lock:
                    self.runs[key]["cell"] = i
                cid = nb["cells"][i].get("id")
                src = _source(nb["cells"][i])
                with self._file_lock(key):  # the cell as it is now in the file (the person may have just changed it)
                    cur = load(ws, rel)
                    c = next((x for x in cur["cells"] if x.get("id") == cid), None)
                    src = _source(c) if c is not None else src
                watch = None
                if cancel is not None:  # an agent run stopped: the cell stops too
                    watch = threading.Thread(target=_relay, args=(cancel, ev, kern), daemon=True)
                    watch.start()
                got = kern.run(src, min(cell_s, left))
                ev_stop = ev.is_set()
                self._put(ws, rel, key, cid, got)
                ran.append(i)
                with self.lock:
                    self.runs[key]["done"].append(i)
                if on_cell is not None:
                    on_cell(i, got)
                if got.get("status") != "ok":
                    failed = i
                    state = {"timeout": "timeout", "stopped": "stopped"}.get(got.get("status"), "error")
                    if got.get("status") == "error" and got.get("error") and not got.get("outputs"):
                        err = got["error"]
                    break
                if ev_stop:
                    state = "stopped"
                    break
        except Failed as e:
            state, err = "failed", str(e)
            self.shutdown(ws, rel)
        finally:
            with self.lock:
                r = self.runs[key]
                r.update(state=state, cell=None, error=err, ended=time.time(), failed=failed)
                self.cancels.pop(key, None)
        return {"state": state, "ran": ran, "failed": failed, "error": err,
                "seconds": round(time.monotonic() - t0, 2), "sandboxed": sandbox_works(), "notebook": load(ws, rel)}

    def _put(self, ws, rel: str, key: str, cid: str, got: dict) -> None:
        with self._file_lock(key):
            cur = load(ws, rel)
            c = next((x for x in cur["cells"] if x.get("id") == cid), None)
            if c is None:  # the cell was deleted while it ran
                return
            outs = got.get("outputs") or []
            if got.get("error") and not outs:
                outs = [{"output_type": "error", "ename": "KernelError", "evalue": str(got["error"])[:500],
                         "traceback": []}]
            c["outputs"], c["execution_count"] = outs, got.get("count")
            save(ws, rel, cur)

    def start(self, ws, rel: str, which: int | None = None, **kw) -> dict:
        """``run`` in the background, for the app (it polls ``state``)."""
        key = str(ws.path(rel))
        load(ws, rel)
        with self.lock:
            if self.runs.get(key, {}).get("state") == "running":
                raise RuntimeError(f"{rel} is running already; stop it first")
            self.runs[key] = {"state": "running", "cell": None, "done": [], "todo": [], "error": None,
                              "started": time.time(), "ended": None, "path": rel}

        def go():
            try:
                self.run(ws, rel, which, _claimed=True, **kw)
            except Exception as e:  # noqa: BLE001 (shown in the app)
                with self.lock:
                    self.runs[key] = {"state": "failed", "cell": None, "done": [], "error": f"{e}"[:500],
                                      "started": time.time(), "ended": time.time(), "path": rel}

        threading.Thread(target=go, daemon=True, name=f"notebook {rel}").start()
        return self.state(ws, rel)


def _relay(cancel: threading.Event, ev: threading.Event, kern: Kernel) -> None:
    while kern.lock.locked() and not ev.is_set():
        if cancel.wait(0.2):
            ev.set()
            kern.interrupt()
            return


NOTEBOOKS = Notebooks()


# -- scripts

def run_script(ws, rel: str, *, timeout_s: float = SCRIPT_S, cancel: threading.Event | None = None) -> dict:
    """Run a .py file of the project with the kernel's Python, in the project folder, locked down as a notebook is.
    Returns ``{"code", "output", "seconds", "timed_out", "made", "sandboxed"}``; ``made`` are the files it wrote."""
    _check(rel, ".py")
    p = ws.path(rel)
    if not p.is_file():
        raise ValueError(f"there is no script {rel}")
    if not kernel_ready():
        raise Failed(f"the notebook Python is not set up yet ({kernel_env()})")
    before = {f["path"]: f.get("size") for f in ws.tree() if not f["dir"]}
    stamp = time.time()
    tmp = Path(tempfile.mkdtemp(prefix="camrs-", dir="/private/tmp" if sys.platform == "darwin" else None))
    out_path = tmp / "out.txt"
    t0 = time.monotonic()
    timed_out = False
    try:
        with open(out_path, "wb") as out:
            proc = subprocess.Popen(_locked([str(kernel_python()), str(p)], ws.root, tmp), cwd=ws.root,
                                    stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                    env=_env(tmp, backend="Agg"), start_new_session=True)
            while proc.poll() is None:
                if time.monotonic() - t0 > timeout_s or (cancel is not None and cancel.is_set()):
                    timed_out = time.monotonic() - t0 > timeout_s
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except OSError:
                        pass
                    proc.wait(5)
                    break
                time.sleep(0.05)
        output = out_path.read_bytes()[-200_000:].decode("utf-8", "replace")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if timed_out:
        output += f"\n[stopped: the script ran longer than {timeout_s:g} s]\n"
    made = []
    for f in ws.tree():
        if f["dir"] or f["path"] == rel:
            continue
        try:
            changed = (ws.root / f["path"]).stat().st_mtime >= stamp - 0.5
        except OSError:
            continue
        if f["path"] not in before or changed:
            made.append(f["path"])
    return {"code": proc.returncode, "output": output, "seconds": round(time.monotonic() - t0, 2),
            "timed_out": timed_out, "made": made[:40], "sandboxed": sandbox_works()}


def image_b64(ws, rel: str, limit: int = 4_000_000) -> str | None:
    """A picture a script made, as base64, for the app."""
    p = ws.path(rel)
    if p.suffix.lower() not in (".png", ".jpg", ".jpeg") or not p.is_file() or p.stat().st_size > limit:
        return None
    return base64.b64encode(p.read_bytes()).decode()


if __name__ == "__main__":  # python -m camr_engine.notebooks: make the kernel's Python
    print(json.dumps(ensure_kernel_env(), indent=2))
