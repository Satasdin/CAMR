"""The engine behind CAMR for Mac (v2/mac): the app starts it and talks to its JSON API.

    CAMR_TOKEN=<secret> python -m camr_engine.app --port 8765      # memory in ~/.camr/default

Routes live in ``routes/``, one module per part of the app. Everything runs on this Mac; the server listens on
127.0.0.1 only, serves nothing but its API, and answers only a caller that holds the launch token.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import secrets
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from camr_engine.app.web import Refused, Request, Routes

START = dt.date(2026, 1, 5)  # day 0 of the scripted lives; chat moments count days from here too
MAX_BODY = 1 << 20  # a request body larger than 1 MB is refused
CSP = "default-src 'none'; base-uri 'none'; frame-ancestors 'none'"  # the answers are JSON: nothing in one may run


class App:
    def __init__(self, path: Path, reader: str | None = None):
        from camr_engine.app.runtime import Runtime
        from camr_engine.memory import Memory
        from camr_engine.models import Embedder, Reader

        self.reader, self.embedder = (Reader(reader) if reader else Reader()), Embedder()
        from camr_engine.live import probe

        probe(self.reader.model)  # each layer's activity can be watched (camr_engine.live), in Chat and Code alike
        self.memory = Memory(self.reader, self.embedder, path)
        self.lock = threading.Lock()  # one model, one job at a time
        self.today = dt.date.today()
        self.sim = None
        self.sim_root = Path(path).parent / "simulations"
        self.models = Runtime()
        self.models.adopt(self.reader)

    def paths(self) -> dict[str, Path | None]:
        """The logs the app follows: the memory's events and its metrics."""
        log = self.memory.log
        return {"events": log.path if log else None, "metrics": self.memory.path / "metrics.jsonl",
                "memory": self.memory.path}

    def simulate(self, persona: str, seed: int, questions: int) -> dict:
        from camr_engine.app.sim import Simulation

        if self.sim and not self.sim.done:
            self.sim.stop()
            self.sim.thread.join(timeout=30)
        self.sim = Simulation(self, persona, seed, max(5, min(questions, 100)), self.sim_root)
        return self.sim.state()

    def _day(self, d: dt.date) -> int:
        return (d - START).days

    def _last(self, kinds: tuple[str, ...]) -> int:
        events = self.memory.log.read()
        return max(i for i, e in enumerate(events) if e["type"] in kinds)

    def state(self) -> dict:
        r = self.memory.rooms
        return {"moments": len(r.moments), "rooms": len(r.rooms), "disk_mb": round(r.disk_bytes() / 1e6, 1),
                "today": self.today.isoformat()}

    def chat(self, text: str) -> dict:
        text = " ".join(text.split())
        if not text:
            return {"reply": ""}
        with self.lock:
            if text.endswith("?"):
                reply = self.memory.answer(text, self.today)
                return {"reply": reply.text, "event": self._last(("answer",)), "wait_s": round(reply.ttft_s, 3)}
            m = self.memory.remember(f"[{self.today.isoformat()}] {text}", self._day(self.today))
            self.memory.rooms.save()
            return {"reply": "Noted. I'll remember that.", "moment": m.mid, "room": m.room}

    def errand(self, text: str) -> dict:
        from camr_engine.agent import act, done

        with self.lock:
            tool, args, reply = act(self.memory, " ".join(text.split()), self.today)
            return {"tool": tool, "args": args, "result": done(tool, args), "event": self._last(("agent",)),
                    "wait_s": round(reply.ttft_s, 3)}

    def load_life(self, persona: str, seed: int) -> dict:
        from camr_engine.ruler.life import build

        life = build(persona, seed)
        with self.lock:
            for day in life.days:
                for text in day.dated():
                    self.memory.remember(text, day.index)
            self.memory.rooms.save()
        return {"loaded": persona, **self.state()}

    def quiz(self, persona: str, seed: int, errands: bool, limit: int) -> dict:
        """Ask a loaded life's quiz (or its errands) on its last day, keeping each verdict in the log."""
        from collections import Counter

        from camr_engine.agent import act, grade, tasks
        from camr_engine.ruler.grade import grade as quiz_grade
        from camr_engine.ruler.life import build

        life = build(persona, seed)
        day = life.days[-1]
        verdicts = Counter()
        with self.lock:
            if errands:
                for t in tasks(life)[:limit]:
                    right = t.question.answer_on(day.index)
                    tool, args, _ = act(self.memory, t.text, day.date)
                    v = grade(t, tool, args, day.index)
                    self.memory.log.write("verdict", event=self._last(("agent",)), verdict=v,
                                          expected=right[0] if right else None)
                    verdicts[v] += 1
            else:
                for q in life.questions[:limit]:
                    right = q.answer_on(day.index)
                    reply = self.memory.answer(q.text, day.date)
                    v = quiz_grade(q, reply.text, day.index)
                    self.memory.log.write("verdict", event=self._last(("answer",)), verdict=v,
                                          expected=right[0] if right else None)
                    verdicts[v] += 1
        return {"asked": sum(verdicts.values()), "verdicts": dict(verdicts)}

    def brain(self, memory=None, layout=None) -> dict:
        from camr_engine.view.layout import positions

        memory = memory or self.memory
        with self.lock:
            r = memory.rooms
            xy = layout[:len(r.moments)] if layout is not None else positions(r)
            events = memory.log.read()
        return shown(events, [{"room": m.room, "day": m.day, "text": m.text} for m in r.moments],
                     [{"id": x.rid, "members": x.members} for x in r.rooms], xy)


