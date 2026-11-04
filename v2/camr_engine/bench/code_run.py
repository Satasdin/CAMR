"""Code: café websites from notes kept in memory.

Each task tells memory a few notes first, one remembered moment each: a café's name, its brand colours as hex, three
menu items with prices in KES, its opening hours, its address, and a rule ("prices always show KES and two
decimals"). Then the Code agent (camr_engine.agentic.loop.Run, as the Code screen runs it, persona Coder) is asked,
in a fresh empty workspace: "Build a one-page website for our café: index.html and style.css."

Four ways to run each café, the same model, the same task, the same tools:

- ``off``: the plain model with no memory (PlainBrain), and the notes are not given. It cannot know the café.
- ``prompt``: the plain model with the notes pasted in the prompt, under "What the user told you earlier:": the
  ceiling, what the model does when it is handed the notes.
- ``memory``: the engine (EngineBrain over a reach session, as the Code screen opens it), the notes kept on the
  Coding shelf the day before the task.
- ``noisy``: the engine, the notes told ten days before the task among unrelated noise (Long Haul events: a food
  business's chats, meetings and code, about NOISE_TOKENS tokens over nine days), all on the Coding shelf, so memory
  has to find them.

Each site is graded by rule, with no model (``grade``): both files exist, the HTML parses, it links style.css, the
café's name, all three items, every price as "KES n.00", the opening and closing times, the address, both brand
colours in the CSS, and nothing invented (no price that is not in the notes, and no menu word from a fixed list that
the notes do not hold).

Shell commands are refused at once (the sites need only file writes): ``Refuse`` is a gate that denies every ask,
and the record counts the asks. A run has at most ``--max-steps`` steps (12, as the Code screen).

The record goes to records/bench/<YYYY-MM-DD>/<HHMMSS>-code-cafe-code-<model>.json, written again after every site:
each run's rules, steps, answer, files and what memory put on the desk, and per mode the rules passed per site. Each
site is kept under work/code_run/.

    python -m camr_engine.bench.code_run --model qwen3-4b
    python -m camr_engine.bench.code_run --model qwen3-8b --seeds 1 2 3 --modes off memory
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import random
import re
import shutil
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Sequence

from camr_engine.agentic.brain import CLOSEST, EngineBrain, PlainBrain
from camr_engine.agentic.gate import Ask, Gate
from camr_engine.agentic.loop import STEP_TOKENS, Run
from camr_engine.agentic.personas import BUILT_IN
from camr_engine.agentic.tools import Toolbox
from camr_engine.agentic.workspace import Workspace
from camr_engine.bench.contender import RECORDS, environment, record_path, write_record
from camr_engine.bench.local import MODELS, WORK, Loader, _let_go

TASK = "Build a one-page website for our café: index.html and style.css."
MODES = ("off", "prompt", "memory", "noisy")
SEEDS = (1, 2, 3, 4, 5)
MAX_STEPS = 12
NOISE_TOKENS = 6000
NOISE_DAYS = 9
START = dt.date(2026, 10, 20)  # the noisy notes' first day; the task is asked TASK_DAY days later
TASK_DAY = 10
CODING = "project:coding"  # the Coding shelf (camr_engine.shelves)
PROMPT_TITLE = "What the user told you earlier:"
RULES = ("files", "parses", "links_css", "name", "items", "prices", "hours", "address", "colours", "nothing_invented")

NAMES = ("Kahawa Corner", "Mvule Café", "Baobab Bean", "Jacaranda Cup", "Tamu Roastery", "Pwani Brew", "Savanna Sip",
         "Kilele Coffee House")
COLOURS = (("#1F4D3A", "#F4E9D8"), ("#7A2E1D", "#F2C14E"), ("#2B3A67", "#E8DCC4"), ("#4A2C2A", "#D9A441"),
           ("#0E6E6E", "#FCEFD4"), ("#5B3256", "#F7D6BF"), ("#33503A", "#E9C46A"), ("#8C3B2E", "#EFE6DD"))
ITEMS = ("Masala Chai", "Cardamom Latte", "Banana Bread", "Dawa Tea", "Cinnamon Roll", "Mango Smoothie",
         "Avocado Toast", "Coconut Mandazi", "Iced Hibiscus", "Kenya AA Pour-Over", "Sweet Potato Muffin",
         "Honey Ginger Tea")
STREETS = ("Moi Avenue, Nairobi", "Ngong Road, Nairobi", "Kenyatta Avenue, Nakuru", "Oginga Odinga Street, Kisumu",
           "Nyerere Road, Mombasa", "Kimathi Street, Nyeri", "Biashara Street, Naivasha", "Tom Mboya Street, Thika")
DAYS = ("Monday to Saturday", "Monday to Friday", "every day", "Tuesday to Sunday")
# menu words a café site might invent; one counts only when the café's own notes do not hold it
MENU_WORDS = ("latte", "cappuccino", "espresso", "americano", "mocha", "macchiato", "flat white", "croissant", "muffin",
              "scone", "bagel", "sandwich", "cake", "cookie", "brownie", "pancake", "waffle", "smoothie", "juice",
              "samosa", "mandazi", "chapati", "toast", "omelette", "burger", "pizza", "salad", "roll", "chai",
              "hibiscus", "pour-over", "bread")


def cafe(seed: int) -> dict:
    """One café, fixed by its seed."""
    r = random.Random(f"code-cafe-{seed}")
    name = r.choice(NAMES)
    items = r.sample(ITEMS, 3)
    prices = sorted(r.sample(range(150, 900, 10), 3))
    opens, closes = r.choice((6, 7, 8)), r.choice((17, 18, 19, 20, 21))
    number, street = r.randint(2, 180), r.choice(STREETS)
    road, town = street.split(", ")
    return {"seed": seed, "name": name, "colours": list(r.choice(COLOURS)),
            "items": [{"name": n, "price": p} for n, p in zip(items, prices)], "days": r.choice(DAYS),
            "opens": opens, "closes": closes, "street": f"{number} {road}", "town": town}


def clock(hour: int) -> str:
    """7 -> "7:00 am", 19 -> "7:00 pm"."""
    return f"{(hour - 1) % 12 + 1}:00 {'am' if hour < 12 else 'pm'}"


def notes(c: dict) -> list[str]:
    """What the user tells memory about the café, one moment each."""
    menu = ", ".join(f"{x['name']} KES {x['price']}" for x in c["items"])
    light, dark = c["colours"][1], c["colours"][0]
    return [f"Our café is called {c['name']}; I want a website for it soon.",
            f"{c['name']} brand colours: the main colour is {dark} and the background colour is {light}.",
            f"The {c['name']} menu has three items: {menu}.",
            f"{c['name']} opening hours: {c['days']}, {clock(c['opens'])} to {clock(c['closes'])}.",
            f"{c['name']} address: {c['street']}, {c['town']}.",
            "Rule for the café website: prices always show KES and two decimals."]


# -- grading, by rule

class _Page(HTMLParser):
    """The page's visible text, its tags, and whether every closing tag closes one that is open."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.tags: list[tuple[str, dict]] = []
        self.open: list[str] = []
        self.stray = 0
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, {k: v or "" for k, v in attrs}))
        if tag in ("script", "style"):
            self._skip += 1
        if tag not in self.VOID:
            self.open.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, {k: v or "" for k, v in attrs}))

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        if tag in self.VOID:
            return
        if tag in self.open:  # an unclosed <p> or <li> before it is let go, as a browser does
            while self.open and self.open.pop() != tag:
                pass
        else:
            self.stray += 1

    def handle_data(self, data):
        if not self._skip:
            self.text.append(data)


