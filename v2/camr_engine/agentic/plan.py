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
TEAM_FILES = ("BRIEF.md", "ARCHITECTURE.md", "PLAN.md", "REPORT.md")
_FILE = re.compile(r"(?<![\w/.-])((?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.(?:html|htm|css|js|mjs|json|svg|py|ts|txt))\b")
_CLASS = re.compile(r"\.([A-Za-z][\w-]*)\s*[{,:\s]")
STYLE_WORDS = re.compile(r"\b(colou?rs?|fonts?|typefaces?|bigger|smaller|spacing|padding|margins?|dark|light|"
                         r"background|layout|looks?|styles?|theme|rounded|shadows?|centred|centered|sticky|columns?|desktop|mobile|"
                         r"serif|sans-serif|bold|italic|underlined?|width|gap|align\w*|red|green|blue|yellow|orange|"
                         r"purple|pink|black|white|grey|gray|brown|gold|teal|navy|cream|beige)\b|#[0-9a-f]{3,6}\b", re.I)
NEW_ELEMENT = re.compile(r"\b(add|put|show)\b.*\b(button|box|field|input|form|toggle|checkbox|slider|picker)\b", re.I)
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
         ("write_file", "read_file", "read_shelf", "ask_user"), 4),
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


def _longest_gap(asks: list[float], end: float) -> float:
    """The longest time between the start, each question and the end."""
    marks = [0.0, *sorted(asks), end]
    return max(b - a for a, b in zip(marks, marks[1:]))


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


