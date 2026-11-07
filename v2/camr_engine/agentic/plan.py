"""The lead: a request to make something is planned first, then built one part at a time, each part by a specialist.

A small model asked for a whole website in one go writes one long file, forgets half of what it was told and stops.
The lead splits the work the way a team would: a researcher writes the brief (BRIEF.md), an architect decides the files
and their structure (ARCHITECTURE.md), then one maker per file, then a reviewer tests the page in the browser and fixes
it. Each specialist is a run of its own (``camr_engine.agentic.loop.Run``) with a narrow prompt: its role, the method
for its part (a skill in ``curated/skills``), the brief, the architecture, and only the files it builds on. No prompt
carries the whole build, so the build goes on by itself once the first questions are answered.

What is decided where (the app says which, on the plan's card):
- by rule, here: the order of the roles, which role makes a file (by its kind: .css design, .html pages, .js behaviour,
  anything else code), trying a part once more when its file was not written, and which file a change goes to;
- by the model: the brief, the file structure (the lead makes one part per file ARCHITECTURE.md names), and every
  file's content.

The plan is kept as PLAN.md in the project, for the person to read, and as JSON beside the desk's threads.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from camr_engine.agentic.loop import WEBSITE

if TYPE_CHECKING:
    from camr_engine.agentic.desk import Desk

SKILLS = Path(__file__).resolve().parent.parent / "curated" / "skills"  # the methods, shipped with the engine
MAX_FILES = 6  # files one plan makes, at most
SHOWN = 9000  # characters of one file a specialist reads
TEAM_FILES = ("BRIEF.md", "ARCHITECTURE.md", "PLAN.md")
_FILE = re.compile(r"(?<![\w/.-])((?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.(?:html|htm|css|js|mjs|json|svg|py|ts|txt))\b")
_CLASS = re.compile(r"\.([A-Za-z][\w-]*)\s*[{,:\s]")
STYLE_WORDS = re.compile(r"\b(colou?rs?|fonts?|typefaces?|bigger|smaller|spacing|padding|margins?|dark|light|"
                         r"background|layout|looks?|styles?|theme|rounded|shadows?|centred|centered|red|green|blue|yellow|orange|"
                         r"purple|pink|black|white|grey|gray|brown|gold|teal|navy|cream|beige)\b|#[0-9a-f]{3,6}\b", re.I)
BEHAVIOUR_WORDS = re.compile(r"\b(clicks?|total|cart|basket|counts?|calculat\w*|submit|saves?|filters?|sort|"
                             r"remembers?|localStorage|quantity|quantities)\b", re.I)
ENDED = ("done", "stopped", "failed")
CHECKS = 2  # times the lead checks a reviewed page against the brief and plans what is missing
CHECK_SYSTEM = ("You check a web page against a list of things people must be able to do on it. For each numbered "
                "item, answer on its own line with the number, then yes or no, then a few words: yes only when the "
                "page has the elements and the script for it. Answer nothing else.")
_MUST_HEAD = re.compile(r"^#+\s*.*(must|able to|can do|people can|what people)", re.I)
_ANSWER = re.compile(r"^\W*(\d+)\W+(yes|no)\b\W*(.*)$", re.I)


@dataclass(frozen=True)
class Role:
    id: str
    name: str
    skill: str  # the method in curated/skills, or "" for none
    system: str
    tools: tuple[str, ...]
    steps: int  # steps its run may take


_WRITES = ("write_file", "edit_file", "read_file", "read_shelf")
ROLES = {r.id: r for r in [
    Role("research", "Researcher", "research",
         "You are the researcher on a small team building what the user asked for. You write the brief the team "
         "builds from: what it is, what people must be able to do, every fact exactly as told, and what is not known.",
         ("write_file", "read_file", "read_shelf"), 4),
    Role("architect", "Architect", "architecture",
         "You are the architect on a small team. From the brief you decide the files and the structure, and write it "
         "down in ARCHITECTURE.md for the designer, the builder and the behaviour agent. You write no code.",
         ("write_file", "read_file", "read_shelf"), 4),
    Role("design", "Designer", "design-system",
         "You are the designer on a small team. You write the stylesheet as a small design system, from the "
         "architecture and the brief.", _WRITES, 5),
    Role("builder", "Builder", "build-pages",
         "You are the builder on a small team. You write the HTML pages from the architecture, with the brief's facts "
         "copied exactly, using the stylesheet's classes.", _WRITES, 6),
    Role("behaviour", "Behaviour", "behaviour",
         "You write the JavaScript that makes the page work, as the architecture describes, for the elements the page "
         "already has.", _WRITES, 6),
    Role("coder", "Coder", "", "You write one file of the project, as the architecture describes.", _WRITES, 6),
    Role("review", "Reviewer", "review",
         "You are the reviewer on a small team. You test the page in the browser and fix what is wrong, without "
         "breaking what works.", ("open_page", "edit_file", "write_file", "read_file", "ask_user"), 10),
    Role("change", "Editor", "",
         "You make the change the user asked for, in the file you are given, and keep everything else as it is.",
         _WRITES, 6),
]}


def role_of(path: str) -> str:
    """Which role makes a file, by its kind. A rule, not the model's choice."""
    low = path.lower()
    if low.endswith(".css"):
        return "design"
    if low.endswith((".html", ".htm")):
        return "builder"
    if low.endswith((".js", ".mjs")):
        return "behaviour"
    return "coder"


