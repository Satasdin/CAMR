"""Hard front-end briefs (docs/real-use/HARD.md): run one through the lead with a chosen model, or check a page by the
motion rules in Chrome.

    # mark a hand-made page (copied into a scratch project with the vendored files, then checked in Chrome)
    .venv/bin/python scripts/hard.py check H1 ../docs/real-use/hard/h1-reference

    # build a brief with a model, then collect REPORT.md, the motion numbers and the screenshot strip
    .venv/bin/python scripts/hard.py run H1 --model claude-sonnet-5-5
    .venv/bin/python scripts/hard.py run H1 --model ollama:qwen3:8b
    .venv/bin/python scripts/hard.py run H1 --model mlx            # the app's model, Qwen3 4B in MLX

Projects go under $CAMR_PROJECTS (default: work/scratch-hard beside v2), never ~/CAMR Projects. A local model (MLX or
Ollama) does not start while a benchmark measures (~/.camr/measuring.json), so the GPU stays the benchmark's. The run
plays the app's part itself: the page test is answered by Playwright's Chrome (connected, and trusted, as a person
would in the app), and a question is answered from the brief's told facts, or left unanswered.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import threading
import time
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V2))

from camr_engine.agentic import motion  # noqa: E402
from camr_engine.agentic.workspace import Workspace  # noqa: E402

HARD = V2.parent / "docs" / "real-use" / "HARD.md"
PAGE_FILES = (".html", ".css", ".js", ".mjs", ".json", ".svg", ".png", ".jpg", ".webp", ".glb")


def projects() -> Path:
    p = Path(os.environ.get("CAMR_PROJECTS") or V2.parent / "work" / "scratch-hard").expanduser()
    if p.resolve() == (Path.home() / "CAMR Projects").resolve():
        raise SystemExit("not ~/CAMR Projects: set CAMR_PROJECTS to a scratch folder")
    p.mkdir(parents=True, exist_ok=True)
    return p


def briefs(path: Path = HARD) -> dict[str, dict]:
    """The briefs in HARD.md: {id: {title, brief, told, rules}}, each from its "## H<n>: title" section."""
    out: dict[str, dict] = {}
    cur = None
    mode = None
    for line in path.read_text().splitlines():
        m = re.match(r"^##\s+(H\d+):\s*(.+)$", line)
        if m:
            cur = out[m.group(1)] = {"title": m.group(2).strip(), "brief": "", "told": [], "rules": []}
            mode = None
            continue
        if cur is None:
            continue
        b = re.match(r"^>\s*\*\*Brief:\*\*\s*(.+)$", line)
        if b:
            cur["brief"] = b.group(1).strip()
            continue
        if line.startswith("**Told"):
            mode = "told"
            continue
        if line.startswith("**Pass rules"):
            mode = "rules"
            continue
        item = re.match(r"^\s*[-*]\s+(.+)$", line)
        if item and mode:
            cur[mode].append(item.group(1).strip())
        elif not line.strip() == "" and not item:
            mode = None if line.startswith("**") else mode
    return out


STOP_CAPS = {"The", "Its", "It", "A", "An", "On", "From", "To", "In", "Of"}


def fact_words(told: str) -> list[str]:
    """The words a told fact must show: its names and its numbers ("Halcyon-7", "14:00", "550"), not "The"."""
    got = re.findall(r"[A-Z][A-Za-z0-9-]+|\d[\d,.:]*\d|\d", told)
    return [w for w in got if w not in STOP_CAPS]


def brief_rules(link, url: str, told: list[str], wait: float = 2.5) -> dict:
    """The brief's own rules the motion check does not cover, read off the page in Chrome at a desktop's width:
    the countdown's numbers change from one moment to the next, and every told fact is on the page (a fact counts
    when at least 70% of its names and numbers are in the page's text). "Nothing that was not told" is left to a
    person's eye."""
    link.call("browser_navigate", {"url": url})
    link.call("browser_resize", {"width": 1440, "height": 900})
    read = lambda: str(link.call("browser_evaluate", {"function": "() => document.body.innerText"}).get("text", ""))
    first = read()
    time.sleep(wait)
    second = read()
    ticks = re.findall(r"\d+", first) != re.findall(r"\d+", second)
    page = second.lower()
    facts = []
    for t in told:
        words = fact_words(t)
        have = [w for w in words if w.lower() in page]
        facts.append({"fact": t, "shown": len(have), "of": len(words),
                      "ok": not words or len(have) / len(words) >= 0.7,
                      "missing": [w for w in words if w.lower() not in page]})
    return {"countdown_ticks": ticks, "facts": facts, "facts_ok": sum(f["ok"] for f in facts),
            "facts_of": len(facts), "passed": ticks and all(f["ok"] for f in facts)}


