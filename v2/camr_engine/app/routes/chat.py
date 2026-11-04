"""Chat's routes: tell, ask, or give one errand, through a reach.Session that reads several reaches and writes one.

- ``GET /api/chat/state``: memory on or off, each of the four reaches (read or not, the one written, its notes and
  its bytes on the SSD), the model and its window, the history's tokens and the last answer's context;
- ``POST /api/chat/settings`` ``{on, reads, writes, project, agent}``: switch memory, or read other reaches (the
  session is opened again over them; its own reach keeps its name, so nothing it was told is lost);
- ``POST /api/chat`` ``{text, intent}``: ``tell`` keeps a moment, ``ask`` answers, ``errand`` makes one tool call.
  Without an intent, text ending in a question mark is asked and anything else is told;
- ``POST /api/errand`` ``{text}``: the same as an errand intent;
- ``GET /api/chat/thread``: this run's turns, so a reload shows the conversation again;
- shelves (camr_engine.shelves): every chat reads the Projects, Coding, Research and Personal shelves too, and a
  remembered moment goes on the shelf the settings name (``{shelf}``: a shelf's name, or ``auto`` to file it by
  meaning); once a session opens, its model and the newest notes of every shelf are warmed (``GET /api/live?id=warm``);
- ``POST /api/chat/message`` ``{text, intent, shelf}``: the same as ``POST /api/chat``, started at once and answered with
  ``{id}``; ``GET /api/live?id=&from=N`` then gives the job's events as they happen (camr_engine.live): the room
  read, each word with every layer's activity, and the reply (``done``). The Mac app draws its weights view from
  these.

The session lives on the app as ``app.session`` (the shell's ``/api/state`` lists its reaches from there). It is
opened the first time a screen asks for it, with every engine layer on: the vault, the core, the RAM and SSD tiers,
and one metrics record per answer. Opening reads the header with the model, so it happens under the app's lock, like
every step: a poll that finds the model busy does not wait for it, and after a failed open a poll tries again at most
every 30 s (a send or a settings change tries at once). Its reaches live beside the app's memory folder
(``~/.camr`` by default: ``global``, ``session/<id>``, ``project/<name>``, ``agent/<name>``). It answers with the
memory's own reader: the rooms are that model's notes, which another model could not read. An app with no reader (a
recorded memory, a stand-in in a test) has no session; its own ``chat`` and ``errand`` are used when it has them.
A message is at most 4,000 characters: a longer one is refused (413), never kept cut short.
"""

from __future__ import annotations

import datetime as dt
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from camr_engine.app.web import Refused, Request, Routes, part
from camr_engine.live import Live, current, probe, reporting
from camr_engine.shelves import BY_NAME, SHELVES, Sorter, shelf_of, warm
from camr_engine.shelves import reaches as shelf_reaches

INTENTS = ("tell", "ask", "errand")
DEFAULT_READS = ("session", "global")
TURNS = 400  # turns kept for the thread
TEXT_MAX = 4000  # characters in one message; a longer one is refused, never cut
RETRY_S = 30.0  # after a failed open, a poll tries again at most this often
JOBS = 30  # live jobs kept for GET /api/live


def _measuring() -> dict | None:
    from camr_engine.app.measuring import active

    return active()


def _not_measuring() -> None:
    job = _measuring()
    if job:
        raise Refused(409, f"a benchmark is measuring ({job['job']}); chat waits until it is done")


