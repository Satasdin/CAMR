"""Benchmarks F and G (DECISIONS.md, E-74), through the real app engine and its real chat route, with a scratch memory.

  keeping   about 650 scripted messages told as a person would: facts, changes, repeats, questions and requests.
            Were the right ones kept, changes caught, shelves right? Then questions, on six shelves and on one.
  workflows writing, study, errands, code and photos: 30 rule-graded tasks each, memory on and memory off.

All names and values come from one seeded generator, so every answer is known. Run from v2.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import random
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections import Counter
from pathlib import Path

MODEL = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
SHELVES = [("Writing", "How you write: your style, words you use and avoid, how you sign off, letters, drafts and emails."),
           ("Study", "Studying: courses, lectures, slides, exams, revision, topics you keep getting wrong.")]
FIRST = ("Asha Baraka Chebet Dalmas Esther Faith Gitonga Halima Imani Jomo Kerubo Lumumba Makena Nia Omondi Pendo Rehema Sifa "
         "Tumaini Wafula Zawadi Akinyi Bahati Daudi Ekesa Furaha Githinji Hadija Ivy Juma Kamau Lilian Mutua Nekesa Okoth "
         "Pamela Ruth Salim Tabitha Vera Wanjala Yusuf Zuri Amani Beatrice Cynthia Dennis Eunice").split()
SURNAMES = ("Achola Barasa Cherono Danso Etale Fundi Gachoka Hamisi Irungu Jaoko Kiptoo Lagat Mwangi Nduta Odera Pkemoi "
            "Ruto Simiyu Toroitich Wekesa").split()
TOWNS = ("Thika Nyeri Kisii Embu Meru Malindi Naivasha Kakamega Bungoma Kericho Machakos Voi Isiolo Lamu Garissa Busia "
         "Nanyuki Kitui Narok Kilifi").split()
MONTHS = "January February March April May June July August September October November December".split()
ITEMS = "printer router generator freezer scanner projector inverter dishwasher".split()
TOPICS = ("recursion|inflation|photosynthesis|supply curves|hash tables|Newton's second law|integration by parts|the Krebs "
          "cycle|Bayes' rule|plate tectonics|matrix inverses|osmosis|game theory|electrolysis|binary search").split("|")
COURSES = ("Organic Chemistry|Macroeconomics|Linear Algebra|Data Structures|Thermodynamics|Microbiology|Statistics|Operating "
           "Systems|Calculus|Genetics|Databases|Corporate Law|Physics|Networks|Econometrics").split("|")


class Gen:
    def __init__(self, seed):
        self.r = random.Random(seed)
        self.used = set()

    def name(self):
        for _ in range(9999):
            n = f"{self.r.choice(FIRST)} {self.r.choice(SURNAMES)}"
            if n not in self.used:
                self.used.add(n)
                return n
        raise RuntimeError

    def num(self, lo=1000, hi=99000, step=50):
        for _ in range(9999):
            v = self.r.randrange(lo, hi, step)
            if v not in self.used:
                self.used.add(v)
                return v
        raise RuntimeError

    def date(self):
        return f"{self.r.randint(2, 27)} {self.r.choice(MONTHS)}"

    def code(self):
        for _ in range(9999):
            v = f"{self.r.choice('ABCDEFGHKMNPRSTVWXZ')}{self.r.randint(100, 999)}{self.r.choice('ABCDEFGHKMNPRSTVWXZ')}"
            if v not in self.used:
                self.used.add(v)
                return v
        raise RuntimeError


def life(seed=4, each=20):
    """Facts: {shelf, say, ask, answer, change?, new?}: ``each`` per template."""
    g, facts = Gen(seed), []

    def add(shelf, say, ask, answer, new=None):
        facts.append({"shelf": shelf, "say": say, "ask": ask, "answer": str(answer), "new": new})

    for _ in range(each):
        n = g.name(); d = g.date()
        add("personal", f"My cousin {n}'s birthday is on {d}.", f"When is my cousin {n}'s birthday?", d)
        n = g.name(); t = g.r.choice(TOWNS); t2 = g.r.choice([x for x in TOWNS if x != t])
        add("personal", f"My friend {n} lives in {t}.", f"Where does my friend {n} live?", t,
            (f"My friend {n} has moved to {t2}.", t2))
        n = g.name(); v = g.num(); v2 = g.num()
        add("personal", f"I pay my landlady {n} KSh {v:,} a month for the flat.", f"How much do I pay my landlady {n} for the flat?", f"{v:,}",
            (f"My landlady {n} raised the flat's rent to KSh {v2:,} a month.", f"{v2:,}"))
        n = g.name(); d = g.date()
        add("personal", f"My dentist Dr {n} has me booked for {d}.", f"When is my appointment with Dr {n}?", d)
        n = g.name(); v = g.num(20, 400, 10)
        add("personal", f"The matatu to {n}'s place costs me KSh {v}.", f"How much is the matatu to {n}'s place?", v)

        n = g.name(); v = g.r.randint(200, 899); v2 = g.r.randint(900, 1999)
        add("projects", f"At work, {n} is on extension {v}.", f"What is {n}'s extension at work?", v,
            (f"{n}'s work extension changed to {v2}.", v2))
        n = g.name(); d = g.date()
        add("projects", f"I promised our client {n} the quarterly report by {d}.", f"When did I promise client {n} the quarterly report?", d)
        n = g.name(); v = g.num()
        add("projects", f"Our supplier {n} quoted KSh {v:,} for the {g.r.choice(ITEMS)} order.", f"What did supplier {n} quote for the order?", f"{v:,}")
        n = g.name(); t = g.r.choice(TOWNS)
        add("projects", f"{n} manages our {t} branch staff rota.", f"Who manages the staff rota at our {t} branch? It's one of the managers I told you about.", n)

        c = g.code(); v = g.r.randint(3000, 8999); v2 = g.r.randint(9000, 9999)
        add("coding", f"The service {c} runs on port {v} in production.", f"Which port does the service {c} run on in production?", v,
            (f"The service {c} moved to port {v2} in production.", v2))
        c = g.code(); f_ = f"parse_{c.lower()}"
        add("coding", f"The function {f_} throws a KeyError when the header is missing.", f"What error does {f_} throw when the header is missing?", "KeyError")
        c = g.code(); v = g.r.randint(11, 99)
        add("coding", f"The nightly job {c} times out after {v} seconds in CI.", f"After how many seconds does job {c} time out in CI?", v)
        c = g.code(); v = g.r.choice(["Redis", "Postgres", "SQLite", "Kafka", "RabbitMQ", "Nginx"])
        add("coding", f"Service {c} stores its sessions in {v}.", f"Where does service {c} store its sessions?", v)

        c = g.code(); v = g.r.randint(21, 97)
        add("research", f"In experiment {c} the model reached {v} percent accuracy on the benchmark.", f"What accuracy did experiment {c} reach?", v)
        n = g.name(); v = g.r.randint(1995, 2025)
        add("research", f"The paper by {n} on retrieval was published in {v}.", f"When was the paper by {n} on retrieval published?", v)
        c = g.code(); v = g.num(100, 9000, 10)
        add("research", f"Dataset {c} has {v} labelled samples.", f"How many labelled samples does dataset {c} have?", v)
        c = g.code(); v = g.r.choice(["a control group", "a crossover design", "bootstrapped intervals", "a double-blind design"])
        add("research", f"Study {c} used {v} in its method.", f"What did study {c} use in its method?", v)

        n = g.name(); w = g.r.choice(["Kind regards", "Warm wishes", "Yours sincerely", "Best wishes", "With thanks"])
        add("writing", f"When I write to {n}, I sign off with '{w}'.", f"How do I sign off when I write to {n}?", w)
        n = g.name(); w = g.r.choice(["Dr", "Prof", "Mrs", "Eng", "Hon"])
        add("writing", f"In my letters I always address {n} with the title {w}.", f"What title do I use for {n} in my letters?", w)
        c = g.r.choice(TOPICS); n = g.name()
        add("writing", f"My draft for {n}'s newsletter opens with a story about {c}.", f"What does my draft for {n}'s newsletter open with?", c)

        c = g.r.choice(COURSES); code = g.code(); d = g.date()
        add("study", f"My {c} resit, paper {code}, is on {d}.", f"When is my resit for paper {code}?", d)
        c = g.r.choice(COURSES); code = g.code(); t = g.r.choice(TOPICS)
        add("study", f"In unit {code} of {c}, I keep getting {t} wrong.", f"What do I keep getting wrong in unit {code}?", t)
        code = g.code(); v = g.r.randint(4, 88)
        add("study", f"Slide {v} of lecture {code} explains the proof we need for the exam.", f"Which slide of lecture {code} explains the proof?", v)
    g.r.shuffle(facts)
    return facts, g


NOT_KEPT = ["What's the capital of Tanzania?", "Write a two-line poem about the rain.", "Explain what a mortgage is in one sentence.",
            "Can you suggest a name for a bakery?", "How do you say thank you in Swahili?", "Give me one tip for sleeping better.",
            "What is 17 times 23?", "List three colours.", "Translate 'good morning' into French.", "Why is the sky blue? Keep it short."]


def client(root: Path, model: str):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    token = secrets.token_hex(16)
    env = {**os.environ, "CAMR_TOKEN": token, "CAMR_APP_MEMORY": str(root / "app"), "CAMR_PROJECTS": str(root / "projects"),
           "HF_HUB_OFFLINE": "1"}
    proc = subprocess.Popen([sys.executable, "-m", "camr_engine.app", "--port", str(port), "--model", model, "--memory",
                             str(root / "default")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                            cwd=Path(__file__).resolve().parents[1])
    head = {"X-CAMR-Token": token, "Content-Type": "application/json"}

    def call(path, body=None):
        r = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(), headers=head)
        return json.load(urllib.request.urlopen(r, timeout=900))

    def say(text, intent="auto"):
        t = time.perf_counter()
        job = call("/api/chat/message", {"text": text, "intent": intent, "layers": False})["id"]
        at, done, first = 0, None, None
        while done is None:
            r = call(f"/api/live?id={job}&from={at}")
            for e in r["events"]:
                if e["kind"] == "token" and first is None:
                    first = time.perf_counter() - t
                if e["kind"] == "done":
                    done = e
            at = r["next"]
            if r.get("done") and done is None:
                done = {"error": "no done event"}
            time.sleep(0.03)
        done["first_word_s"] = first
        return done

    for _ in range(300):
        try:
            call("/api/chat/state")
            break
        except Exception:  # noqa: BLE001 (still starting)
            time.sleep(1)
    return call, say, proc


def has(reply, answer):
    return str(answer).lower().replace(",", "") in (reply or "").lower().replace(",", "")


def run_questions(say, picked):
    right = 0
    out = []
    for f in picked:
        d = say(f["ask"])
        want = f["new"][1] if f.get("new") else f["answer"]
        ok = has(d.get("reply"), want)
        right += ok
        out.append({"ask": f["ask"], "want": str(want), "right": bool(ok), "reply": (d.get("reply") or "")[:300], "first_word_s": d.get("first_word_s")})
    return right, out


def keeping(a) -> int:
    facts, _ = life(4)
    if a.limit:
        facts = facts[:a.limit]
    r = random.Random(40)
    changes = [f for f in facts if f["new"]]
    repeats = r.sample([f for f in facts if not f["new"]], min(40, len(facts) // 4))
    rows = {"facts": len(facts), "changes": len(changes), "repeats": len(repeats), "not_kept": len(NOT_KEPT) * 4}
    results = {}
    for name, shelf in (("six shelves", "auto"), ("one shelf", "personal")):
        with tempfile.TemporaryDirectory(dir=a.work) as tmp:
            call, say, proc = client(Path(tmp), a.model)
            try:
                call("/api/chat/settings", {"shelf": "auto"})
                for label, about in SHELVES:
                    call("/api/shelves/add", {"label": label, "about": about})
                call("/api/chat/settings", {"shelf": shelf})
                c, kept, sorted_right, wrong = Counter(), 0, 0, Counter()
                t = time.time()
                for f in facts:
                    d = say(f["say"])
                    kept += d.get("intent") == "tell" and d.get("kept") is True
                    if shelf == "auto":
                        sorted_right += d.get("shelf") == f["shelf"]
                        if d.get("shelf") != f["shelf"]:
                            wrong[f"{f['shelf']}->{d.get('shelf')}"] += 1
                for f in changes:
                    d = say(f["new"][0])
                    c["change_told"] += 1
                    c["change_caught"] += "This updates note" in (d.get("reply") or "")  # the reply is what the done event carries
                    c["change_kept"] += d.get("kept") is True
                    c["change_same_shelf"] += d.get("shelf") == f["shelf"] if shelf == "auto" else 0
                for f in repeats:
                    d = say(f["say"])
                    c["repeat_told"] += 1
                    c["repeat_not_doubled"] += d.get("kept") is False
                call("/api/chat/new", {})
                for t_ in (NOT_KEPT[:2] if a.limit else NOT_KEPT * 4):
                    d = say(t_)
                    c["request_told"] += 1
                    c["request_not_kept"] += d.get("intent") != "tell"
                call("/api/chat/new", {})
                tell_s = time.time() - t
                plain = [f for f in facts if not f["new"]]
                pick = r.sample(plain, min(150, len(plain))) + r.sample(changes, min(50, len(changes)))
                right, answers = run_questions(say, pick)
                fw = sorted(x["first_word_s"] for x in answers if x["first_word_s"])
                results[name] = {"facts_kept": int(kept), "sorted_right": int(sorted_right), "sorted_wrong": dict(wrong.most_common(12)),
                                 **{k: int(v) for k, v in c.items()}, "tell_s": round(tell_s, 1), "questions": len(pick), "right": right,
                                 "first_word_p50": round(fw[len(fw) // 2], 3) if fw else None, "answers": answers}
                print(name, json.dumps({k: v for k, v in results[name].items() if k != "answers"}), flush=True)
            finally:
                proc.terminate()
                proc.wait(timeout=60)
    a.records.mkdir(parents=True, exist_ok=True)
    p = a.records / f"{time.strftime('%Y%m%d-%H%M%S')}-keeping.json"
    p.write_text(json.dumps({"kind": "thesis-keeping", "seed": 4, **rows, "results": results}, indent=1))
    print(p)
    return 0


def tasks(g: Gen):
    """{workflow: {tell: [...], tasks: [{ask, check}]}}, where check says what a right answer holds."""
    wf = {}
    # writing: the rules are told once, and every email must keep all of them
    peoples = [g.name() for _ in range(30)]
    tops = ["the budget review", "next week's site visit", "a late invoice", "the new delivery schedule", "the staff party", "our office move"]
    titles = {p: g.r.choice(["Dr", "Prof", "Eng"]) for p in peoples}
    tell = ["I sign every email 'Kind regards, Ibrahim'.", "I never use the word 'utilise' in anything I write.",
            "I always use British spelling, like 'organise' and 'colour'.", "I never start an email with 'I hope this email finds you well'."]
    tell += [f"I always address {p} as {titles[p]} {p.split()[1]}." for p in peoples]
    wf["writing"] = {"tell": tell, "tasks": [{"ask": f"Write a short email to {p} about {g.r.choice(tops)}, the way I write.", "kind": "email",
                                              "must": ["Kind regards", "Ibrahim", f"{titles[p]} {p.split()[1]}"], "never": ["utilize", "utilise", "finds you well", "organize", "color "]} for p in peoples]}
    # study
    tell, ts = [], []
    for _ in range(30):
        c, code, d, t = g.r.choice(COURSES), g.code(), g.date(), g.r.choice(TOPICS)
        tell.append(f"My {c} paper {code} is on {d}, and the topic I keep getting wrong for it is {t}.")
        ts.append({"ask": f"Plan my revision for paper {code}: when is it, and what should I focus on?", "must": [d, t]})
    wf["study"] = {"tell": tell, "tasks": ts}
    # errands
    tell, ts = [], []
    for i in range(30):
        n = g.name()
        kind = i % 3
        if kind == 0:
            till, v = g.num(100000, 999000, 1), g.num()
            tell.append(f"I pay {n}'s rent through till number {till}, and it comes to KSh {v:,}.")
            ts.append({"ask": f"Write the M-Pesa reminder I should use to pay {n}'s rent, with the till and amount.", "must": [till, f"{v:,}"]})
        elif kind == 1:
            code, t = g.code(), g.r.choice(TOWNS)
            tell.append(f"{n}'s gate code at the {t} house is {code}.")
            ts.append({"ask": f"Draft a text telling the plumber how to get through {n}'s gate at the {t} house.", "must": [code]})
        else:
            meter, d = g.num(1000000, 9000000, 7), g.date()
            tell.append(f"{n}'s electricity meter is number {meter}, and the token runs out on {d}.")
            ts.append({"ask": f"Write me a to-do note for topping up {n}'s electricity.", "must": [meter, d]})
    wf["errands"] = {"tell": tell, "tasks": ts}
    # code
    tell, ts = [], []
    for _ in range(30):
        c = g.code().lower()
        kind = g.r.randint(0, 2)
        if kind == 0:
            helper = f"fmt_money_{c}"
            tell.append(f"In the {c} project, money must always be formatted by calling {helper}(amount).")
            ts.append({"ask": f"Write a Python function for the {c} project that prints the total of a list of prices.", "must": [helper], "code": True})
        elif kind == 1:
            url = f"https://api.{c}.example/v2"
            tell.append(f"The {c} project's API base URL is {url}.")
            ts.append({"ask": f"Write a Python function for the {c} project that builds the URL for /orders.", "must": [url], "code": True})
        else:
            table = f"tbl_{c}_users"
            tell.append(f"In the {c} project, the users table is called {table}.")
            ts.append({"ask": f"Write a Python function for the {c} project that returns the SQL to count users.", "must": [table], "code": True})
    wf["code"] = {"tell": tell, "tasks": ts}
    # photos
    pics, ts = [], []
    for i in range(30):
        shop, v, d = g.name(), g.num(), g.date()
        pics.append({"id": f"receipt-{i:02d}", "text": f"RECEIPT\n{shop} Hardware\nDate: {d}\nTotal: KSh {v:,}\nThank you"})
        ts.append({"ask": f"How much was the total on my receipt from {shop} Hardware?", "must": [f"{v:,}"]})
    wf["photos"] = {"pictures": pics, "tell": [], "tasks": ts}
    return wf


def check(task, reply):
    text = reply or ""
    ok = all(has(text, m) for m in task["must"]) and not any(n.lower() in text.lower() for n in task.get("never", []))
    if ok and task.get("code"):
        blocks = re.findall(r"```(?:python)?\n(.*?)```", text, re.S)
        if blocks:
            try:
                ast.parse(blocks[0])
            except SyntaxError:
                return False
    return bool(ok)


def workflows(a) -> int:
    g = Gen(44)
    wf = tasks(g)
    if a.limit:
        wf = {k: {**v, "tell": v["tell"][:a.limit * 2], "tasks": v["tasks"][:a.limit],
                  **({"pictures": v["pictures"][:a.limit]} if v.get("pictures") else {})} for k, v in wf.items()}
    results = {}
    with tempfile.TemporaryDirectory(dir=a.work) as tmp:
        call, say, proc = client(Path(tmp), a.model)
        try:
            call("/api/chat/settings", {"shelf": "auto"})
            for label, about in SHELVES:
                call("/api/shelves/add", {"label": label, "about": about})
            for name, w in wf.items():
                for t in w["tell"]:
                    say(t)
                if w.get("pictures"):
                    src = Path(tmp) / "in.json"
                    src.write_text(json.dumps(w["pictures"]))
                    got = subprocess.run(["swift", str(Path(__file__).with_name("thesis_photos.swift")), str(src), str(Path(tmp) / "pics")],
                                         capture_output=True, text=True, check=True).stdout
                    for item in json.loads(got):
                        call("/api/chat/attach", {"path": item["path"], "shelf": "auto", "read": item["read"]})
            for mode, on in (("memory on", True), ("memory off", False)):
                call("/api/chat/settings", {"on": on})
                for name, w in wf.items():
                    call("/api/chat/new", {})
                    rows, t0 = [], time.time()
                    for task in w["tasks"]:
                        d = say(task["ask"], "chat")
                        rows.append({"ask": task["ask"], "must": [str(m) for m in task["must"]], "right": check(task, d.get("reply")),
                                     "reply": (d.get("reply") or "")[:500], "first_word_s": d.get("first_word_s")})
                    results.setdefault(name, {})[mode] = {"right": sum(x["right"] for x in rows), "of": len(rows), "seconds": round(time.time() - t0, 1), "rows": rows}
                    print(name, mode, results[name][mode]["right"], "/", len(rows), flush=True)
        finally:
            proc.terminate()
            proc.wait(timeout=60)
    a.records.mkdir(parents=True, exist_ok=True)
    p = a.records / f"{time.strftime('%Y%m%d-%H%M%S')}-workflows.json"
    p.write_text(json.dumps({"kind": "thesis-workflows", "seed": 44, "results": results}, indent=1))
    print(p)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["keeping", "workflows"])
    ap.add_argument("--records", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--limit", type=int, help="a smoke test: only this many of each")
    a = ap.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    return keeping(a) if a.cmd == "keeping" else workflows(a)


if __name__ == "__main__":
    raise SystemExit(main())