def shown(events: list[dict], moments: list[dict], rooms: list[dict], layout) -> dict:
    """The brain view's data: moments, rooms, layout, and the last 400 answers and errands with their verdicts."""
    verdict = {e["event"]: e for e in events if e["type"] == "verdict"}
    tools = {}
    for i, e in enumerate(events):
        if e["type"] == "tool":
            prev = max((j for j in range(i) if events[j]["type"] == "agent"), default=None)
            if prev is not None:
                tools[prev] = e
    out = []
    for i, e in enumerate(events):
        if e["type"] not in ("answer", "agent") or e.get("room") is None:
            continue
        item = {k: e.get(k) for k in ("question", "room", "nodes", "share", "used", "words", "looks", "wait_s")}
        item.update(id=i, kind=e["type"], at=e["at"], verdict=verdict.get(i, {}).get("verdict"),
                    expected=verdict.get(i, {}).get("expected"))
        if i in tools:
            item.update(tool=tools[i]["tool"], args=tools[i]["args"], result=tools[i]["result"])
        out.append(item)
    return {"moments": moments, "rooms": rooms, "layout": layout, "answers": out[-400:]}


def make_server(app, port: int, *, routes: Routes | None = None) -> tuple[ThreadingHTTPServer, str]:
    """The server (not yet serving) and its launch token."""
    from camr_engine.app.routes import collect

    # Only the app that started this engine may talk to it: websites the user visits can reach 127.0.0.1 too. Requests
    # must name this host (stops DNS rebinding), must not come from another origin, POSTs must be JSON, and every API
    # call carries a secret made at launch.
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    origins = {f"http://{h}" for h in hosts}
    token = os.environ.get("CAMR_TOKEN") or secrets.token_urlsafe(24)  # the Mac app makes its own and passes it
    routes = routes if routes is not None else collect()
    app.route_errors = dict(routes.errors)

    class Handler(BaseHTTPRequestHandler):
        server_version = "camr"
        sys_version = ""

        def _allowed(self, api: bool, post: bool) -> bool:
            if self.headers.get("Host") not in hosts:
                return False
            origin = self.headers.get("Origin")
            if origin is not None and origin not in origins:
                return False
            if api and self.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none"):
                return False
            if post and (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
                return False
            return not api or secrets.compare_digest(self.headers.get("X-CAMR-Token", ""), token)

        def _send(self, code: int, body: bytes, kind: str, cache: str = "no-store") -> None:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj).encode(), "application/json")

        def log_message(self, *args) -> None:  # keep the terminal quiet
            pass

        def _drain(self, size: int) -> None:
            """Read and drop a refused body, at most 16 MB and for at most a second."""
            self.connection.settimeout(1.0)
            left = min(max(size, 0), 16 * MAX_BODY)
            try:
                while left > 0:
                    got = self.rfile.read(min(left, 1 << 16))
                    if not got:
                        break
                    left -= len(got)
            except OSError:
                pass

        def _route(self, method: str, path: str, query: dict, body: dict) -> None:
            fn = routes.find(method, path)
            if fn is None:
                return self._json({"error": "not found"}, 404)
            try:
                return self._json(fn(Request(app, method, path, query, body)))
            except Refused as e:
                return self._json({"error": e.why}, e.code)
            except Exception as e:  # report it to the app instead of dropping the connection
                return self._json({"error": f"{type(e).__name__}: {e}"}, 500)

        def do_GET(self) -> None:
            url = urllib.parse.urlsplit(self.path)
            path = url.path
            if not self._allowed(api=path.startswith("/api/"), post=False):
                return self._json({"error": "forbidden"}, 403)
            if path.startswith("/api/"):
                query = {k: v[-1] for k, v in urllib.parse.parse_qs(url.query, keep_blank_values=True).items()}
                return self._route("GET", path, query, {})
            self._json({"error": "not found"}, 404)

        def do_POST(self) -> None:
            path = urllib.parse.urlsplit(self.path).path
            if not self._allowed(api=True, post=True):
                return self._json({"error": "forbidden"}, 403)
            try:
                size = int(self.headers.get("Content-Length", 0) or 0)
            except ValueError:
                return self._json({"error": "bad length"}, 400)
            if size > MAX_BODY or size < 0:
                self._drain(size)  # so the client reads the refusal instead of a reset connection
                self.close_connection = True
                return self._json({"error": "too large"}, 413)
            try:
                body = json.loads(self.rfile.read(size) or b"{}")
            except ValueError:
                return self._json({"error": "not JSON"}, 400)
            if not isinstance(body, dict):
                return self._json({"error": "send a JSON object"}, 400)
            self._route("POST", path, {}, body)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler), token


