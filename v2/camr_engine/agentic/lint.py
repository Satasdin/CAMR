"""What can be seen wrong in a page's own files without running them: a script that does not parse, code that only
works outside a browser, elements a script looks for that the page does not have, and handlers written into the
HTML. A small model makes each of these often, and with the page's scripts off (the preview's default) the browser
cannot show them, so the page test adds these to its report.

These are rules, not the model's judgment. The syntax check uses Node's parser (``node --check``, which reads and does
not run the file) when Node is installed, and is skipped quietly when it is not.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

SCRIPT_SRC = re.compile(r"<script\b[^>]*\bsrc\s*=\s*[\"']([^\"'#?]+)[\"']", re.I)
IDS = re.compile(r"\bid\s*=\s*[\"']([^\"']+)[\"']", re.I)
CLASSES = re.compile(r"\bclass\s*=\s*[\"']([^\"']+)[\"']", re.I)
LOOKS_ID = re.compile(r"getElementById\(\s*[\"'`]([\w-]+)[\"'`]\s*\)|querySelector(?:All)?\(\s*[\"'`]#([\w-]+)[\"'`]")
LOOKS_CLASS = re.compile(r"querySelector(?:All)?\(\s*[\"'`]\.([\w-]+)[\"'`]|getElementsByClassName\(\s*[\"'`]([\w-]+)")
HANDLERS = re.compile(r"\son(click|submit|change|input|load)\s*=", re.I)
NOT_BROWSER = ((re.compile(r"\brequire\s*\("), "require(), which a browser does not have"),
               (re.compile(r"^\s*import\s.+\sfrom\s", re.M), "import ... from, which a plain script cannot use"),
               (re.compile(r"\bmodule\.exports\b"), "module.exports, which a browser does not have"),
               (re.compile(r"\bprocess\.(env|argv)\b"), "process, which a browser does not have"))
CHECK_S = 5


def _syntax(path: Path) -> str | None:
    """Node's complaint about a script's syntax, or None (also when Node is not there)."""
    node = shutil.which("node")
    if node is None:
        return None
    try:
        got = subprocess.run([node, "--check", str(path)], capture_output=True, text=True, timeout=CHECK_S,
                             stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if got.returncode == 0:
        return None
    lines = [x for x in got.stderr.splitlines() if x.strip()]
    msg = next((x for x in lines if "Error" in x), lines[-1] if lines else "it does not parse")
    where = next((x for x in lines if str(path) in x), "")
    line = where.rsplit(":", 1)[-1] if where else ""
    return f"{msg.strip()}" + (f" (line {line})" if line.isdigit() else "")


def page_problems(ws, page: str) -> list[str]:
    """Problems in ``page`` and the local scripts it loads, read through the workspace ``ws``
    (camr_engine.agentic.workspace), which keeps to the project and leaves symlinks out and files of secrets alone."""
    from camr_engine.agentic.workspace import Outside

    try:
        html = ws.text(page)[1]
    except (Outside, OSError):
        return []
    ids = {i.strip() for i in IDS.findall(html)}
    classes = {c for group in CLASSES.findall(html) for c in group.split()}
    out = []
    scripts = []
    for src in SCRIPT_SRC.findall(html):
        if re.match(r"^[a-z]+:|^//", src, re.I):
            continue
        rel = (Path(page).parent / src).as_posix()
        try:
            f = ws.path(rel)
            scripts.append((src, f, ws.text(rel)[1]))
        except (Outside, OSError):
            continue
    for src, f, js in scripts:
        bad = _syntax(f)
        if bad:
            out.append(f"{src} does not parse: {bad}. Fix it, or nothing in it runs")
        for pattern, what in NOT_BROWSER:
            if pattern.search(js):
                out.append(f"{src} uses {what}: the whole script stops there. Remove it")
        wanted = {a or b for a, b in LOOKS_ID.findall(js)} - ids
        if wanted:
            out.append(f"{src} looks for {', '.join('#' + w for w in sorted(wanted))}, which {page} does not have. "
                       "Use the ids the page has, or add them to the page")
        cls = {a or b for a, b in LOOKS_CLASS.findall(js)} - classes
        if cls:
            out.append(f"{src} looks for {', '.join('.' + c for c in sorted(cls))}, which {page} does not use")
    handlers = sorted({h.lower() for h in HANDLERS.findall(html)})
    if handlers and scripts:
        out.append(f"{page} has on{'/on'.join(handlers)} attributes written into it: move each into "
                   f"{scripts[0][0]} with addEventListener, and give the elements ids or data attributes instead")
    return out