def files_named(text: str) -> list[str]:
    """The files an architecture names, each once, in a sensible build order: styles, pages (index first), behaviour,
    then the rest. Never a path that climbs out of the project, nor the team's own notes."""
    found = []
    for f in _FILE.findall(text):
        if f in TEAM_FILES or ".." in f or f.startswith("/") or f in found:
            continue
        found.append(f)
    order = {"design": 0, "builder": 1, "behaviour": 2, "coder": 3}
    found.sort(key=lambda f: (order[role_of(f)], f.lower() != "index.html"))
    return found[:MAX_FILES]


def change_target(request: str, files: list[str]) -> tuple[str, str]:
    """The file a change goes to, and why: looks to the stylesheet, what happens on a click to the script, everything
    else to the page. A rule, so the reason is said plainly."""
    css = next((f for f in files if f.lower().endswith(".css")), None)
    js = next((f for f in files if f.lower().endswith((".js", ".mjs"))), None)
    page = "index.html" if "index.html" in files else next((f for f in files if f.lower().endswith(".html")), None)
    if css and STYLE_WORDS.search(request):
        return css, f"it is about how the page looks ({STYLE_WORDS.search(request).group(0)})"
    if js and BEHAVIOUR_WORDS.search(request):
        return js, f"it is about what the page does ({BEHAVIOUR_WORDS.search(request).group(0)})"
    if page:
        return page, "it is about what the page says or shows"
    return (files[0] if files else "index.html"), "it is the project's main file"


def classes_in(css: str) -> list[str]:
    return list(dict.fromkeys(_CLASS.findall(css)))[:80]


@dataclass
class Part:
    id: str
    role: str
    title: str
    target: str | None  # the file it makes or changes
    by: str  # "rule" or "model": who decided this part is needed
    why: str
    state: str = "todo"  # todo, running, done, failed, stopped
    run: str | None = None
    runs: list[str] = field(default_factory=list)
    tries: int = 0
    seconds: float = 0.0
    note: str = ""


