"""The agent's tools, and the one place they run.

- In the workspace, with no question asked: ``read_file``, ``list_files``, ``search``, ``write_file`` and
  ``edit_file``, each confined to the folder (camr_engine.agentic.workspace).
- After the person allows each call in the page: ``run_shell`` and every MCP server's tools.
- ``load_skill`` reads a skill's instructions.

A persona may narrow the list. A call of a tool the agent does not have, or with arguments it cannot use, comes back
to the model as a failure it can read; nothing else runs.

Every result the model reads back is at most RESULT_LIMIT characters (a file is read at most READ_LINES lines at a
time), so one big file never floods the prompt. What waits at the gate is shown to the person exactly as it will run:
a command or MCP arguments holding control characters (other than new lines and tabs) or invisible ones (such as the
right-to-left override, which can make text read differently from what runs) are refused before anyone is asked.
"""

from __future__ import annotations

import json
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from camr_engine.agentic import shell
from camr_engine.agentic.gate import Gate
from camr_engine.agentic.servers import Servers, arguments, split_name, tool_name
from camr_engine.agentic.skills import Skills
from camr_engine.agentic.workspace import Outside, Workspace, Wrote

RESULT_LIMIT = 12_000  # characters of one result the model reads back
READ_LINES = 400  # lines of a file the model reads at once
OUTPUT_SHOWN = 20_000  # characters of a call's output kept for the page (its start and its end)
DIFF_SHOWN = 200_000  # a written file bigger than this (before or after) is shown without its diff


def _fn(name: str, description: str, props: dict[str, tuple[str, str]], required: list[str]) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": {k: {"type": t, "description": d} for k, (t, d) in props.items()},
        "required": required}}}


SPECS = {
    "read_file": _fn("read_file", "Read a text file in the workspace, with line numbers.", {
        "path": ("string", "the file, relative to the workspace"),
        "start_line": ("integer", "the first line to read (default 1)"),
        "lines": ("integer", "how many lines to read (default: to the end)")}, ["path"]),
    "list_files": _fn("list_files", "List the files and folders in a folder of the workspace.", {
        "path": ("string", "the folder, relative to the workspace (default: the workspace)"),
        "depth": ("integer", "how many levels down (default 2)")}, []),
    "search": _fn("search", "Find the lines holding some text in the workspace's files.", {
        "pattern": ("string", "the text to find (ignoring case)"),
        "path": ("string", "a folder or file to search in (default: the workspace)"),
        "glob": ("string", "only files whose name matches, such as *.py"),
        "regex": ("boolean", "true to read the pattern as a regular expression")}, ["pattern"]),
    "write_file": _fn("write_file", "Write a whole file in the workspace: a new file, or all of an old one.", {
        "path": ("string", "the file, relative to the workspace"),
        "content": ("string", "the file's whole text")}, ["path", "content"]),
    "edit_file": _fn("edit_file", "Change one part of a file: replace text copied exactly from it.", {
        "path": ("string", "the file, relative to the workspace"),
        "old_text": ("string", "the exact text to replace; it must appear once in the file"),
        "new_text": ("string", "the text to put in its place")}, ["path", "old_text", "new_text"]),
    "run_shell": _fn("run_shell", "Run a shell command in the workspace folder. The user must allow each command "
                     "before it runs, and may refuse.", {
                         "command": ("string", "the command, as typed in a terminal"),
                         "timeout_s": ("integer", "seconds before it is stopped (default 120)")}, ["command"]),
    "load_skill": _fn("load_skill", "Read the instructions of one of the skills listed in your instructions.", {
        "name": ("string", "the skill's name")}, ["name"]),
}
LOCAL = ("read_file", "list_files", "search", "write_file", "edit_file")
ALIASES = {"old_text": ("old_string", "old", "find", "search"), "new_text": ("new_string", "new", "replace"),
           "content": ("text", "contents", "code"), "path": ("file", "file_path", "filename", "folder", "dir"),
           "command": ("cmd",), "start_line": ("start", "offset", "line"), "lines": ("limit", "count")}


@dataclass
class Done:
    tool: str
    args: dict
    ok: bool
    text: str  # what the model reads back
    ms: float
    output: str = ""  # what the page shows, when more than the model reads
    ask: dict | None = None  # the approval this call waited for
    wrote: Wrote | None = None
    offset: int = 0  # for an edit: the line in the file where the new text starts (0-based)
    content: str = ""  # for a write or an edit: the text the call wrote, as written in the reply

    def show(self) -> dict:
        w = self.wrote
        return {"tool": self.tool, "args": shown_args(self.args), "ok": self.ok, "text": self.text[:4000],
                "output": _ends(self.output or self.text, OUTPUT_SHOWN), "ms": round(self.ms, 1), "ask": self.ask,
                "path": w.path if w else None,
                "diff": {"before": w.before, "after": w.after}
                if w and len(w.after) < DIFF_SHOWN and len(w.before or "") < DIFF_SHOWN else None}