def show_rules(r: dict) -> None:
    print(f"  countdown ticks: {'pass' if r['countdown_ticks'] else 'FAIL'}")
    print(f"  told facts on the page: {r['facts_ok']} of {r['facts_of']}")
    for f in r["facts"]:
        if not f["ok"]:
            print(f"    missing from \"{f['fact'][:60]}\": {', '.join(f['missing'])}")


def playwright_link(cwd: Path):
    from camr_engine.agentic.plugins import BY_ID
    from camr_engine.agentic.servers import Link, Spec

    p = BY_ID["playwright"]
    link = Link(Spec("playwright", p["command"], p["args"], trusted=True), cwd, cwd / ".camr-logs" / "playwright.log")
    link.connect()
    if link.state != "connected":
        raise SystemExit(f"Playwright did not start: {link.error}")
    return link


def show(motion_result: dict) -> None:
    m = motion_result.get("measured") or {}
    print(f"  measured: {m.get('frames')} frames in {m.get('seconds')} s, scroll {m.get('max')} px, "
          f"canvas {m.get('canvas', {}) and {k: v for k, v in (m.get('canvas') or {}).items() if k != 'samples'}}")
    for line in motion.summary(motion_result):
        print(" ", line)


def check(bid: str, src: Path, name: str | None = None) -> dict:
    """Copy a hand-made page into a fresh scratch project with the vendored kits, then mark it in Chrome."""
    from camr_engine.agentic.plugins import browser_check
    from camr_engine.agentic.serve import close_all, serving

    brief = briefs()[bid]
    dest = projects() / (name or f"{bid.lower()}-{src.name}")
    if dest.exists():  # a scratch folder of an earlier check: moved aside, never deleted
        dest.rename(dest.with_name(f"{dest.name}-{int(time.time())}"))
    dest.mkdir(parents=True)
    for f in src.iterdir():
        if f.is_file() and f.suffix.lower() in PAGE_FILES:
            shutil.copy2(f, dest / f.name)
    ws = Workspace(dest)
    motion.install(ws, motion.kits_for(brief["brief"]))
    page = (dest / "index.html").read_text()
    want = motion.wants(brief["brief"], page)
    link = playwright_link(dest)
    try:
        got = browser_check(link, serving(ws).url("index.html"), motion=want)
        rules = brief_rules(link, serving(ws).url("index.html"), brief["told"])
    finally:
        link.close()
        close_all()
    kept = motion.keep_report(ws, got.get("motion") or {})
    print(f"{bid} {src.name} -> {dest}")
    print(f"  wanted: {sorted(want)}; errors: {got.get('errors')}; failed: {len(got.get('failed') or [])}")
    show(got.get("motion") or {})
    print(f"  strip: {kept['strip']}")
    show_rules(rules)
    return {"dest": str(dest), "check": got, "kept": kept, "rules": rules}


def brains(model: str):
    """The model for every part: claude-..., ollama:<name>, or mlx[:<hf name>] (the app's own reader, memory off)."""
    if model.startswith("claude-"):
        from camr_engine.agentic.claude_brain import ClaudeBrain

        return lambda spec: ClaudeBrain(model)
    if model.startswith("ollama:"):
        from camr_engine.agentic.ollama_brain import OllamaBrain

        return lambda spec: OllamaBrain(model.removeprefix("ollama:"))
    if model == "mlx" or model.startswith("mlx:"):
        from camr_engine.agentic.brain import PlainBrain
        from camr_engine.models import Reader

        name = model.partition(":")[2]
        reader = Reader(name) if name else Reader()
        return lambda spec: PlainBrain(reader)
    raise SystemExit("--model is claude-..., ollama:<name> or mlx[:<name>]")


