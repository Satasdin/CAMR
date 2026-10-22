"""Checking code before it is shown (CAMR Personal): its syntax only, on this computer. Nothing is run.

Python is parsed by Python's own parser (``ast.parse``); JavaScript by ``node --check``, which parses a file without
running it. Other languages are not checked. A small model's code with a syntax error gets one retry with the error
message (``Assistant.events``).
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

FENCE = re.compile(r"```([\w+#.-]*)[ \t]*\n(.*?)```", re.S)
PYTHON = {"python", "py", "python3", ""}
JAVASCRIPT = {"javascript", "js", "node", "mjs", "cjs"}


def blocks(answer: str) -> list[tuple[str, str]]:
    """The fenced code blocks of an answer: (language, code)."""
    return [(m.group(1).lower(), m.group(2)) for m in FENCE.finditer(answer or "")]


def check(language: str, code: str) -> dict | None:
    """{"language", "ok", "error", "line"} for Python or JavaScript; None for a language that is not checked."""
    lang = (language or "").lower()
    if lang in PYTHON:
        if not lang and not re.search(r"^\s*(?:def |class |import |from |print\(|for |if |return )", code, re.M):
            return None  # an unlabelled block that does not look like Python (a shell command, output)
        try:
            ast.parse(code)
        except SyntaxError as exc:
            return {"language": "Python", "ok": False, "error": exc.msg, "line": exc.lineno}
        return {"language": "Python", "ok": True, "error": "", "line": None}
    if lang in JAVASCRIPT:
        node = shutil.which("node")
        if node is None:
            return None
        suffix = ".mjs" if re.search(r"^\s*(?:import|export)\s", code, re.M) else ".js"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"answer{suffix}"
            path.write_text(code)
            try:
                done = subprocess.run([node, "--check", str(path)], capture_output=True, text=True, timeout=15)
            except (OSError, subprocess.TimeoutExpired):
                return None
        if done.returncode == 0:
            return {"language": "JavaScript", "ok": True, "error": "", "line": None}
        err = done.stderr.strip().splitlines()
        line = next((int(m.group(1)) for ln in err for m in [re.search(r"answer\.m?js:(\d+)", ln)] if m), None)
        msg = next((ln for ln in err if "Error" in ln), err[-1] if err else "syntax error")
        return {"language": "JavaScript", "ok": False, "error": msg.strip(), "line": line}
    return None


def check_answer(answer: str) -> dict | None:
    """The check of an answer's code: the first block that fails, else the first that passes; None if none checked."""
    results = [r for lang, code in blocks(answer) for r in [check(lang, code)] if r is not None]
    return next((r for r in results if not r["ok"]), results[0] if results else None)