class Talk:
    """The app's conversation: one reach.Session, the settings it was opened with, and this run's turns."""

    def __init__(self, app):
        from camr_engine.reach import new_session

        self.app = app
        self.on = True
        self.reads: list[str] = list(DEFAULT_READS)
        self.writes = "session"
        self.project: str | None = None
        self.agent: str | None = None
        self.name = getattr(app, "session_name", None) or new_session()
        self.session = None
        self.error: str | None = None
        self.failed = 0.0  # time.monotonic() of the last failed open
        self.turns: list[dict] = []
        self.lock = getattr(app, "lock", None) or threading.Lock()  # one model, one job at a time
        # Every MLX call for the session runs on this one thread. Once mlx_lm is loaded each thread has its own
        # default stream, and the session keeps lazy arrays between requests (a hot room's copy, joined with new
        # notes), which another request's thread could not evaluate.
        self.worker = ThreadPoolExecutor(1, thread_name_prefix="camr-session")
        self.jobs: dict[str, Live] = {}
        self.shelf: str | None = None  # where a remembered moment goes: a shelf, auto (by meaning), or None: the
        # session's own reach (the Mac app picks auto)
        self.sorter: Sorter | None = None

    # -- the session

    @property
    def root(self) -> Path:
        root = getattr(self.app, "reach_root", None)
        if root is not None:
            return Path(root)
        return Path(self.app.memory.path).parent

    def _make(self):
        from camr_engine.reach import Session

        settings = {"vault": True, "core": True, "tiers": {}, "metrics": True,
                    **(getattr(self.app, "session_settings", None) or {})}
        reads = list(self.reads)
        if self.shelf is not None:  # shelves on: every shelf is read too
            reads += [r for r in shelf_reaches() if r not in reads]
        return Session(self.app.reader, self.app.embedder, root=self.root, name=self.name, project=self.project,
                       agent=self.agent, reads=reads, writes=self.writes, on=self.on, **settings)

    def ensure(self, *, wait: bool = True):
        """The session, opened now if it is not yet, under the app's lock. With ``wait=False``, None when the model is
        busy with another job (a poll asks again later)."""
        if self.session is not None:
            return self.session
        if not self.lock.acquire(blocking=wait):
            return None
        try:
            return self._open()
        finally:
            self.lock.release()

    def poll(self):
        """The session for a GET: opened now only if that needs no waiting, never while a benchmark measures, and
        after a failed open at most once every 30 s. None when it is not open."""
        if self.session is not None:
            return self.session
        if _measuring() or (self.error is not None and time.monotonic() - self.failed < RETRY_S):
            return None
        try:
            return self.ensure(wait=False)
        except Refused:
            return None

    def _open(self):
        """The session, opened now if it is not yet (never while a benchmark measures: opening reads the header
        with the model). The caller holds ``self.lock``."""
        if self.session is not None:
            return self.session
        _not_measuring()
        try:
            self.session = self.run(self._make)
            self.error = None
        except Exception as e:  # noqa: BLE001 (shown on the composer)
            self.error = f"{type(e).__name__}: {e}"[:300]
            self.failed = time.monotonic()
            raise Refused(409, f"the memory could not be opened: {self.error}") from None
        self.app.session = self.session
        try:  # each layer's activity can now be measured while a Live listens
            probe(self.app.reader.model)
        except (AttributeError, ValueError):  # a stand-in reader has no layers
            pass
        live = self.jobs["warm"] = Live("warm")
        session = self.session

        def warming():
            with reporting(live):
                try:
                    warm(self.app.reader, {r.label: m for r, m in session.memories.items()}, report=live.add)
                finally:
                    live.finish()

        self.worker.submit(warming)  # before any question, on the session's own thread
        return self.session

    def configure(self, *, on: bool | None = None, reads: list[str] | None = None, writes: str | None = None,
                  project: str | None = None, agent: str | None = None) -> dict:
        """Change what the session reads or writes (it is opened again over the new reaches), or switch memory."""
        from camr_engine.reach import KINDS, Reach

        new_reads = list(dict.fromkeys(reads)) if reads is not None else list(self.reads)
        new_writes = writes if writes is not None else self.writes
        new_project = (project or None) if project is not None else self.project
        new_agent = (agent or None) if agent is not None else self.agent
        for k in new_reads + [new_writes]:
            if k not in KINDS:
                raise Refused(400, f"a reach is one of {', '.join(KINDS)}")
        if new_writes not in new_reads:
            new_reads.insert(0, new_writes)  # the written reach is always read
        try:
            for k, n in (("project", new_project), ("agent", new_agent)):
                if n is not None:
                    Reach(k, n)
                if k in new_reads and n is None:
                    raise Refused(400, f"reading the {k} reach needs its name")
        except ValueError as e:
            raise Refused(400, str(e)) from None
        reopen = (new_reads, new_writes, new_project, new_agent) != (self.reads, self.writes, self.project,
                                                                      self.agent)
        with self.lock:
            if on is not None:
                self.on = bool(on)
                if self.session is not None:
                    self.session.switch(self.on)
            if reopen:
                _not_measuring()
                old = (self.reads, self.writes, self.project, self.agent)
                self.reads, self.writes, self.project, self.agent = new_reads, new_writes, new_project, new_agent
                if self.session is not None:
                    self.run(self.session.close)
                    self.session = None
                    self.app.session = None
                try:
                    self._open()
                except Refused:
                    self.reads, self.writes, self.project, self.agent = old  # put back what worked
                    try:
                        self._open()
                    except Refused:
                        pass
                    raise
        return self.state()

    def use_shelf(self, shelf: str | None) -> None:
        """Where remembered moments go: a shelf, auto, or None (shelves off: the session's own reach, and only the
        reaches picked are read). Turning shelves on or off opens the session again over its new reaches."""
        with self.lock:
            changed = (shelf is None) != (self.shelf is None)
            self.shelf = shelf
            if changed and self.session is not None:
                _not_measuring()
                self.run(self.session.close)
                self.session = None
                self.app.session = None
                self._open()

    def close(self) -> None:
        with self.lock:
            if self.session is not None:
                self.run(self.session.close)
                self.session = None
                self.app.session = None

    def run(self, fn, *args):
        """``fn(*args)`` on the session's own thread, waited for. It reports to the caller's Live."""
        live = current()

        def within():
            with reporting(live):
                return fn(*args)

        return self.worker.submit(within).result()

    def start(self, text: str, intent: str | None = None, shelf: str | None = None) -> dict:
        """``say`` on a thread of its own, reporting to a new Live: ``{id}`` names it for ``GET /api/live``."""
        import secrets

        live = Live("message")
        jid = secrets.token_hex(6)
        self.jobs[jid] = live
        for old in list(self.jobs)[:-JOBS]:
            del self.jobs[old]

        def work():
            with reporting(live):
                live.add("start", text=" ".join(text.split()), intent=intent, on=self.on)
                try:
                    out = self.say(text, intent, shelf)
                except Refused as e:
                    live.finish(error=e.why, code=e.code)
                except Exception as e:  # noqa: BLE001 (shown in the chat)
                    live.finish(error=f"{type(e).__name__}: {e}"[:300])
                else:
                    live.finish(**{k: out.get(k) for k in ("intent", "on", "reply", "reach", "shelf", "sorted",
                                                          "wait_s", "metric", "kept", "room", "moment", "tokens",
                                                          "seconds")})

        threading.Thread(target=work, daemon=True, name="camr-message").start()
        return {"id": jid}

    # -- talking

    def _today(self) -> tuple[dt.date, int]:
        today = getattr(self.app, "today", None) or dt.date.today()
        day = self.app._day(today) if hasattr(self.app, "_day") else 0
        return today, day

    def say(self, text: str, intent: str | None = None, shelf: str | None = None) -> dict:
        text = " ".join(text.split())
        if not text:
            return {"reply": "", "intent": None}
        intent = intent or ("ask" if text.endswith("?") else "tell")
        if intent not in INTENTS:
            raise Refused(400, f"intent is one of {', '.join(INTENTS)}")
        _not_measuring()
        today, day = self._today()
        step = {"tell": self._tell, "ask": self._ask, "errand": self._errand}[intent]
        with self.lock:  # the session is taken under the lock: a settings change may have closed the one before
            session = self._open()
            t = time.perf_counter()
            out = (self.run(step, session, text, today, day, shelf) if intent == "tell"
                   else self.run(step, session, text, today, day))
            out["seconds"] = round(time.perf_counter() - t, 4)
        self._keep({"who": "you", "text": text, "intent": intent, "at": _now()})
        self._keep({"who": "camr", **out, "at": _now()})
        return out

    def _tell(self, session, text: str, today: dt.date, day: int, shelf: str | None = None) -> dict:
        if not session.on:
            return {"intent": "tell", "on": False, "reply": "Memory is off, so nothing was kept.", "kept": False}
        target, sorted_ = shelf or self.shelf, None
        if target == "auto":
            if self.sorter is None:
                self.sorter = Sorter(session.embedder)
            sorted_ = self.sorter.sort(text)
            target = sorted_.name
        reach = session._reach(BY_NAME[target].reach) if target in BY_NAME else session.home
        m = session.remember(f"[{today.isoformat()}] {text}", day, date=today, to=reach)
        session.memory(reach).save()
        on = shelf_of(reach.label)
        return {"intent": "tell", "on": True, "reply": f"Noted, on the {on.label} shelf." if on else "Noted.",
                "kept": True, "reach": reach.label, "shelf": on.name if on else None, "sorted": sorted_ is not None,
                "moment": m.mid, "room": m.room, "tokens": m.tokens,
                "event": self._event(session.memory(reach), ("remember",))}

    def _ask(self, session, text: str, today: dt.date, day: int) -> dict:
        reply = session.answer(text, today, day=day)
        return self._reply("ask", session, reply, ("answer",))

    def _errand(self, session, text: str, today: dt.date, day: int) -> dict:
        from camr_engine.agent import THEN, TOOLS, done, parse

        if session.on:
            reply = session.answer(text, today, then=THEN, tools=TOOLS, max_tokens=120, kind="agent", day=day)
        else:
            reply = session.plain(text, today, then=THEN, tools=TOOLS, max_tokens=120)
        tool, args = parse("".join(reply.pieces))
        out = self._reply("errand", session, reply, ("agent",))
        result = done(tool, args)
        m = self._chosen(session)
        if session.on and m is not None and m.log is not None:
            m.log.write("tool", task=text, tool=tool, args=args, result=result)
        out.update(tool=tool, args=args, result=result)
        return out

    def _chosen(self, session):
        rec = session.last
        if rec is None:
            return None
        return next((m for r, m in session.memories.items() if r.label == rec.reach), None)

    def _reply(self, intent: str, session, reply, kinds: tuple[str, ...]) -> dict:
        metric = getattr(reply, "metrics", None)
        out = {"intent": intent, "on": session.on, "reply": reply.text, "words": list(reply.pieces),
               "wait_s": round(float(reply.ttft_s), 4),
               "metric": metric.to_dict() if hasattr(metric, "to_dict") else metric}
        m = self._chosen(session) if session.on else None
        if m is not None:
            out["reach"] = m.reach
            out["event"] = self._event(m, kinds)
        return out

    def _event(self, memory, kinds: tuple[str, ...]) -> dict | None:
        from camr_engine.app.routes.memory import last_event

        e = last_event(self.app, memory, kinds)
        if e is not None:
            e.setdefault("reach", memory.reach)
            e["src"] = memory.reach or "memory"
        return e

    def _keep(self, turn: dict) -> None:
        self.turns.append(turn)
        del self.turns[:-TURNS]

    # -- what the composer shows

    def state(self) -> dict:
        from camr_engine.reach import KINDS, Reach

        session = self.session
        names = {"session": self.name, "project": self.project, "agent": self.agent, "global": ""}
        reaches = []
        history = 0
        for k in KINDS:
            n = names[k]
            label = None
            folder = None
            if k == "global" or n:
                r = Reach(k, n)
                label, folder = r.label, r.path(self.root) if self._rooted() else None
            m = None
            if session is not None and label is not None:
                m = next((mem for rr, mem in session.memories.items() if rr.label == label), None)
            size = _size(m, folder)
            read = k in self.reads
            if read:
                history += size["history_tokens"] or 0
            reaches.append({"kind": k, "name": n or None, "label": label, "read": read, "written": k == self.writes,
                            "open": m is not None, **size})
        reader = getattr(self.app, "reader", None)
        picked = None
        runtime = getattr(self.app, "models", None)
        if runtime is not None and hasattr(runtime, "state"):
            p = runtime.state().get("picked")
            picked = p.get("repo") if p else None
        last = None
        if session is not None and session.meter.last is not None:
            r = session.meter.last
            last = {"context_tokens": r.context_tokens, "history_tokens": r.history_tokens,
                    "first_word_s": r.first_word_s, "total_s": r.total_s}
        shelves = []
        for sh in SHELVES:
            m = None
            if session is not None:
                m = next((mem for rr, mem in session.memories.items() if rr.label == sh.reach), None)
            size = _size(m, None) if m is not None else {}
            shelves.append({"name": sh.name, "label": sh.label, "reach": sh.reach, "rooms": size.get("rooms", 0),
                            "moments": size.get("moments", 0), "room_bytes": size.get("room_bytes", 0)})
        return {"ready": session is not None, "can": self.can(), "why": self.error, "measuring": _measuring(),
                "shelf": self.shelf, "shelves": shelves,
                "on": self.on, "session": self.name, "reads": list(self.reads), "writes": self.writes,
                "project": self.project, "agent": self.agent, "reaches": reaches,
                "projects": self._names("project"), "agents": self._names("agent"),
                "model": {"repo": getattr(reader, "repo", None), "window": _window(reader)}, "picked": picked,
                "history_tokens": history, "last": last, "busy": self.lock.locked()}

    def can(self) -> bool:
        return can_talk(self.app)

    def _rooted(self) -> bool:
        try:
            self.root
            return True
        except AttributeError:
            return False

    def _names(self, kind: str) -> list[str]:
        if not self._rooted():
            return []
        try:
            return sorted(p.name for p in (self.root / kind).iterdir() if p.is_dir() and not p.name.startswith("."))[:50]
        except OSError:
            return []