def run(bid: str, model: str, minutes: float, tag: str = "") -> dict:
    from camr_engine.agentic.desk import Desk
    from camr_engine.agentic.plugins import browser_check
    from camr_engine.agentic.serve import serving
    from camr_engine.agentic.servers import Spec

    local = not model.startswith("claude-")
    if local:
        from camr_engine.app.measuring import active

        if active():
            raise SystemExit(f"a benchmark is measuring ({active().get('job')}): a local model would take its GPU")
    brief = briefs()[bid]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = f"{bid.lower()}-{re.sub(r'[^a-z0-9]+', '-', model.lower())}" + (f"-{tag}" if tag else "")
    folder = projects() / f"{name}-{stamp}"
    folder.mkdir(parents=True)
    desk_root = projects() / "_desk" / stamp
    desk = Desk(desk_root, brains=brains(model), keep_out=[])
    desk.set_workspace(str(folder))
    from camr_engine.agentic.plugins import BY_ID

    p = BY_ID["playwright"]
    desk.servers.add(Spec("playwright", p["command"], list(p["args"]), trusted=True))
    desk.servers.connect("playwright", folder)
    told = list(brief["told"])
    stop = threading.Event()

    def answer_asks():  # the app's part: the browser's report, and the person's answers
        while not stop.is_set():
            for a in desk.gate.waiting():
                if a["kind"] == "browser":
                    link = desk.servers.link("playwright")
                    got = browser_check(link, serving(desk.workspace).url(a["what"].get("path") or "index.html"))
                    got.update(loaded=True, scriptsRan=True, hasScripts=True)
                    desk.gate.answer(a["id"], json.dumps(got))
                elif a["kind"] == "question":
                    reply = "\n".join(told) if told else ""
                    if reply:
                        desk.gate.answer(a["id"], reply)
                    else:
                        desk.gate.decide(a["id"], False)
            time.sleep(0.3)

    t = threading.Thread(target=answer_asks, daemon=True)
    t.start()
    thread = desk.new_thread(f"{bid} {brief['title']}")["id"]
    # the facts go in with the request, as a person would type them: the parts that design and write the page have
    # no way to ask, and a build that never got the facts can only fill the page with placeholders
    request = brief["brief"] + ("\n\nWhat you need to know:\n" + "\n".join(f"- {t}" for t in told) if told else "")
    lead = desk.build(thread, request, memory=False)
    lead.thread_obj.join(minutes * 60)
    if lead.live:
        lead.stop()
        lead.thread_obj.join(60)
    stop.set()
    t.join(5)
    desk.servers.close()
    rules = None
    if (folder / "index.html").exists():
        link = playwright_link(folder)
        try:
            rules = brief_rules(link, serving(desk.workspace).url("index.html"), told)
        finally:
            link.close()
    out = {"brief": bid, "model": model, "tag": tag, "skills": os.environ.get("CAMR_SKILLS") or "shipped",
           "folder": str(folder), "state": lead.state, "seconds": lead.facts()["seconds"],
           "parts": [(x.role, x.target, x.state) for x in lead.plan.parts], "motion": motion.read_report(desk.workspace),
           "rules": rules}
    (folder / "report").mkdir(exist_ok=True)
    (folder / "report" / "run.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "motion"}, indent=1))
    print((folder / "REPORT.md").read_text() if (folder / "REPORT.md").exists() else "(no REPORT.md)")
    if rules:
        show_rules(rules)
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="mark a hand-made page by the motion rules in Chrome")
    c.add_argument("brief")
    c.add_argument("folder", type=Path)
    c.add_argument("--name")
    r = sub.add_parser("run", help="build a brief with a model through the lead")
    r.add_argument("brief")
    r.add_argument("--model", required=True)
    r.add_argument("--minutes", type=float, default=45)
    r.add_argument("--tag", default="", help="a label for the run's folder (e.g. cards-before)")
    sub.add_parser("list", help="the briefs in HARD.md")
    k = sub.add_parser("rules", help="the brief's own rules (countdown, told facts) on a page already built")
    k.add_argument("brief")
    k.add_argument("folder", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "list":
        for k, b in briefs().items():
            print(f"{k}: {b['title']}\n  {b['brief']}\n  rules: {len(b['rules'])}, told: {len(b['told'])}")
    elif a.cmd == "rules":
        from camr_engine.agentic.serve import close_all, serving

        link = playwright_link(a.folder.resolve())
        try:
            r = brief_rules(link, serving(Workspace(a.folder.resolve())).url("index.html"), briefs()[a.brief]["told"])
        finally:
            link.close()
            close_all()
        show_rules(r)
    elif a.cmd == "check":
        check(a.brief, a.folder.resolve(), a.name)
    else:
        run(a.brief, a.model, a.minutes, a.tag)


if __name__ == "__main__":
    main()