def change_targets(request: str, files: list[str]) -> list[tuple[str, str]]:
    """The files a change goes to, in order, each with why: a new control the page must show and the script must
    work goes to both; otherwise one file, as ``change_target`` picks it."""
    js = next((f for f in files if f.lower().endswith((".js", ".mjs"))), None)
    page = "index.html" if "index.html" in files else next((f for f in files if f.lower().endswith(".html")), None)
    m = NEW_ELEMENT.search(request)
    if m and js and page and not STYLE_WORDS.search(request):
        return [(page, f"the page must show the new {m.group(2).lower()}"),
                (js, f"the script must make the new {m.group(2).lower()} work")]
    return [change_target(request, files)]


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
    detail: str = ""  # what the part must fix, when the lead planned it from a test


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
        """The project's files, as the workspace lists them (no symlinks, no files of secrets, no dot-folders)."""
        out = []
        for f in self.desk.workspace.tree():
            rel = f["path"]
            if f["dir"] or f.get("secret") or rel in TEAM_FILES or any(x.startswith(".") for x in rel.split("/")):
                continue
            out.append(rel)
        return out[:200]

    def _first_plan(self) -> Plan:
        files = self._files()
        if files:  # a project that has files already: the request is a change to it
            targets = change_targets(self.request, files)
            plan = Plan(self.request, "change", [
                Part(f"p{i}", "change", f"Change {target}", target, "rule", why)
                for i, (target, why) in enumerate(targets, 1)])
            plan.decide("rule", "The project has files already, so this is a change. It goes to "
                        + "; then ".join(f"{t}: {why}" for t, why in targets) + ".")
            if any(f.lower().endswith((".html", ".htm")) for f in files):
                plan.parts.append(Part(f"p{len(targets) + 1}", "review", "Test the page and fix it", None, "rule",
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
        if self.checks >= CHECKS:
            return
        if self._fix_from_test():
            return
        musts = self.musts()
        if not musts:
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

    def _fix_from_test(self) -> bool:
        """The review's last page test still failing is evidence, and it outweighs the model's own reading: a rule
        plans a fix of the file the problems point at, with the problems, then another review."""
        review = next((p for p in reversed(self.plan.parts) if p.role == "review"), None)
        run = self.desk.runs.get(review.run) if review is not None and review.run else None
        last = run.last_test() if run is not None else None
        if not last or last["ok"]:
            return False
        self.checks += 1
        problems = last["text"].split("\n\nThe page as it is now")[0]
        files = self._files()
        js = next((f for f in files if f.lower().endswith((".js", ".mjs"))), None)
        script = js and re.search(r"pressing|script|TypeError|ReferenceError|\.js\b", problems)
        target = js if script else ("index.html" if "index.html" in files else (files[0] if files else "index.html"))
        self.plan.decide("rule", f"The page's last test still shows problems, so {target} gets a fix planned from "
                         "them (the test outweighs the model's own reading).")
        n = len(self.plan.parts)
        self.plan.parts.append(Part(f"p{n + 1}", "change", f"Fix what the page test found in {target}", target, "rule",
                                    "the last page test failed", detail=problems[:1500]))
        self.plan.parts.append(Part(f"p{n + 2}", "review", "Test the page again and fix it", None, "rule",
                                    "every change to a page is tested"))
        return True

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
            self._write_report()
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
        tools = list(role.tools)
        if part.role == "review":  # a connected browser plugin's few tools, which ask like any other call
            from camr_engine.agentic.plugins import review_tools

            tools += review_tools(self.desk.servers)
        persona = replace(coder, name=role.name, system=role.system, tools=tools)
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
        if part.target and part.role != "change" and not self._read(part.target).strip():
            return f"{part.target} was not written"
        if part.role == "change" and not run._made():
            return "nothing was changed"
        return ""

    # -- what each specialist reads

    def _read(self, rel: str, limit: int = SHOWN) -> str:
        """A project file through the workspace, which keeps to the project and leaves files of secrets alone."""
        from camr_engine.agentic.workspace import Outside

        try:
            text = self.desk.workspace.text(rel)[1]
        except (Outside, OSError):
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
        }[part.role] + (f"\n\nWhat the page test found:\n{part.detail}" if part.detail else "")

    def _first(self, part: Part) -> str:
        t = part.target
        if part.role == "change":
            return f"Read {t} with read_file first, then make only this change with edit_file. Keep everything else."
        if part.role == "review":
            return ""
        if t and t in self._files():
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
        if part.role == "review" and self.desk.servers.link("playwright") is not None:
            from camr_engine.agentic.serve import serving

            out.append("A real Chrome is connected (the browser_ tools). The page is at "
                       f"{serving(self.desk.workspace).url('index.html')}: open it there, never as a file.")
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

    # -- the report: what happened, from what was recorded (no model writes it)

    def facts(self) -> dict:
        """The build in numbers, from its runs' records."""
        asks, tests, steps = [], [], []
        for part in self.plan.parts:
            for rid in part.runs:
                run = self.desk.runs.get(rid)
                if run is None:
                    continue
                for t in list(run.turns):
                    at = round(float(t.get("at", self.started)) - self.started, 1)
                    if t.get("kind") == "model":
                        steps.append({"part": ROLES[part.role].name, "read": int(t.get("prompt_tokens") or 0),
                                      "wrote": int(t.get("written_tokens") or 0),
                                      "s": round(float(t.get("total_s") or 0), 1)})
                    elif t.get("kind") == "call" and t.get("tool") == "ask_user":
                        text = str(t.get("text") or "")
                        said = text.removeprefix("The user answered: ") if text.startswith("The user answered") else ""
                        asks.append({"at_s": at, "part": ROLES[part.role].name,
                                     "question": str((t.get("args") or {}).get("question", ""))[:300],
                                     "answer": said[:300], "asked": bool(t.get("ok")), "why": text[:200]})
                    elif t.get("kind") == "call" and t.get("tool") == "open_page" and not str(
                            t.get("text") or "").startswith("(the same as "):  # a repeat answered, not a test
                        report = str(t.get("text") or "").split("\n\nThe page as it is now")[0]
                        tests.append({"at_s": at, "part": ROLES[part.role].name, "ok": bool(t.get("ok")),
                                      "report": report[:1200]})
        end = (self.ended or time.time()) - self.started
        reached = [a for a in asks if a["asked"]]
        return {"seconds": round(end, 1), "asks": asks, "stops": len(reached), "tests": tests, "steps": len(steps),
                "first_ask_s": reached[0]["at_s"] if reached else None,
                "longest_alone_s": round(_longest_gap([a["at_s"] for a in reached], end), 1),
                "most_read": max((x["read"] for x in steps), default=0),
                "read": sum(x["read"] for x in steps), "wrote": sum(x["wrote"] for x in steps),
                "window": self.desk.window_tokens()}

    def report(self) -> str:
        f = self.facts()
        mins = lambda s: f"{int(s // 60)} min {int(s % 60)} s" if s >= 60 else f"{s:.0f} s"  # noqa: E731
        lines = ["# Build report", "", f"Request: {self.request}", "",
                 f"Model: {self._model()}", "",
                 "## In short", "",
                 f"- It worked for {mins(f['seconds'])} in {f['steps']} model steps, and ended {self.state}.",
                 (f"- It stopped for you {f['stops']} time{'s' if f['stops'] != 1 else ''}; the first after "
                  f"{mins(f['first_ask_s'])}. Its longest stretch alone was {mins(f['longest_alone_s'])}."
                  if f["stops"] else f"- It never stopped for you: {mins(f['seconds'])} alone."),
                 f"- The most one step read was {f['most_read']:,} tokens"
                 + (f" (the window was limited to {f['window']:,})." if f["window"] else "."),
                 f"- In all it read {f['read']:,} tokens and wrote {f['wrote']:,}.",
                 f"- {self.answer or self._summary()}", "", "## The parts", "",
                 "| Part | Who decided it | State | Time | Tries |", "|---|---|---|---|---|"]
        for p in self.plan.parts:
            lines.append(f"| {ROLES[p.role].name}: {p.title} | {p.by} | {p.state}{' (' + p.note + ')' if p.note else ''}"
                         f" | {mins(p.seconds)} | {p.tries} |")
        lines += ["", "## What it asked you", ""]
        lines += [f"- After {mins(a['at_s'])}, the {a['part'].lower()} asked: \"{a['question']}\" "
                  + (f"You said: \"{a['answer']}\"." if a["answer"] else "You left it out." if a.get("asked", True)
                     else f"It never reached you: {a['why']}") for a in f["asks"]] or [
            "- Nothing: every fact it needed was in memory or in the request."]
        lines += ["", "## Decisions", ""]
        lines += [f"- ({d['by']}) {d['text']}" for d in self.plan.decisions]
        lines += ["", "## Page tests", ""]
        merged = []
        for t in f["tests"]:
            if merged and merged[-1]["report"] == t["report"] and merged[-1]["part"] == t["part"]:
                merged[-1]["times"] += 1
                continue
            merged.append({**t, "times": 1})
        for t in merged:
            again = f" (the same result {t['times']} times)" if t["times"] > 1 else ""
            lines.append(f"- After {mins(t['at_s'])}, by the {t['part'].lower()}: "
                         f"{'passed' if t['ok'] else 'problems'}{again}.")
            if not t["ok"]:
                lines += ["  " + x for x in t["report"].splitlines()[:8]]
        if not f["tests"]:
            lines.append("- The page was not tested.")
        lines += ["", "Rules wrote the order of the parts, the retries and this report. The model wrote the brief, "
                  "chose the files, wrote every file and answered the checks marked (model)."]
        return "\n".join(lines) + "\n"

    def _model(self) -> str:
        for p in reversed(self.plan.parts):
            for rid in reversed(p.runs):
                run = self.desk.runs.get(rid)
                if run is not None:
                    return run.brain.label
        return "unknown"

    def _write_report(self) -> None:
        from camr_engine.agentic.workspace import Outside

        try:
            self.desk.workspace.write("REPORT.md", self.report())
        except (Outside, OSError):
            pass

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
        from camr_engine.agentic.workspace import Outside

        try:
            ws.write("PLAN.md", self.plan.markdown())  # atomic, never through a symlink, never outside the project
        except (Outside, OSError):
            pass
        try:
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
                "told": len(self.told), "model": run.brain.label if run is not None else self._model()}