def serve(app, port: int) -> None:
    httpd, _ = make_server(app, port)
    where = getattr(getattr(getattr(app, "memory", None), "rooms", None), "path", None) or getattr(app, "folder", "—")
    print(f"CAMR's engine is listening on 127.0.0.1:{port}  (memory: {where})", flush=True)
    if not os.environ.get("CAMR_TOKEN"):
        print("Started without CAMR_TOKEN, so nothing can call it: CAMR for Mac sets one (see mac/build.sh).", flush=True)
    if os.environ.get("CAMR_TOKEN"):  # the Mac app sends its token only once its own engine has said this
        print(f"CAMR-PORT {httpd.server_address[1]}", flush=True)
        _follow_parent(httpd)
    try:
        httpd.serve_forever()
    finally:
        talk = getattr(app, "talk", None)  # the chat's session holds the reach locks: close it so it saves
        if talk is not None:
            try:
                talk.close()
            except Exception:  # noqa: BLE001 - leaving anyway; the locks go with the process
                pass


def _follow_parent(httpd, every: float = 1.0) -> None:
    """Stop serving when the app that started this engine is gone (force-quit or crashed), so the engine does not
    live on holding the memory's locks and the next launch can open it."""
    import threading
    import time

    parent = os.getppid()

    def watch() -> None:
        while os.getppid() == parent:
            time.sleep(every)
        httpd.shutdown()

    threading.Thread(target=watch, name="follow-parent", daemon=True).start()