@dataclass
class Plan:
    request: str
    kind: str  # "website", "code" or "change"
    parts: list[Part]
    decisions: list[dict] = field(default_factory=list)  # {"by": "rule" | "model", "text"}

    def decide(self, by: str, text: str) -> None:
        self.decisions.append({"by": by, "text": text, "at": time.time()})

    def markdown(self) -> str:
        mark = {"todo": "[ ]", "running": "[~]", "done": "[x]", "failed": "[!]", "stopped": "[-]"}
        lines = ["# Plan", "", f"Request: {self.request}", "", "## Parts", ""]
        for p in self.parts:
            lines.append(f"- {mark.get(p.state, '[ ]')} **{ROLES[p.role].name}**: {p.title}"
                         + (f" ({p.note})" if p.note else ""))
        lines += ["", "## Decisions", ""]
        lines += [f"- ({d['by']}) {d['text']}" for d in self.decisions]
        return "\n".join(lines) + "\n"

    def show(self) -> dict:
        return {"request": self.request, "kind": self.kind,
                "parts": [{**asdict(p), "name": ROLES[p.role].name} for p in self.parts],
                "decisions": list(self.decisions)}


class Lead:
    """Plans a request and runs its parts in order, in one thread of the desk. ``stop`` ends the part running and
    every part after it."""

    def __init__(self, desk: Desk, thread: str, request: str, *, memory: bool | None = None, lid: str = ""):
        self.desk, self.thread, self.request = desk, thread, " ".join(request.split())[:2000]
        self.memory = desk.settings["memory"] if memory is None else bool(memory)
        self.id = lid or f"lead-{thread}-{int(time.time() * 1000) % 10**9}"
        self.state = "planning"  # planning, building, done, stopped, failed
        self.error: str | None = None
        self.answer: str | None = None
        self.started, self.ended = time.time(), None
        self.cancel = threading.Event()
        self.told: list[str] = []  # what the person told about the request (found, or asked for), for every part
        self.current = None  # the part's run
        self.lock = threading.Lock()
        self.plan = self._first_plan()
        self.thread_obj: threading.Thread | None = None
        self.checks = 0

    # -- the plan

    def _files(self) -> list[str]:
        root = Path(self.desk.workspace.root)
        out = []
        for p in sorted(root.rglob("*")):
            rel = p.relative_to(root).as_posix()
            if p.is_file() and not any(s.startswith(".") for s in rel.split("/")) and rel not in TEAM_FILES:
                out.append(rel)
        return out[:200]

    def _first_plan(self) -> Plan:
        files = self._files()
        if files:  # a project that has files already: the request is a change to it
            target, why = change_target(self.request, files)
            plan = Plan(self.request, "change", [
                Part("p1", "change", f"Change {target}", target, "rule", why),
            ])
            plan.decide("rule", f"The project has files already, so this is a change. It goes to {target}: {why}.")
            if any(f.lower().endswith((".html", ".htm")) for f in files):
                plan.parts.append(Part("p2", "review", "Test the page and fix it", None, "rule",
                                       "every change to a page is tested"))
            return plan
        kind = "website" if WEBSITE.search(self.request) else "code"
        plan = Plan(self.request, kind, [
            Part("p1", "research", "Write the brief (BRIEF.md)", "BRIEF.md", "rule", "every build starts from a brief"),
            Part("p2", "architect", "Decide the files and structure (ARCHITECTURE.md)", "ARCHITECTURE.md", "rule",
                 "the files are decided before any is written"),
        ])
        plan.decide("rule", f"An empty project: plan first, then build ({kind}).")
        return plan

    def _after_architecture(self) -> None:
        """One part per file the architect named (the model's decision), in build order; for a website, index.html and
        a stylesheet are always among them (a rule), and a review comes last."""
        arch = self._read("ARCHITECTURE.md")
        named = files_named(arch)
        if named:
            self.plan.decide("model", "The architect named the files: " + ", ".join(named) + ".")
        if self.plan.kind == "website":
            if not any(f.lower().endswith((".html", ".htm")) for f in named):
                named.insert(0, "index.html")
                self.plan.decide("rule", "A website needs index.html, which the architecture did not name: added.")
            if not any(f.lower().endswith(".css") for f in named):
                named.insert(0, "style.css")
                self.plan.decide("rule", "A website gets a stylesheet, which the architecture did not name: added.")
        elif not named:
            self.plan.decide("rule", "The architecture named no file to make, so nothing more is planned.")
        n = len(self.plan.parts)
        for f in files_named("\n".join(named)):
            n += 1
            role = role_of(f)
            self.plan.parts.append(Part(f"p{n}", role, f"Write {f}", f, "model", "the architecture names it"))
        if self.plan.kind == "website":
            n += 1
            self.plan.parts.append(Part(f"p{n}", "review", "Test the page and fix it", None, "rule",
                                        "every page is tested before it is shown as done"))

    def musts(self) -> list[str]:
        """What people must be able to do, as the brief lists it."""
        out, inside = [], False
        for line in self._read("BRIEF.md").splitlines():
            if line.lstrip().startswith("#"):
                inside = bool(_MUST_HEAD.match(line.strip()))
                continue
            item = line.strip().lstrip("-*0123456789.) ").strip()
            if inside and item:
                out.append(item[:200])
        return out[:8]

    def _check(self) -> None:
        """The lead's own decision, by the model: does the page do each thing the brief says people must be able to
        do? Each "no" becomes a change part, then the page is reviewed again. At most CHECKS times."""
        musts = self.musts()
        if self.checks >= CHECKS or not musts:
            return
        self.checks += 1
        page = self._read("index.html", 7000)
        script = self._read("app.js", 4000)
        user = ("Things people must be able to do:\n" + "\n".join(f"{i}. {m}" for i, m in enumerate(musts, 1))
                + "\n\nThe page, index.html:\n" + page.replace("<", "‹").replace(">", "›")
                + ("\n\nIts script, app.js:\n" + script if script else "")
                + "\n\nFor each numbered item: the number, yes or no, a few words.")
        from camr_engine.agentic.brain import Prompt

        coder = self.desk.personas.get("coder")
        brain = self.desk.brain_for(replace(coder, name="Lead", system=CHECK_SYSTEM, tools=[]), self.thread,
                                    self.memory)
        with self.desk.model_lock:
            thought = brain.think(Prompt(CHECK_SYSTEM, user, [], ask=self.request, max_tokens=200,
                                         tags={"agent": "lead", "check": self.checks}))
        missing, read = [], set()
        for line in thought.text.splitlines():
            m = _ANSWER.match(line.strip())
            if not m or not 0 < int(m.group(1)) <= len(musts):
                continue
            read.add(int(m.group(1)))
            if m.group(2).lower() == "no":
                missing.append(musts[int(m.group(1)) - 1])
        missing = list(dict.fromkeys(missing))
        if not read:
            self.plan.decide("model", "Checked the page against the brief, but the answer could not be read; "
                             "nothing was added.")
            return
        if not missing:
            self.plan.decide("model", f"Checked the page against the brief's {len(musts)} must-dos: all there.")
            return
        self.plan.decide("model", "Checked the page against the brief: it does not yet let people "
                         + "; ".join(missing) + ". Planned a change for each.")
        files = self._files()
        n = len(self.plan.parts)
        for item in missing:
            n += 1
            target, why = change_target(item, files)
            self.plan.parts.append(Part(f"p{n}", "change", f"Make the page let people {item[:80]}", target, "model",
                                        f"the check found it missing; {target} because {why}"))
        n += 1
        self.plan.parts.append(Part(f"p{n}", "review", "Test the page again and fix it", None, "rule",
                                    "every change to a page is tested"))

    # -- running

    def start(self) -> Lead:
        self.thread_obj = threading.Thread(target=self._go, name=self.id, daemon=True)
        self.thread_obj.start()
        return self

    def stop(self) -> None:
        self.cancel.set()
        run = self.current
        if run is not None:
            run.stop()

    @property
    def live(self) -> bool:
        return self.state not in ENDED

    def _go(self) -> None:
        self._save()
        try:
            self.state = "building"
            if self.plan.kind == "change" and self.memory and self.desk.told is not None:
                # what the person decided before reaches the change as data, not as the conversation re-read
                self.told = list(self.desk.told(self.request))[:8]
            i = 0
            while i < len(self.plan.parts) and not self.cancel.is_set():
                part = self.plan.parts[i]
                self._do(part, last=i == len(self.plan.parts) - 1 and part.role != "architect")
                self._save()
                if part.role == "architect" and part.state == "done":
                    self._after_architecture()
                    self._save()
                if part.role == "review" and self.plan.kind == "website" and not self.cancel.is_set():
                    self._check()
                    self._save()
                i += 1
            if self.cancel.is_set():
                for p in self.plan.parts:
                    if p.state in ("todo", "running"):
                        p.state = "stopped"
                self.state = "stopped"
            else:
                self.state = "done"
            self.answer = self._summary()
        except Exception as e:  # noqa: BLE001 (shown on the card)
            self.error = f"{type(e).__name__}: {e}"[:600]
            self.state = "failed"
        finally:
            self.ended = time.time()
            self.current = None
            self._save()

    def _do(self, part: Part, *, last: bool) -> None:
        role = ROLES[part.role]
        coder = self.desk.personas.get("coder")
        persona = replace(coder, name=role.name, system=role.system, tools=list(role.tools))
        task = self._task(part)
        for attempt in (1, 2):
            if self.cancel.is_set():
                part.state = "stopped"
                return
            part.state, part.tries = "running", attempt
            self._save()
            t0 = time.time()
            run = self.desk.start(self.thread, task, memory=self.memory, persona=persona, window=True,
                                  max_steps=role.steps, context=self._context(part), request=self.request,
                                  opts=self._opts(part, last=last))
            part.run = run.id
            part.runs.append(run.id)
            self.current = run
            while run.thread is not None and run.thread.is_alive():
                run.thread.join(0.25)
                if self.cancel.is_set():
                    run.stop()
            part.seconds += time.time() - t0
            if part.role == "research":
                self.told = list(run.told_notes)
            if self.cancel.is_set():
                part.state = "stopped"
                return
            why = self._not_done(part, run)
            if not why:
                part.state, part.note = "done", ""
                return
            part.note = why
            if attempt == 1 and part.target and run.state != "failed":
                self.plan.decide("rule", f"{part.title}: {why}, so it is tried once more.")
                task = (f"{task}\n\nThe last try did not finish: {why}. " + (
                    f"Make the change in {part.target} now with edit_file." if part.role == "change" else
                    f"Write {part.target} now with write_file, whole."))
                continue
            break
        part.state = "failed"
        self.plan.decide("rule", f"{part.title}: {part.note}. The build goes on without it.")

    def _not_done(self, part: Part, run) -> str:
        """Why a part is not done, or "" when it is."""
        if run.state == "failed":
            return f"its run failed ({(run.error or '')[:120]})"
        if part.target and part.role != "change":
            f = Path(self.desk.workspace.root) / part.target
            if not f.is_file() or not f.read_text(errors="replace").strip():
                return f"{part.target} was not written"
        if part.role == "change" and not run._made():
            return "nothing was changed"
        return ""

    # -- what each specialist reads

    def _read(self, rel: str, limit: int = SHOWN) -> str:
        f = Path(self.desk.workspace.root) / rel
        try:
            text = f.read_text(errors="replace") if f.is_file() else ""
        except OSError:
            return ""
        return text if len(text) <= limit else text[:limit] + f"\n… {len(text) - limit:,} more characters"

    def _task(self, part: Part) -> str:
        r, t = self.request, part.target
        return {
            "research": f'Write BRIEF.md for this request: "{r}"',
            "architect": f'Write ARCHITECTURE.md: the files and the structure for "{r}", from the brief. Write no code.',
            "design": f'Write {t}, the stylesheet, as the architecture says. The request: "{r}"',
            "builder": f'Write {t}, as the architecture says, with the brief\'s facts copied exactly. The request: "{r}"',
            "behaviour": f'Write {t}, the behaviour the architecture describes, for the elements in the page. '
                         f'The request: "{r}"',
            "coder": f'Write {t}, as the architecture says. The request: "{r}"',
            "review": f'Test the page and fix what its test reports. The request: "{r}"',
            "change": f'In {t}: {r}' if self.plan.kind == "change" else
                      f'In {t}: {part.title[0].lower() + part.title[1:]}. The request: "{r}"',
        }[part.role]

    def _first(self, part: Part) -> str:
        t = part.target
        if part.role == "change":
            return f"Read {t} with read_file first, then make only this change with edit_file. Keep everything else."
        if part.role == "review":
            return ""
        if t and (Path(self.desk.workspace.root) / t).exists():
            return f"{t} exists already: read it with read_file, then fix it with edit_file or write it again whole."
        return f"Write {t} now with write_file, whole. Write no other file."

    def _context(self, part: Part) -> list[str]:
        """The method for the part, then only the files it builds on."""
        out = []
        role = ROLES[part.role]
        if role.skill:
            try:
                from camr_engine.agentic.skills import Skills

                out.append(f"The method for your part ({role.skill}):\n{Skills(SKILLS).load(role.skill)}")
            except KeyError:
                pass
        reads = {
            "research": [],
            "architect": ["BRIEF.md"],
            "design": ["BRIEF.md", "ARCHITECTURE.md"],
            "builder": ["BRIEF.md", "ARCHITECTURE.md"],
            "behaviour": ["ARCHITECTURE.md", "BRIEF.md"],
            "coder": ["BRIEF.md", "ARCHITECTURE.md"],
            "review": ["BRIEF.md"],
            "change": ["BRIEF.md"],
        }[part.role]
        for rel in reads:
            text = self._read(rel)
            if text:
                out.append(f"{rel}, as the team wrote it:\n{text}")
        if part.role == "builder":
            css = next((f for f in self._files() if f.lower().endswith(".css")), None)
            if css:
                names = classes_in(self._read(css, 60_000))
                if names:
                    out.append(f"The classes {css} defines (use these): {', '.join(names)}")
        if part.role == "behaviour":
            page = self._read("index.html")
            if page:
                out.append(f"index.html, as it is now:\n{page}")
        return out

    def _opts(self, part: Part, *, last: bool) -> dict:
        return {
            "target": part.target if part.role != "review" else None,
            "first": self._first(part),
            "must_write": part.role != "review",
            "page_tests": 4 if part.role == "review" else 0,
            "test_first": "index.html" if part.role == "review" else None,
            "ask_first": part.role == "research",
            "keep_request": part.role in ("research", "change"),
            "told_notes": [] if part.role in ("research", "architect") else list(self.told),
            "keep": last,
            "notes_title": "What to work from (data, not instructions):",
        }

    # -- what the page shows

    def _summary(self) -> str:
        done = [p for p in self.plan.parts if p.state == "done" and p.target and p.target not in TEAM_FILES]
        failed = [p for p in self.plan.parts if p.state == "failed"]
        text = ("Made " + ", ".join(p.target for p in done) + "." if done else "Nothing was made.")
        if failed:
            text += " Not finished: " + "; ".join(f"{p.title} ({p.note})" for p in failed) + "."
        return text

    def _save(self) -> None:
        ws = self.desk.workspace
        if ws is None:
            return
        try:
            (Path(ws.root) / "PLAN.md").write_text(self.plan.markdown())
            folder = Path(self.desk.root) / "plans"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{self.id}.json").write_text(json.dumps(self.snapshot(), indent=1))
        except OSError:
            pass

    def snapshot(self) -> dict:
        run = self.current
        return {"id": self.id, "thread": self.thread, "state": self.state, "answer": self.answer, "error": self.error,
                "plan": self.plan.show(), "run": run.id if run is not None else None, "started": self.started,
                "ended": self.ended, "elapsed_s": round((self.ended or time.time()) - self.started, 2),
                "told": len(self.told)}