_MONEY = re.compile(r"(?:KES|KSh|Ksh|Kshs|KSH)\.?\s*([\d,]+(?:\.\d+)?)|\b(\d{2,5}\.\d{2})\b")
_TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?(?![\d:])", re.I)


def _flat(text: str) -> str:
    return " ".join(html.unescape(text).replace(" ", " ").split())


def times(text: str) -> set[int]:
    """Every time of day written in the text, as minutes after midnight: "7:00 am", "7am", "19:00", "7.00 pm"."""
    out = set()
    for m in _TIME.finditer(text.replace(".00", ":00")):
        h, mins, half = int(m.group(1)), m.group(2), (m.group(3) or "").lower().replace(".", "")
        if mins is None and not half:
            continue  # a bare number is not a time
        if half == "pm" and h < 12:
            h += 12
        elif half == "am" and h == 12:
            h = 0
        if 0 <= h < 24:
            out.add(h * 60 + int(mins or 0))
    return out


def amounts(text: str) -> set[float]:
    out = set()
    for m in _MONEY.finditer(text):
        raw = (m.group(1) or m.group(2) or "").replace(",", "").rstrip(".")
        try:
            out.add(float(raw))
        except ValueError:
            pass
    return out


def grade(site: Path, c: dict) -> dict:
    """The site's rules, each True or False, with what was missing or invented."""
    page, css = Path(site) / "index.html", Path(site) / "style.css"
    rules = dict.fromkeys(RULES, False)
    why: dict[str, list] = {}
    rules["files"] = page.is_file() and css.is_file()
    if not page.is_file():
        return {"rules": rules, "passed": 0, "of": len(RULES), "why": {"files": ["no index.html"]}}
    source = page.read_text(errors="replace")
    style = css.read_text(errors="replace") if css.is_file() else ""
    p = _Page()
    try:
        p.feed(source)
        p.close()
        parsed = True
    except Exception:  # noqa: BLE001 (a page the parser cannot read fails the rule)
        parsed = False
    names = {t for t, _ in p.tags}
    rules["parses"] = parsed and {"html", "body"} <= names and p.stray == 0
    rules["links_css"] = any(t == "link" and a.get("href", "").strip().lstrip("./") == "style.css" for t, a in p.tags)
    text = _flat(" ".join(p.text))
    low = text.lower()
    rules["name"] = c["name"].lower() in low
    missing = [x["name"] for x in c["items"] if x["name"].lower() not in low]
    rules["items"] = not missing
    want = {x["price"]: re.compile(rf"KES\s?{x['price']}\.00\b") for x in c["items"]}
    bad = [f"KES {n}.00" for n, rx in want.items() if not rx.search(text)]
    rules["prices"] = not bad
    seen = times(text)
    rules["hours"] = {c["opens"] * 60, c["closes"] * 60} <= seen
    rules["address"] = c["street"].lower() in low and c["town"].lower() in low
    colours = [h for h in c["colours"] if h.lower() not in style.lower()]
    rules["colours"] = not colours
    told = " ".join(notes(c)).lower()
    extra = sorted(a for a in amounts(text) if a not in {float(x["price"]) for x in c["items"]})
    words = sorted(w for w in MENU_WORDS if re.search(rf"\b{re.escape(w)}s?\b", low) and w not in told)
    rules["nothing_invented"] = not extra and not words
    why.update({k: v for k, v in (("items", missing), ("prices", bad), ("colours", colours),
                                  ("invented", [*(f"{a:g}" for a in extra), *words])) if v})
    if not rules["hours"]:
        why["hours"] = sorted(seen)[:12]
    return {"rules": rules, "passed": sum(rules.values()), "of": len(RULES), "why": why}