def _ends(text: str, limit: int) -> str:
    """The start and the end of a long text (a command's errors are at its end)."""
    if len(text) <= limit:
        return text
    head = limit // 5
    return f"{text[:head]}\n… {len(text) - limit:,} characters left out …\n{text[-(limit - head):]}"


def hidden(value) -> str | None:
    """The first control or invisible character in a text (or in any text inside a list or object), as ``U+202E``,
    or None. New lines and tabs are allowed."""
    if isinstance(value, str):
        for c in value:
            if c not in "\n\t" and unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp"):
                return f"U+{ord(c):04X}"
        return None
    if isinstance(value, dict):
        items = [*value.keys(), *value.values()]
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        return None
    for x in items:
        got = hidden(x)
        if got:
            return got
    return None


def shown_args(args: dict) -> dict:
    """The arguments for the transcript: long text shortened."""
    out = {}
    for k, v in args.items():
        if isinstance(v, str) and len(v) > 400:
            out[k] = f"{v[:400]}… ({v.count(chr(10)) + 1} lines)"
        else:
            out[k] = v
    return out


def _arg(args: dict, key: str, default=None):
    if key in args:
        return args[key]
    for alt in ALIASES.get(key, ()):
        if alt in args:
            return args[alt]
    return default


def _int(v, default: int | None) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _clip(text: str, limit: int = RESULT_LIMIT) -> str:
    """At most ``limit`` characters, saying how many were left out."""
    if len(text) <= limit:
        return text
    keep = limit - 48
    return text[:keep] + f"\n… {len(text) - keep:,} more characters left out"


