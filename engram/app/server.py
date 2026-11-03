"""Engram's app: talk to it, give it errands, and look inside while it works.

    python -m engram.app                      # http://127.0.0.1:8765, memory in ~/.engram/default

One page, three tabs. Chat: what you tell it is remembered, and questions (ending in "?") are answered from memory.
Errands: one tool call filled from memory. Brain: any answer or errand replayed word by word on the specimen view.
A sample life can be loaded and quizzed, so the Brain tab can show what went wrong next to what went right.
Everything runs on this Mac; the server listens on 127.0.0.1 only.
"""

from __future__ import annotations

import datetime as dt
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATIC = Path(__file__).parent / "static"
START = dt.date(2026, 1, 5)  # day 0 of the scripted lives; chat moments count days from here too


class App:
    def __init__(self, path: Path):
        from engram.memory import Memory
        from engram.models import Embedder, Reader

        self.reader, self.embedder = Reader(), Embedder()
        self.memory = Memory(self.reader, self.embedder, path)
        self.lock = threading.Lock()  # one model, one job at a time
        self.today = dt.date.today()

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
        from engram.agent import act, done

        with self.lock:
            tool, args, reply = act(self.memory, " ".join(text.split()), self.today)
            return {"tool": tool, "args": args, "result": done(tool, args), "event": self._last(("agent",)),
                    "wait_s": round(reply.ttft_s, 3)}

    def load_life(self, persona: str, seed: int) -> dict:
        from engram.ruler.life import build

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

        from engram.agent import act, grade, tasks
        from engram.ruler.grade import grade as quiz_grade
        from engram.ruler.life import build

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

    def brain(self) -> dict:
        from engram.view.layout import positions

        with self.lock:
            r = self.memory.rooms
            xy = positions(r)
            events = self.memory.log.read()
        verdict = {e["event"]: e for e in events if e["type"] == "verdict"}
        tools = {}
        for i, e in enumerate(events):
            if e["type"] == "tool":
                prev = max((j for j in range(i) if events[j]["type"] == "agent"), default=None)
                if prev is not None:
                    tools[prev] = e
        shown = []
        for i, e in enumerate(events):
            if e["type"] not in ("answer", "agent") or e.get("room") is None:
                continue
            item = {k: e[k] for k in ("question", "room", "nodes", "share", "used", "words", "looks", "wait_s")}
            item.update(id=i, kind=e["type"], at=e["at"], verdict=verdict.get(i, {}).get("verdict"),
                        expected=verdict.get(i, {}).get("expected"))
            if i in tools:
                item.update(tool=tools[i]["tool"], args=tools[i]["args"], result=tools[i]["result"])
            shown.append(item)
        return {"moments": [{"room": m.room, "day": m.day, "text": m.text} for m in r.moments],
                "rooms": [{"id": x.rid, "members": x.members} for x in r.rooms], "layout": xy, "answers": shown[-400:]}


def serve(app: App, port: int) -> None:
    # Only this page may talk to the server: other websites the user visits can reach 127.0.0.1 too. Requests must
    # name this host (stops DNS rebinding), POSTs must be JSON from this origin, and every API call carries a secret
    # made at launch that only the served page knows.
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    origins = {f"http://{h}" for h in hosts}
    token = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def _allowed(self, api: bool, post: bool) -> bool:
            if self.headers.get("Host") not in hosts:
                return False
            origin = self.headers.get("Origin")
            if origin is not None and origin not in origins:
                return False
            if post and (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
                return False
            return not api or secrets.compare_digest(self.headers.get("X-Engram-Token", ""), token)

        def _send(self, code: int, body: bytes, kind: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj).encode(), "application/json")

        def log_message(self, *args) -> None:  # keep the terminal quiet
            pass

        def do_GET(self) -> None:
            if not self._allowed(api=self.path.startswith("/api/"), post=False):
                return self._json({"error": "forbidden"}, 403)
            if self.path in ("/", "/index.html"):
                page = (STATIC / "index.html").read_text().replace("__ENGRAM_TOKEN__", token)
                return self._send(200, page.encode(), "text/html; charset=utf-8")
            if self.path == "/api/state":
                return self._json(app.state())
            if self.path == "/api/brain":
                return self._json(app.brain())
            self._json({"error": "not found"}, 404)

        def do_POST(self) -> None:
            if not self._allowed(api=True, post=True):
                return self._json({"error": "forbidden"}, 403)
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0) or 0)) or b"{}")
            try:
                if self.path == "/api/chat":
                    return self._json(app.chat(str(body.get("text", ""))))
                if self.path == "/api/errand":
                    return self._json(app.errand(str(body.get("text", ""))))
                if self.path == "/api/life":
                    return self._json(app.load_life(str(body.get("persona", "farmer")), int(body.get("seed", 0))))
                if self.path == "/api/quiz":
                    return self._json(app.quiz(str(body.get("persona", "farmer")), int(body.get("seed", 0)),
                                               bool(body.get("errands")), int(body.get("limit", 100))))
            except Exception as e:  # report it to the page instead of dropping the connection
                return self._json({"error": f"{type(e).__name__}: {e}"}, 500)
            self._json({"error": "not found"}, 404)

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"engram is listening on http://127.0.0.1:{port}  (memory: {app.memory.rooms.path})", flush=True)
    httpd.serve_forever()