def can_talk(app) -> bool:
    """An app with a reader and an embedder can open a session; a recorded memory or a stand-in cannot."""
    return getattr(app, "reader", None) is not None and getattr(app, "embedder", None) is not None and (
        getattr(app, "reach_root", None) is not None or getattr(getattr(app, "memory", None), "path", None) is not None)


def talk(app) -> Talk | None:
    """The app's Talk, made on first use; None for an app that cannot open a session."""
    if not can_talk(app):
        return None
    return part(app, "talk", lambda: Talk(app))


def _window(reader) -> int | None:
    """The model's context window, from its config."""
    args = getattr(getattr(reader, "model", None), "args", None)
    n = getattr(args, "max_position_embeddings", None)
    return int(n) if isinstance(n, int) else None


_SIZES: dict[str, tuple[float, dict]] = {}


def _size(memory, folder: Path | None) -> dict:
    """A reach's size: notes in its vault, room bytes on the SSD, moments and tokens. Read from the open memory, or
    from its folder on disk (looked at again at most every 5 s)."""
    if memory is not None:
        r = memory.rooms
        tiers = getattr(memory, "tiers", None)
        awake = tiers.disk_bytes() if tiers is not None else r.disk_bytes()
        return {"notes": len(memory.vault) if getattr(memory, "vault", None) is not None else None,
                "room_bytes": int(awake), "moments": len(r.moments), "history_tokens": sum(x.tokens for x in r.rooms),
                "rooms": len(r.rooms), "exists": True}
    if folder is None or not folder.is_dir():
        return {"notes": 0 if folder is not None else None, "room_bytes": 0 if folder is not None else None,
                "moments": 0 if folder is not None else None, "history_tokens": 0 if folder is not None else None,
                "exists": False}
    key = str(folder)
    got = _SIZES.get(key)
    if got is not None and time.monotonic() - got[0] < 5:
        return got[1]
    from camr_engine.app.routes.memory import folder_size

    try:
        index = json.loads((folder / "index.json").read_text())
        moments, tokens = len(index.get("moments", [])), sum(int(x.get("tokens", 0)) for x in index.get("rooms", []))
    except (OSError, ValueError):
        moments, tokens = 0, 0
    try:
        notes = sum(1 for p in (folder / "vault").iterdir() if p.suffix == ".md")
    except OSError:
        notes = 0
    out = {"notes": notes, "room_bytes": folder_size(folder, "room-*.notes"), "moments": moments,
           "history_tokens": tokens, "exists": True}
    _SIZES[key] = (time.monotonic(), out)
    return out


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="milliseconds")


