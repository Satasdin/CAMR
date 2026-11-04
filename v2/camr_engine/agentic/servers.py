"""MCP servers over stdio, through the official ``mcp`` package. The person adds a server on the Code screen (a name
and the command that starts it) and presses connect; the agent can neither add nor start one. Its tools then show up
for the model as ``mcp__<server>__<tool>``, and every call of one waits at the gate like a shell command.

The list is kept in ``mcp.json`` (readable by this user only, since a server's environment may hold its key); the
page is shown the names of a server's environment settings, never their values. A connected server runs as a child
process in the workspace folder, with the ``mcp`` package's safe environment plus its own settings, and its errors go
to a log file of its own. Each connection lives on one background event loop, so calls come from any thread.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# no "__" and no "_" at the end, so ``mcp__<server>__<tool>`` splits back into the one server it names
NAME = re.compile(r"^(?!.*__)(?!.*_$)[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
CONNECT_S = 30.0  # starting a server and listing its tools
CALL_S = 120.0
MAX_SERVERS = 16
RESULT_LIMIT = 20_000  # characters of one result the model reads


@dataclass
class Spec:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    def show(self) -> dict:
        return {"name": self.name, "command": self.command, "args": self.args, "env": sorted(self.env)}


def spec(name: str, command_line: str, env: dict | None = None) -> Spec:
    """A server from the command line a person typed (split like a shell would, but never run by one)."""
    if not isinstance(name, str) or not NAME.match(name):
        raise ValueError("a server's name is letters, digits, _ and -, at most 32, with no __ and no _ at its end")
    try:
        words = shlex.split(command_line or "")
    except ValueError as e:
        raise ValueError(f"cannot read that command: {e}") from None
    if not words:
        raise ValueError("give the command that starts the server")
    env = {str(k): str(v) for k, v in (env or {}).items()}
    for k in env:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$", k):
            raise ValueError(f"{k!r} is not an environment variable name")
    return Spec(name, words[0], words[1:], env)


def tool_name(server: str, tool: str) -> str:
    return f"mcp__{server}__{tool}"


def split_name(name: str) -> tuple[str, str] | None:
    """(server, tool) for an ``mcp__server__tool`` name, else None."""
    m = re.match(r"^mcp__([A-Za-z0-9][A-Za-z0-9_-]{0,31}?)__(.+)$", name or "")
    return (m.group(1), m.group(2)) if m else None


class Link:
    """One connected server: its process, its session, and the event loop they live on."""

    def __init__(self, s: Spec, cwd: Path | None, log: Path):
        self.spec, self.cwd, self.log_path = s, cwd, log
        self.state = "connecting"
        self.error: str | None = None
        self.tools: list[dict] = []
        self.calls = 0
        self.failures = 0
        self.at = time.time()
        self._session = None
        self._stop = None
        self._portal_cm = None
        self.portal = None
        self._task = None

    def connect(self) -> None:
        from anyio.from_thread import start_blocking_portal

        self._portal_cm = start_blocking_portal()
        self.portal = self._portal_cm.__enter__()
        try:
            self._task, self.tools = self.portal.start_task(self._serve)
            self.state = "connected"
        except BaseException as e:  # noqa: BLE001 (shown on the server's tile)
            self.state, self.error = "failed", _why(e, self.log_path)
            self._shut()
            if not isinstance(e, Exception):
                raise

    async def _serve(self, *, task_status) -> None:
        """Start the server, list its tools, then hold the connection open until ``close``."""
        import anyio
        from mcp import ClientSession, StdioServerParameters, stdio_client

        params = StdioServerParameters(command=self.spec.command, args=list(self.spec.args), env=dict(self.spec.env),
                                       cwd=str(self.cwd) if self.cwd else None)
        self._stop = anyio.Event()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a") as errlog:
            async with stdio_client(params, errlog=errlog) as (read, write):
                async with ClientSession(read, write) as session:
                    with anyio.fail_after(CONNECT_S):
                        await session.initialize()
                        listed = await session.list_tools()
                    self._session = session
                    task_status.started([{"name": t.name, "description": (t.description or "")[:1000],
                                          "schema": t.input_schema or {"type": "object", "properties": {}}}
                                         for t in listed.tools])
                    try:
                        await self._stop.wait()
                    finally:
                        self._session = None

    def call(self, tool: str, arguments: dict, timeout_s: float = CALL_S) -> dict:
        """One tool call, already allowed by the person: ``{ok, text, ms}``."""
        if self.state != "connected" or self._session is None:
            raise RuntimeError(f"the {self.spec.name} server is not connected")
        t = time.perf_counter()
        self.calls += 1
        try:
            res = self.portal.call(self._call, tool, arguments, timeout_s)
        except Exception as e:  # noqa: BLE001 (the model reads the failure)
            self.failures += 1
            return {"ok": False, "text": f"the call failed: {type(e).__name__}: {e}"[:2000],
                    "ms": round((time.perf_counter() - t) * 1000, 1)}
        parts = []
        for c in res.content or []:
            if getattr(c, "type", None) == "text":
                parts.append(c.text)
            else:
                parts.append(f"[{getattr(c, 'type', 'content')} left out]")
        if not parts and res.structured_content is not None:
            parts.append(json.dumps(res.structured_content)[:RESULT_LIMIT])
        text = "\n".join(parts)
        if len(text) > RESULT_LIMIT:
            text = text[:RESULT_LIMIT] + "\n… the rest was left out"
        if res.is_error:
            self.failures += 1
        return {"ok": not res.is_error, "text": text or "(no output)", "ms": round((time.perf_counter() - t) * 1000, 1)}

    async def _call(self, tool: str, arguments: dict, timeout_s: float):
        return await self._session.call_tool(tool, arguments, read_timeout_seconds=timeout_s)

    def close(self) -> None:
        if self.portal is not None and self._stop is not None:
            try:
                self.portal.call(self._stop.set)
                if self._task is not None:
                    self._task.result(timeout=10)
            except Exception:  # noqa: BLE001 (closing anyway)
                pass
        self._shut()
        if self.state != "failed":
            self.state = "idle"

    def _shut(self) -> None:
        if self._portal_cm is not None:
            try:
                self._portal_cm.__exit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
        self._portal_cm = self.portal = None

    def show(self) -> dict:
        return {"state": self.state, "error": self.error, "tools": [{"name": t["name"],
                "description": t["description"][:200]} for t in self.tools], "calls": self.calls,
                "failures": self.failures}


def _why(e: BaseException, log: Path) -> str:
    while getattr(e, "exceptions", None):  # an exception group from the event loop: the first real error
        e = e.exceptions[0]
    why = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
    try:
        tail = log.read_text(errors="replace").strip().splitlines()[-3:]
    except OSError:
        tail = []
    return (why + (" · " + " · ".join(tail) if tail else ""))[:400]


class Servers:
    """The servers a person added, and the ones connected now."""

    def __init__(self, path: Path, logs: Path):
        self.path, self.logs = Path(path), Path(logs)
        self.lock = threading.Lock()
        self.links: dict[str, Link] = {}
        self._specs: dict[str, Spec] = self._load()

    def _load(self) -> dict[str, Spec]:
        try:
            raw = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}
        out = {}
        for x in raw.get("servers", []) if isinstance(raw, dict) else []:
            try:
                s = Spec(str(x["name"]), str(x["command"]), [str(a) for a in x.get("args", [])],
                         {str(k): str(v) for k, v in (x.get("env") or {}).items()})
            except (KeyError, TypeError, AttributeError):
                continue
            if NAME.match(s.name):
                out[s.name] = s
        return out

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"servers": [asdict(s) for s in self._specs.values()]}, f, indent=1)
        os.replace(tmp, self.path)
        os.chmod(self.path, 0o600)

    def add(self, s: Spec) -> dict:
        with self.lock:
            if s.name not in self._specs and len(self._specs) >= MAX_SERVERS:
                raise ValueError(f"at most {MAX_SERVERS} servers")
            if s.name in self.links and self.links[s.name].state == "connected":
                raise ValueError(f"disconnect {s.name} before changing it")
            self._specs[s.name] = s
            self._save()
        return self.show()

    def remove(self, name: str) -> dict:
        self.disconnect(name)
        with self.lock:
            if self._specs.pop(name, None) is None:
                raise KeyError(name)
            self.links.pop(name, None)
            self._save()
        return self.show()

    def connect(self, name: str, cwd: Path | None) -> Link:
        """Start the server and list its tools (blocks until it answers, or fails, at most CONNECT_S)."""
        with self.lock:
            s = self._specs.get(name)
            if s is None:
                raise KeyError(name)
            old = self.links.get(name)
            if old is not None and old.state in ("connected", "connecting"):
                return old
            link = Link(s, cwd, self.logs / f"{name}.log")
            self.links[name] = link
        link.connect()
        return link

    def disconnect(self, name: str) -> None:
        with self.lock:
            link = self.links.get(name)
        if link is not None:
            link.close()

    def link(self, name: str) -> Link | None:
        with self.lock:
            got = self.links.get(name)
        return got if got is not None and got.state == "connected" else None

    def tools(self) -> list[tuple[str, dict]]:
        """(server, tool) for every connected server's tools."""
        with self.lock:
            links = [(n, x) for n, x in self.links.items() if x.state == "connected"]
        return [(n, t) for n, x in links for t in x.tools]

    def show(self) -> list[dict]:
        with self.lock:
            out = []
            for name, s in self._specs.items():
                link = self.links.get(name)
                out.append({**s.show(), **(link.show() if link else {"state": "idle", "error": None, "tools": [],
                                                                     "calls": 0, "failures": 0})})
            return out

    def close(self) -> None:
        with self.lock:
            links = list(self.links.values())
        for x in links:
            x.close()


def arguments(schema: dict, args: Any) -> dict:
    """The model's arguments for an MCP tool, as an object (numbers written as text are turned back into numbers
    where the tool's schema asks for them)."""
    if not isinstance(args, dict):
        return {}
    props = (schema or {}).get("properties") or {}
    out = {}
    for k, v in args.items():
        kind = (props.get(k) or {}).get("type")
        if isinstance(v, str) and kind in ("integer", "number"):
            try:
                v = int(v) if kind == "integer" else float(v)
            except ValueError:
                pass
        elif isinstance(v, str) and kind == "boolean" and v.lower() in ("true", "false"):
            v = v.lower() == "true"
        elif isinstance(v, str) and kind in ("object", "array"):
            try:
                v = json.loads(v)
            except ValueError:
                pass
        out[k] = v
    return out