class Toolbox:
    def __init__(self, workspace: Workspace | None, gate: Gate, *, skills: Skills | None = None,
                 servers: Servers | None = None, allows: Callable[[str], bool] = lambda name: True):
        self.workspace, self.gate, self.skills, self.servers, self.allows = workspace, gate, skills, servers, allows

    def specs(self) -> list[dict]:
        """The tool list for the chat template."""
        out = [SPECS[n] for n in ("read_file", "list_files", "search", "write_file", "edit_file", "run_shell")
               if self.workspace is not None and self.allows(n)]
        if self.skills is not None and self.skills.all() and self.allows("load_skill"):
            out.append(SPECS["load_skill"])
        for server, t in self.servers.tools() if self.servers is not None else []:
            name = tool_name(server, t["name"])
            if self.allows(name):
                out.append({"type": "function", "function": {
                    "name": name, "description": f"[{server}] {t['description']} The user must allow each call.",
                    "parameters": t["schema"]}})
        return out

    def names(self) -> set[str]:
        return {s["function"]["name"] for s in self.specs()}

    def run(self, name: str, args: dict, *, owner: str, label: str = "", cancel: threading.Event | None = None,
            on_output: Callable[[str], None] | None = None, on_wait: Callable[[dict], None] | None = None) -> Done:
        """Run one call and say how it went (what the model reads back at most RESULT_LIMIT characters). Never
        raises for the model's mistakes."""
        done = self._run(name, args, owner=owner, label=label, cancel=cancel, on_output=on_output, on_wait=on_wait)
        done.text = _clip(done.text)
        return done

    def _run(self, name: str, args: dict, *, owner: str, label: str, cancel: threading.Event | None,
             on_output: Callable[[str], None] | None, on_wait: Callable[[dict], None] | None) -> Done:
        t = time.perf_counter()
        args = args if isinstance(args, dict) else {}
        if name not in self.names():
            known = ", ".join(sorted(self.names())) or "none"
            return Done(name, args, False, f"there is no tool {name!r} here; the tools are: {known}",
                        (time.perf_counter() - t) * 1000)
        try:
            if name in LOCAL:
                return self._local(name, args, t)
            if name == "load_skill":
                n = str(_arg(args, "name", ""))
                try:
                    text = self.skills.load(n)
                except KeyError:
                    return Done(name, args, False, f"there is no skill {n!r}", (time.perf_counter() - t) * 1000)
                return Done(name, args, True, _clip(text), (time.perf_counter() - t) * 1000)
            if name == "run_shell":
                return self._shell(args, t, owner, label, cancel, on_output, on_wait)
            return self._mcp(name, args, t, owner, label, cancel, on_wait)
        except Outside as e:
            return Done(name, args, False, str(e), (time.perf_counter() - t) * 1000)

    def _local(self, name: str, args: dict, t: float) -> Done:
        ws = self.workspace
        if name == "read_file":
            lines = _int(_arg(args, "lines"), None)
            lines = READ_LINES if not lines or lines < 1 else min(lines, READ_LINES)
            got = ws.read(str(_arg(args, "path", "")), _int(_arg(args, "start_line"), 1) or 1, lines,
                          limit=RESULT_LIMIT - 200)
            more = f"\n(lines {got['from']}–{got['to']} of {got['lines']}; read on with start_line={got['to'] + 1})" \
                if got["truncated"] else ""
            return Done(name, args, True, (got["text"] or "(the file is empty)") + more,
                        (time.perf_counter() - t) * 1000)
        if name == "list_files":
            got = ws.listing(str(_arg(args, "path", ".") or "."), _int(_arg(args, "depth"), 2) or 2)
            return Done(name, args, True, got["text"] + ("\n… more left out" if got["more"] else ""),
                        (time.perf_counter() - t) * 1000)
        if name == "search":
            regex = _arg(args, "regex", False)
            got = ws.search(str(_arg(args, "pattern", "")), str(_arg(args, "path", ".") or "."),
                            _arg(args, "glob") or None, regex is True or str(regex).lower() == "true")
            return Done(name, args, True, got["text"] + ("\n… more matches left out" if got["more"] else ""),
                        (time.perf_counter() - t) * 1000)
        if name == "write_file":
            content = _arg(args, "content")
            if not isinstance(content, str):
                raise Outside("write_file needs the file's whole text as content")
            w = ws.write(str(_arg(args, "path", "")), content)
            lines = content.count("\n") + (0 if content.endswith("\n") or not content else 1)
            verb = "made" if w.before is None else "replaced"
            return Done(name, args, True, f"{verb} {w.path}: {lines} lines, {w.bytes:,} bytes",
                        (time.perf_counter() - t) * 1000, wrote=w, content=content)
        old, new = _arg(args, "old_text"), _arg(args, "new_text")
        if not isinstance(old, str) or not isinstance(new, str):
            raise Outside("edit_file needs old_text and new_text")
        w = ws.edit(str(_arg(args, "path", "")), old, new)
        at = w.before.index(old)
        offset = w.before[:at].count("\n")
        return Done(name, args, True, f"changed {w.path}: {old.count(chr(10)) + 1} lines replaced by "
                    f"{new.count(chr(10)) + 1}", (time.perf_counter() - t) * 1000, wrote=w, offset=offset,
                    content=new)

    def _shell(self, args, t, owner, label, cancel, on_output, on_wait) -> Done:
        command = _arg(args, "command")
        if not isinstance(command, str) or not command.strip() or len(command) > 4000:
            raise Outside("run_shell needs a command, at most 4000 characters")
        bad = hidden(command)
        if bad:
            raise Outside(f"the command holds a control or invisible character ({bad}), so it would not read as it "
                          "runs; write it with plain characters only")
        timeout = max(1, min(_int(_arg(args, "timeout_s"), shell.TIMEOUT_S) or shell.TIMEOUT_S, shell.MAX_TIMEOUT_S))
        what = {"command": command, "cwd": str(self.workspace.root), "timeout_s": timeout}
        if on_wait is not None:
            on_wait(what)
        ask = self.gate.ask("shell", what, owner=owner, label=label, cancel=cancel)
        if not ask.allowed:
            return Done("run_shell", args, False, f"the user did not run this command ({ask.decision})",
                        (time.perf_counter() - t) * 1000, ask=ask.show())
        if on_output is not None:
            on_output(f"\r\n$ {ask.what['command']}\r\n")
        ran = shell.run(ask.what["command"], Path(ask.what["cwd"]), timeout_s=ask.what["timeout_s"],
                        on_output=on_output, cancel=cancel)
        ok = ran.code == 0
        return Done("run_shell", args, ok, ran.summary(), (time.perf_counter() - t) * 1000, output=ran.output,
                    ask=ask.show())

    def _mcp(self, name, args, t, owner, label, cancel, on_wait) -> Done:
        server, tool = split_name(name) or ("", "")
        link = self.servers.link(server) if self.servers is not None else None
        spec = next((x for x in (link.tools if link else []) if x["name"] == tool), None)
        if link is None or spec is None:
            return Done(name, args, False, f"the {server} server is not connected", (time.perf_counter() - t) * 1000)
        what = {"server": server, "tool": tool, "arguments": arguments(spec["schema"], args)}
        bad = hidden(what["arguments"])
        if bad:
            raise Outside(f"the arguments hold a control or invisible character ({bad}), so they would not read as "
                          "they run; write them with plain characters only")
        if on_wait is not None:
            on_wait(what)
        ask = self.gate.ask("mcp", what, owner=owner, label=label, cancel=cancel)
        if not ask.allowed:
            return Done(name, args, False, f"the user did not allow this call ({ask.decision})",
                        (time.perf_counter() - t) * 1000, ask=ask.show())
        got = link.call(ask.what["tool"], ask.what["arguments"])
        return Done(name, args, got["ok"], _clip(got["text"]), (time.perf_counter() - t) * 1000, ask=ask.show())


def short(args: dict, limit: int = 160) -> str:
    """Arguments on one line, for the transcript the model reads back."""
    parts = []
    for k, v in args.items():
        if isinstance(v, str) and ("\n" in v or len(v) > 80):
            parts.append(f"{k}=<{v.count(chr(10)) + 1} lines>")
        else:
            parts.append(f"{k}={json.dumps(v, ensure_ascii=False)}")
    out = ", ".join(parts)
    return out if len(out) <= limit else out[:limit] + "…"
