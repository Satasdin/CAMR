"""Running one shell command the person allowed: in the workspace folder, with ``/bin/sh -c``, as this user.

The command gets a cleaned environment (the path, home, user, language and terminal settings, and nothing else, so
keys and tokens in the app's own environment never reach it), no input, a time limit, and its own process group, so
stopping it stops whatever it started. Output (standard output and errors together) is handed on as it comes, for
the page's terminal, and kept up to a limit, its start and its end. When the command ends, anything it left running
in the background is stopped too: a server to keep running belongs in the person's own terminal. When the app itself
exits (Ctrl-C included), every command still running is stopped with it, since its own process group never hears
the app's Ctrl-C.
"""

from __future__ import annotations

import atexit
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

TIMEOUT_S = 120
MAX_TIMEOUT_S = 600
KEEP = 200_000  # characters of output kept: the first and last halves
KEPT_ENV = ("PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR")
_SHELL = "/bin/sh"
_LIVE: set[int] = set()  # the process groups of commands running now
_LIVE_LOCK = threading.Lock()


def stop_all() -> int:
    """Stop every command still running, and what it started (at the app's exit). Returns how many."""
    with _LIVE_LOCK:
        groups = list(_LIVE)
        _LIVE.clear()
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for g in groups:
            try:
                os.killpg(g, sig)
            except (ProcessLookupError, PermissionError):
                pass
        if sig == signal.SIGTERM and groups:
            time.sleep(0.2)
    return len(groups)


atexit.register(stop_all)


def environment() -> dict[str, str]:
    env = {k: os.environ[k] for k in KEPT_ENV if k in os.environ}
    env.setdefault("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    env["TERM"] = "xterm-256color"
    env["PAGER"] = "cat"
    env["GIT_PAGER"] = "cat"
    return env


@dataclass
class Ran:
    command: str
    code: int | None  # the exit code; None when it was stopped
    output: str
    seconds: float
    timed_out: bool = False
    stopped: bool = False
    truncated: bool = False

    def summary(self, limit: int = 6000) -> str:
        """What the model reads back: the exit code and the output, its end kept when it is long."""
        state = ("timed out" if self.timed_out else "stopped" if self.stopped else f"exit code {self.code}")
        out = self.output if len(self.output) <= limit else "…" + self.output[-limit:]
        return f"{state} after {self.seconds:.1f} s\n{out}".rstrip()


def run(command: str, cwd: Path, *, timeout_s: float = TIMEOUT_S, on_output: Callable[[str], None] | None = None,
        cancel: threading.Event | None = None) -> Ran:
    timeout_s = max(1.0, min(float(timeout_s or TIMEOUT_S), MAX_TIMEOUT_S))
    t = time.perf_counter()
    proc = subprocess.Popen([_SHELL, "-c", command], cwd=str(cwd), env=environment(), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    with _LIVE_LOCK:
        _LIVE.add(proc.pid)  # its own session: the group's id is its pid
    try:
        return _watch(proc, command, t, timeout_s, on_output, cancel)
    finally:
        with _LIVE_LOCK:
            _LIVE.discard(proc.pid)


def _watch(proc: subprocess.Popen, command: str, t: float, timeout_s: float,
           on_output: Callable[[str], None] | None, cancel: threading.Event | None) -> Ran:
    head: list[str] = []
    tail: list[str] = []
    sizes = {"head": 0, "tail": 0, "dropped": 0}

    def keep(chunk: str) -> None:
        """The first and the last KEEP // 2 characters, exactly."""
        room = KEEP // 2 - sizes["head"]
        if room > 0:
            head.append(chunk[:room])
            sizes["head"] += len(head[-1])
            chunk = chunk[room:]
            if not chunk:
                return
        tail.append(chunk)
        sizes["tail"] += len(chunk)
        while sizes["tail"] > KEEP // 2:
            extra = sizes["tail"] - KEEP // 2
            if len(tail[0]) <= extra:
                cut = tail.pop(0)
            else:
                cut, tail[0] = tail[0][:extra], tail[0][extra:]
            sizes["tail"] -= len(cut)
            sizes["dropped"] += len(cut)

    def read() -> None:
        fd = proc.stdout.fileno()
        while True:
            try:
                data = os.read(fd, 65536)
            except OSError:
                break
            if not data:
                break
            chunk = data.decode("utf-8", "replace")
            keep(chunk)
            if on_output is not None:
                try:
                    on_output(chunk)
                except Exception:  # noqa: BLE001 (the page's terminal never stops the command)
                    pass

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    timed_out = stopped = False
    limit = time.monotonic() + timeout_s
    while proc.poll() is None:
        if cancel is not None and cancel.is_set():
            stopped = True
            break
        if time.monotonic() > limit:
            timed_out = True
            break
        time.sleep(0.02)
    if proc.poll() is None:
        _stop(proc)
    else:
        try:  # whatever it left running in the background stops with it
            os.killpg(proc.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    reader.join(timeout=2.0)
    proc.stdout.close()
    out = "".join(head) + (f"\n… {sizes['dropped']:,} characters left out …\n" if sizes["dropped"] else "") + \
        "".join(tail)
    return Ran(command, None if (timed_out or stopped) else proc.returncode, out, time.perf_counter() - t,
               timed_out, stopped, bool(sizes["dropped"]))


def _stop(proc: subprocess.Popen) -> None:
    """Stop the command and everything it started: politely, then for good."""
    for sig, wait in ((signal.SIGTERM, 2.0), (signal.SIGKILL, 2.0)):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue
