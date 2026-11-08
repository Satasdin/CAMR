"""A demo memory for showing CAMR for Mac: one consistent life told to a fresh engine, message by message, the way
the app tells it (POST /api/chat/message, intent "auto"), so every memory is sorted onto its shelf by the engine
itself. Some facts change partway (rent, a fare, an extension), so the newest-kept behaviour can be shown.

    .venv/bin/python scripts/demo_life.py              # → ~/.camr/demo
    CAMR_MEMORY_DIR=~/.camr/demo open mac/build/CAMR.app

It starts its own engine on a free port with its own token and stops it at the end. Nothing here is a benchmark.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

MODEL = "mlx-community/Qwen3-4B-Instruct-2507-4bit"

LIFE = [
    # people
    "My sister Amina moved to Nakuru last week, and her birthday is on 14 March.",
    "Mama Wanjiru's birthday is on 13 November. Her old kikoy is worn out and she wants a blue one for church.",
    "My friend Otieno works at the county office and prefers calls after 6 pm.",
    "Kevin handles payroll at work and his extension is 209.",
    "Ms Achieng is the hiring manager for the data team. She signs her emails 'Ms', with no full stop.",
    # money and errands
    "My rent is KSh 25,000 a month, paid on the 28th.",
    "The matatu fare to Kitengela is KSh 100.",
    "The water bill is due on the 10th of each month.",
    "I go to the gym on Mondays and Wednesdays.",
    "I pass the fabric shops on Moi Avenue on Tuesday evenings.",
    # work and projects
    "The shop site's cart total must always round to whole shillings: never show cents.",
    "The shop site runs on port 8010 in production.",
    "I promised Kevin the payroll sheet by Friday.",
    "My final-year project is CAMR, a memory engine for small models on a Mac.",
    "CAMR's deadline for the thesis draft is the end of November.",
    # writing
    "I write short sentences and use British spelling.",
    "I never use the word 'utilise' in my letters.",
    "I sign my letters 'Kind regards, Ibrahim'.",
    "My letter to the bank in June told the M-Pesa till story and got me an interview.",
    # study
    "In algorithms, I keep forgetting that counting sort is O(n) when the keys are small.",
    "My statistics exam is on 21 November.",
    "Slide 14 of my algorithms lecture explains counting sort.",
    # a trip
    "I'm planning a trip to Mount Kenya in late January with Otieno.",
    "We want to stay in Laikipia, under KSh 8,000 a night.",
    "I'm free from 24 to 26 January.",
    # things change
    "Update: my rent went up to KSh 28,000 from March.",
    "The matatu fare to Kitengela went up to KSh 120.",
    "Kevin's extension changed to 214 on the new phones.",
    "The water bill is now due on the 15th.",
    "I moved my gym days to Tuesday, Thursday and Saturday.",
    "The shop site moved to port 8200 in production; the staging box took 8010.",
]

SHELVES = [  # beside the engine's own (Projects, Coding, Research, Personal)
    ("Writing", "How you write: your style, words you use and avoid, how you sign off, letters, drafts and emails."),
    ("Study", "Studying: courses, lectures, slides, exams, revision, topics you keep getting wrong."),
]

QUESTIONS = [
    "What's my rent now?",
    "Where does my sister live, and when is her birthday?",
    "What did I promise Kevin, and what's his extension?",
]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=Path.home() / ".camr" / "demo")
    ap.add_argument("--model", default=MODEL)
    a = ap.parse_args()
    if a.dir.exists() and any(a.dir.iterdir()):
        print(f"{a.dir} already holds a memory; give another --dir or move it away first", file=sys.stderr)
        return 1
    a.dir.mkdir(parents=True, exist_ok=True)
    port, token = free_port(), secrets.token_hex(16)
    env = {**os.environ, "CAMR_TOKEN": token, "CAMR_APP_MEMORY": str(a.dir / "app"),
           "CAMR_PROJECTS": str(a.dir / "projects")}
    engine = subprocess.Popen([sys.executable, "-m", "camr_engine.app", "--port", str(port), "--model", a.model,
                               "--memory", str(a.dir / "default")], env=env, stdout=subprocess.DEVNULL,
                              stderr=subprocess.STDOUT, cwd=Path(__file__).resolve().parents[1])
    base = f"http://127.0.0.1:{port}"
    head = {"X-CAMR-Token": token, "Content-Type": "application/json"}

    def call(path, body=None):
        r = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=head)
        return json.load(urllib.request.urlopen(r, timeout=300))

    def say(text):
        job = call("/api/chat/message", {"text": text, "intent": "auto", "layers": False})["id"]
        at, done = 0, None
        while done is None:
            r = call(f"/api/live?id={job}&from={at}")
            done = next((e for e in r["events"] if e["kind"] == "done"), None)
            at = r["next"]
            time.sleep(0.1)
        return done

    try:
        for _ in range(120):
            try:
                call("/api/chat/state")
                break
            except Exception:  # noqa: BLE001 - still starting
                time.sleep(1)
        call("/api/chat/settings", {"shelf": "auto"})
        for label, about in SHELVES:
            call("/api/shelves/add", {"label": label, "about": about})
        for t in LIFE:
            d = say(t)
            print(f"{d.get('intent', '?'):6} {str(d.get('shelf') or '-'):9} {t[:70]}")
        call("/api/chat/new", {})
        for q in QUESTIONS:
            d = say(q)
            print(f"\nQ: {q}\nA: {(d.get('reply') or d.get('error') or '').strip()[:300]}")
        s = call("/api/chat/state")
        print("\nshelves:", ", ".join(f"{x['label']} {x['moments']}" for x in s["shelves"]))
    finally:
        engine.terminate()
        engine.wait(timeout=30)
    print(f"\ndemo memory in {a.dir}: open the app with CAMR_MEMORY_DIR={a.dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