def _text(req: Request) -> str:
    """The message, whole: one longer than TEXT_MAX is refused, so nothing is kept cut short."""
    v = req.body.get("text", "")
    text = "" if v is None else str(v)
    if len(text) > TEXT_MAX:
        raise Refused(413, f"a message is at most {TEXT_MAX:,} characters; this one has {len(text):,}")
    return text


def register(routes: Routes) -> None:
    @routes.get("/api/chat/state")
    def state(req: Request) -> dict:
        t = talk(req.app)
        if t is None:
            return {"ready": False, "can": False, "why": "this app has no reader to talk with (a recorded memory is "
                    "read-only)", "on": False, "reaches": [], "measuring": _measuring(), "model": {"repo": None,
                                                                                                  "window": None}}
        t.poll()
        return t.state()

    @routes.post("/api/chat/settings")
    def settings(req: Request) -> dict:
        t = talk(req.app)
        if t is None:
            raise Refused(409, "this app has no memory to set (a recorded memory is read-only)")
        reads = req.body.get("reads")
        if reads is not None and (not isinstance(reads, list) or not all(isinstance(x, str) for x in reads)):
            raise Refused(400, "reads is a list of reaches")
        on = req.body.get("on")
        if "shelf" in req.body:
            shelf = req.str("shelf", limit=20) or None
            if shelf is not None and shelf != "auto" and shelf not in BY_NAME:
                raise Refused(400, f"a shelf is auto or one of {', '.join(BY_NAME)}")
            t.use_shelf(shelf)
        return t.configure(on=None if on is None else bool(on), reads=reads,
                           writes=req.str("writes", limit=20) or None,
                           project=req.str("project", limit=64) if "project" in req.body else None,
                           agent=req.str("agent", limit=64) if "agent" in req.body else None)

    @routes.post("/api/chat")
    def chat(req: Request) -> dict:
        text = _text(req)
        intent = req.str("intent", limit=10) or None
        t = talk(req.app)
        if t is None:
            fn = getattr(req.app, "errand" if intent == "errand" else "chat", None)
            if fn is None:
                raise Refused(409, "this app has no memory to talk to (a fixture is read-only)")
            return fn(text)
        return t.say(text, intent)

    @routes.post("/api/errand")
    def errand(req: Request) -> dict:
        text = _text(req)
        t = talk(req.app)
        if t is None:
            fn = getattr(req.app, "errand", None)
            if fn is None:
                raise Refused(409, "this app has no memory to talk to (a fixture is read-only)")
            return fn(text)
        return t.say(text, "errand")

    @routes.post("/api/chat/message")
    def message(req: Request) -> dict:
        text = _text(req)
        t = talk(req.app)
        if t is None:
            raise Refused(409, "this app has no memory to talk to (a fixture is read-only)")
        shelf = req.str("shelf", limit=20) or None
        if shelf is not None and shelf != "auto" and shelf not in BY_NAME:
            raise Refused(400, f"a shelf is auto or one of {', '.join(BY_NAME)}")
        return t.start(text, req.str("intent", limit=10) or None, shelf)

    @routes.get("/api/live")
    def live(req: Request) -> dict:
        t = talk(req.app)
        job = t.jobs.get(req.str("id", limit=20)) if t is not None else None
        if job is None:
            raise Refused(404, "no such job")
        return job.since(req.int("from", 0, lo=0) or 0)

    @routes.get("/api/chat/thread")
    def thread(req: Request) -> dict:
        t = talk(req.app)
        n = req.int("n", TURNS, lo=1, hi=TURNS)
        return {"turns": (t.turns[-n:] if t is not None else []), "session": t.name if t is not None else None}
