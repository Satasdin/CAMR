"""Learning from the web (camr_engine.learn), as the app drives it: start a topic, watch it, then decide where its
notes go. One learning at a time; the model's calls run on the chat's own thread, between its answers.

    POST /api/learn/start   {topic}                     -> the learning
    GET  /api/learn                                     -> the current learning (or none) and the search engine
    POST /api/learn/stop
    POST /api/learn/decide  {choice, shelf?, label?, keep?: [note ids]}
         choice: "shelf" (an existing shelf), "new" (a new shelf named ``label``), "chat" (this chat only), "drop"
"""

from __future__ import annotations

import datetime as dt
import secrets
import subprocess
import threading
import urllib.request
from pathlib import Path

import numpy as np

from camr_engine import learn
from camr_engine import shelves as shelf_list
from camr_engine.app.web import Refused, Request, Routes

SEARX_DIR = Path.home() / ".camr" / "searxng"
CONTAINER = "camr-searxng"
IMAGE = "searxng/searxng:latest"
SETTINGS = """use_default_settings: true
server:
  secret_key: "{key}"
  limiter: false
  image_proxy: false
  bind_address: "0.0.0.0"
search:
  safe_search: 1
  formats:
    - html
    - json
"""

_lock = threading.Lock()
_job: dict = {"job": None, "thread": None}


def searx_up(host: str = learn.SEARX) -> bool:
    try:
        with urllib.request.urlopen(f"{host}/healthz", timeout=2) as r:
            return r.status == 200
    except OSError:
        return False


def start_searx() -> str:
    """Start the local SearXNG in Docker (bound to 127.0.0.1 only), its settings written once. Answers what
    happened, in words."""
    if searx_up():
        return "running"
    SEARX_DIR.mkdir(parents=True, exist_ok=True)
    cfg = SEARX_DIR / "settings.yml"
    if not cfg.exists():
        cfg.write_text(SETTINGS.format(key=secrets.token_hex(24)))
    run = lambda *a: subprocess.run(["docker", *a], capture_output=True, text=True, timeout=60)  # noqa: E731
    if run("start", CONTAINER).returncode != 0:
        got = run("run", "-d", "--name", CONTAINER, "-p", "127.0.0.1:8888:8080", "-v", f"{SEARX_DIR}:/etc/searxng",
                  IMAGE)
        if got.returncode != 0:
            return f"could not start SearXNG: {got.stderr.strip()[:200]}"
    return "starting"


def _talk(req: Request):
    from camr_engine.app.routes.chat import talk

    t = talk(req.app)
    if t is None:
        raise Refused(409, "this app has no model to learn with")
    return t


def _writer(t, reader):
    def write(system: str, user: str, max_tokens: int) -> str:
        return t.run(lambda: reader.generate(reader.chat_ids(system, user), max_tokens=max_tokens).text)
    return write


def _held(t):
    """Each filed shelf's moment vectors (called, curated shelves are not filed onto)."""
    def held() -> dict:
        # as the chat does it: the lock taken here, the work done on the model's thread
        with t.lock:
            session = t._open()

            def read():
                out = {}
                for s in shelf_list.SHELVES:
                    if s.called:
                        continue
                    try:
                        m = session.memory(session._reach(s.reach))
                    except (KeyError, ValueError):
                        continue
                    if len(m.rooms.moments):
                        out[s.name] = list(np.asarray(m.rooms.vectors, dtype=np.float32))
                return out

            return t.run(read)
    return held


def register(routes: Routes) -> None:
    @routes.get("/api/learn")
    def state(req: Request) -> dict:
        job = _job["job"]
        return {"learning": job.view() if job else None, "card": learn.card_text(job) if job and job.state ==
                "deciding" else None, "search": "running" if searx_up() else "stopped"}

    @routes.post("/api/learn/start")
    def start(req: Request) -> dict:
        topic = req.str("topic", limit=200).strip()
        if len(topic) < 3:
            raise Refused(400, "say what to learn about")
        with _lock:
            job = _job["job"]
            if job is not None and job.state not in ("deciding", "done", "failed"):
                raise Refused(409, "already learning about " + job.topic)
            t = _talk(req)
            app = req.app
            if getattr(app, "reader", None) is None or getattr(app, "embedder", None) is None:
                raise Refused(409, "load a model first")
            how = start_searx()
            if how.startswith("could not"):
                raise Refused(503, how)
            job = learn.Learning(secrets.token_hex(4), topic)
            write, embed = _writer(t, app.reader), (lambda text: t.run(lambda: app.embedder.encode_one(text)))
            sorter = {}

            def scores(text: str) -> dict:
                if "s" not in sorter:
                    sorter["s"] = t.run(lambda: shelf_list.Sorter(app.embedder))
                return t.run(lambda: sorter["s"].scores(text))

            labels = {s.name: s.label for s in shelf_list.SHELVES}

            def go():
                for _ in range(60):  # SearXNG takes a few seconds the first time
                    if searx_up() or job.stop.is_set():
                        break
                    job.stop.wait(1.0)
                learn.run(job, write=write, embed=embed, scores=scores, labels=labels, held=_held(t))

            th = threading.Thread(target=go, name="camr-learn", daemon=True)
            _job.update(job=job, thread=th)
            th.start()
        return {"learning": job.view()}

    @routes.post("/api/learn/stop")
    def stop(req: Request) -> dict:
        job = _job["job"]
        if job is not None:
            job.stop.set()
        return {"stopped": job is not None}

    @routes.post("/api/learn/decide")
    def decide(req: Request) -> dict:
        job = _job["job"]
        if job is None or job.state != "deciding":
            raise Refused(409, "nothing is waiting for a decision")
        choice = req.str("choice", limit=10)
        if choice not in ("shelf", "new", "chat", "drop"):
            raise Refused(400, "choice is shelf, new, chat or drop")
        keep = req.body.get("keep")
        if keep is not None and (not isinstance(keep, list) or not all(isinstance(k, str) for k in keep)):
            raise Refused(400, "keep is a list of note ids")
        notes = learn.chosen(job, keep)
        t = _talk(req)
        today = dt.date.today()
        target = None
        if choice == "drop" or not notes:
            job.decision = {"choice": "drop", "kept": 0}
            job.state, job.finished = "done", dt.datetime.now().isoformat(timespec="seconds")
            return {"learning": job.view()}
        if choice == "new":
            label = (req.body.get("label") or job.suggestion.get("new_label") or job.topic)[:30]
            got = t.change_shelves(lambda root: {"shelf": shelf_list.add(root, label, f"Notes learnt from the web "
                                                                         f"about {job.topic}.").name})
            target = got["shelf"]
        elif choice == "shelf":
            target = req.str("shelf", limit=40) if req.body.get("shelf") else job.suggestion.get("shelf")
            if target not in shelf_list.BY_NAME or shelf_list.BY_NAME[target].called:
                raise Refused(400, "that is not a shelf notes can be filed on")

        with t.lock:
            session = t._open()

            def keep_them():
                if target is None:  # this chat only: the session's own memory
                    for n in notes:
                        session.remember(n.as_moment(today), 0, date=today, tags=["web"])
                    session.memory().save()
                else:
                    m = session.memory(session._reach(shelf_list.BY_NAME[target].reach))
                    for n in notes:
                        m.remember(n.as_moment(today), 0, date=today, tags=["web"])
                    m.save()

            t.run(keep_them)
        job.decision = {"choice": choice, "shelf": target, "kept": len(notes)}
        job.state, job.finished = "done", dt.datetime.now().isoformat(timespec="seconds")
        return {"learning": job.view()}