# -- running

class Refuse(Gate):
    """A gate that denies every ask at once: the sites need only file writes."""

    def __init__(self):
        super().__init__(wait_s=0)
        self.asked = 0

    def ask(self, kind: str, what: dict, *, owner: str, label: str = "", cancel=None, wait_s=None) -> Ask:
        self.asked += 1
        a = Ask(f"refused-{self.asked}", kind, dict(what), owner, label)
        self._settle(a, "denied")
        return a


def noise_lines(tokens: int, seed: int) -> list[str]:
    """Long Haul events no probe needs, about ``tokens`` tokens of them (camr_engine.bench.suite_run's noise)."""
    from camr_engine.bench.ollama_run import HAUL
    from camr_engine.bench.suite_run import noise, noise_pool

    return noise(noise_pool(str(HAUL)), tokens, seed, "code-cafe")


def told(c: dict, mode: str, noise_tokens: int = NOISE_TOKENS) -> list[tuple[dt.date, str]]:
    """What memory is told before the task, as (date, text), oldest first."""
    task_date = START + dt.timedelta(days=TASK_DAY)
    said = notes(c)
    if mode == "memory":
        return [(task_date - dt.timedelta(days=1), n) for n in said]
    if mode != "noisy":
        return []
    lines = noise_lines(noise_tokens, c["seed"])
    per = max(1, -(-len(lines) // NOISE_DAYS))
    days = [lines[i:i + per] for i in range(0, len(lines), per)]
    out: list[tuple[dt.date, str]] = []
    for d, chunk in enumerate(days):
        date = START + dt.timedelta(days=d)
        if d < 2:  # the notes go in among the first two days' noise
            mine = said[:3] if d == 0 else said[3:]
            step = max(1, len(chunk) // (len(mine) + 1))
            for k, n in enumerate(mine):
                chunk.insert(min(len(chunk), (k + 1) * step + k), n)
        out += [(date, x) for x in chunk]
    return out


def open_brain(mode: str, reader, embedder, root: Path, c: dict, today: dt.date):
    if mode in ("off", "prompt"):
        return PlainBrain(reader)
    from camr_engine.reach import Session

    s = Session(reader, embedder, root=root, name="cafe-thread", project=f"cafe-{c['seed']}",
                agent="coder", reads=("session", "project", "global", CODING), writes=CODING, tiers={}, metrics=True,
                closest=CLOSEST)
    return EngineBrain(s, today=lambda: today, day=lambda d: (d - START).days)


def run_one(c: dict, mode: str, reader, embedder, folder: Path, *, max_steps: int = MAX_STEPS,
            step_tokens: int = STEP_TOKENS, noise_tokens: int = NOISE_TOKENS,
            progress: Callable[[str], None] = print) -> dict:
    """One café in one mode, in ``folder`` (made fresh): its site in ``folder/site``, its memory in
    ``folder/memory``."""
    if folder.exists():
        shutil.rmtree(folder)
    site = folder / "site"
    site.mkdir(parents=True)
    today = START + dt.timedelta(days=TASK_DAY)
    brain = open_brain(mode, reader, embedder, folder / "memory", c, today)
    t = time.perf_counter()
    said = told(c, mode, noise_tokens)
    for date, text in said:
        brain.session.remember(f"[{date.isoformat()}] {text}", (date - START).days, to=CODING)
    tell_s = time.perf_counter() - t
    gate = Refuse()
    run = Run(f"cafe-{c['seed']}-{mode}", TASK, brain=brain, tools=Toolbox(Workspace(site), gate),
              persona=BUILT_IN[0], gate=gate, label="café", workspace=site.name,
              notes=notes(c) if mode == "prompt" else None, notes_title=PROMPT_TITLE, max_steps=max_steps,
              step_tokens=step_tokens, keep=False)
    t = time.perf_counter()
    try:
        run.execute()
    finally:
        brain.close()
        _let_go()
    run_s = time.perf_counter() - t
    g = grade(site, c)
    steps = [x for x in run.turns if x["kind"] == "model"]
    out = {"seed": c["seed"], "cafe": c["name"], "mode": mode, **g, "state": run.state, "steps": run.steps,
           "answer": (run.answer or "")[:600], "error": run.error, "shell_refused": gate.asked,
           "calls": [x.get("tool") for x in run.turns if x["kind"] == "call"],
           "failed_calls": sum(1 for x in run.turns if x["kind"] == "call" and not x.get("ok")),
           "trail": [_trail(x) for x in run.turns[1:]],
           "files": sorted(p.name for p in site.iterdir()), "tokens": run.tokens, "told": len(said),
           "tell_s": round(tell_s, 2), "run_s": round(run_s, 2),
           "desk": [{"step": x["step"], **{k: (x.get("memory") or {}).get(k) for k in ("reach", "room", "tier",
                                                                                       "closest", "used")}}
                    for x in steps if x.get("memory")]}
    progress(f"{c['name']:<22} {mode:<7} {g['passed']}/{g['of']}  steps {run.steps}  {run_s:5.1f} s  "
             f"{run.state}  {g['why'] or ''}")
    return out


def _trail(turn: dict) -> dict:
    """A turn, short, for reading back why a run went as it did."""
    if turn["kind"] == "call":
        return {"call": turn.get("tool"), "args": str(turn.get("args"))[:160], "ok": turn.get("ok"),
                "result": str(turn.get("text") or turn.get("result") or "")[:200]}
    return {turn["kind"]: str(turn.get("text") or "")[:300]}


def table(results: Sequence[dict]) -> dict:
    """Per mode: rules passed per site (mean), sites with every rule, and each rule's count."""
    out = {}
    for mode in dict.fromkeys(r["mode"] for r in results):
        rs = [r for r in results if r["mode"] == mode]
        out[mode] = {"sites": len(rs), "rules_mean": round(sum(r["passed"] for r in rs) / len(rs), 2),
                     "of": len(RULES), "complete": sum(r["passed"] == r["of"] for r in rs),
                     "per_rule": {k: sum(r["rules"][k] for r in rs) for k in RULES},
                     "per_site": {r["cafe"]: r["passed"] for r in rs},
                     "steps_mean": round(sum(r["steps"] for r in rs) / len(rs), 2)}
    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m camr_engine.bench.code_run")
    ap.add_argument("--model", default="qwen3-4b", choices=list(MODELS))
    ap.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    ap.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    ap.add_argument("--max-steps", type=int, default=MAX_STEPS)
    ap.add_argument("--step-tokens", type=int, default=STEP_TOKENS)
    ap.add_argument("--noise-tokens", type=int, default=NOISE_TOKENS)
    ap.add_argument("--work", type=Path, default=WORK / "code_run")
    ap.add_argument("--records", type=Path, default=RECORDS)
    a = ap.parse_args(argv)
    started = dt.datetime.now()
    name = f"code:{a.model}"
    path = record_path("code-cafe", name, started, a.records)
    work = a.work / f"{a.model}-{started:%Y%m%d-%H%M%S}"
    loader = Loader()
    reader, embedder = loader.reader(MODELS[a.model]), loader.embedder()
    record = {"task": "code-cafe", "contender": name, "model": MODELS[a.model], "started": started.isoformat(),
              "settings": {"task": TASK, "seeds": a.seeds, "modes": a.modes, "max_steps": a.max_steps,
                           "step_tokens": a.step_tokens, "noise_tokens": a.noise_tokens, "noise_days": NOISE_DAYS,
                           "task_day": TASK_DAY, "persona": BUILT_IN[0].id, "shelf": CODING, "shell": "refused",
                           "rules": list(RULES), "work": str(work)},
              "cafes": [cafe(s) for s in a.seeds], "results": [], "environment": environment()}
    for seed in a.seeds:
        c = cafe(seed)
        for mode in a.modes:
            record["results"].append(run_one(c, mode, reader, embedder, work / f"{seed}-{mode}",
                                             max_steps=a.max_steps, step_tokens=a.step_tokens,
                                             noise_tokens=a.noise_tokens))
            record["summary"] = table(record["results"])
            write_record(record, path)
    record["complete"] = True
    record["finished"] = dt.datetime.now().isoformat()
    write_record(record, path)
    for mode, s in record["summary"].items():
        print(f"{mode:<7} {s['rules_mean']}/{s['of']} rules per site, {s['complete']}/{s['sites']} complete")
    print(path)
    return 0


if __name__ == "__main__":
    from camr_engine.app.measuring import measuring

    with measuring("code_run"):  # the app pauses its views and loads nothing while this measures
        raise SystemExit(main())
