"""Chat through a reach.Session: tell, ask and errands over the reaches it reads, memory on and off, the reach picker's
settings, and what the composer shows. No model is loaded: the reader and embedder are the fakes from test_core (they
need MLX for their small arrays), and attention is watched by a fake that gives every word the same looks."""

from __future__ import annotations

import datetime as dt
import http.client
import json
import socket
import threading

import numpy as np
import pytest

from camr_engine.app import measuring
from camr_engine.app.server import make_server

pytest.importorskip("mlx")

TODAY = dt.date(2026, 1, 20)


class FakeLooks:
    """Stands in for camr_engine.events.Looks (which needs a real Qwen3): the first node on the desk draws half of every
    word's attention, the others a little each."""

    def __init__(self, reader, header, spans, prompt_len, desk, layers=None):
        self.nodes = sorted({n for n, _, _ in spans})

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def per_word(self, words: int) -> np.ndarray:
        a = np.full((words, len(self.nodes)), 0.02, np.float32)
        if self.nodes:
            a[:, 0] = 0.5
        return a


@pytest.fixture
def looks(monkeypatch):
    import camr_engine.memory

    monkeypatch.setattr(camr_engine.memory, "Looks", FakeLooks)


class TalkApp:
    """An app with a (fake) reader and embedder, so the chat opens a real reach.Session under ``root``."""

    def __init__(self, root, reader=None):
        from test_core import FakeEmbedder, FakeReader

        self.reader, self.embedder = reader or FakeReader(), FakeEmbedder()
        self.reach_root = root
        self.session_settings = {"room_tokens": 400, "join": 0.2}
        self.session_name = "s1"
        self.today = TODAY
        self.lock = threading.Lock()

    def _day(self, d: dt.date) -> int:
        return (d - dt.date(2026, 1, 5)).days

    def state(self) -> dict:
        return {"moments": 0}


def serve(app):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    httpd, token = make_server(app, port)
    threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.05), daemon=True).start()

    def call(path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        headers = {"Host": f"127.0.0.1:{port}", "X-CAMR-Token": token}
        if body is not None:
            headers["Content-Type"] = "application/json"
        c.request("GET" if body is None else "POST", path, body=None if body is None else json.dumps(body),
                  headers=headers)
        r = c.getresponse()
        return r.status, json.loads(r.read() or b"null")

    return call, httpd


@pytest.fixture
def chat(tmp_path, looks, monkeypatch):
    monkeypatch.setenv("CAMR_MEASURING", str(tmp_path / "measuring.json"))
    app = TalkApp(tmp_path / "camr")
    call, httpd = serve(app)
    yield app, call
    httpd.shutdown()
    if getattr(app, "talk", None) is not None:
        app.talk.close()


def test_telling_keeps_a_moment_in_the_session_reach_and_asking_reads_the_best_reach(chat):
    app, call = chat
    status, st = call("/api/chat/state")
    assert status == 200 and st["ready"] and st["on"] and st["session"] == "s1"
    assert st["reads"] == ["session", "global"] and st["writes"] == "session"
    kinds = {r["kind"]: r for r in st["reaches"]}
    assert kinds["session"]["label"] == "session:s1" and kinds["session"]["read"] and kinds["session"]["written"]
    assert kinds["global"]["read"] and not kinds["global"]["written"] and kinds["project"]["label"] is None
    assert app.session is app.talk.session  # where the shell's /api/state finds the reaches

    status, told = call("/api/chat", {"text": "I asked for the invoice template today."})
    assert status == 200 and told["intent"] == "tell" and told["kept"] and told["reach"] == "session:s1"
    assert told["event"]["type"] == "remember" and told["event"]["moment"] == 0 and told["event"]["i"] == 0
    assert call("/api/chat/settings", {"writes": "global"})[1]["writes"] == "global"
    told = call("/api/chat", {"text": "Amina moved to Nakuru.", "intent": "tell"})[1]
    assert told["reach"] == "global"
    assert len(app.session.memory("global").rooms.moments) == 1
    assert len(app.session.memory("session").rooms.moments) == 1  # reopened: the session reach kept its moment

    status, got = call("/api/chat", {"text": "Where does Amina live now?"})
    assert status == 200 and got["intent"] == "ask" and got["reply"] == "ok" and got["on"]
    assert got["reach"] == "global" and got["words"] == ["o", "k"]
    e = got["event"]
    assert e["type"] == "answer" and e["reach"] == "global" and e["room"] == 0 and e["nodes"] == [0]
    assert e["used"] == [0] and e["tier"] == "ssd" and e["read_bytes"] > 0 and e["src"] == "global"
    m = got["metric"]
    told_tokens = len("[2026-01-20] I asked for the invoice template today.\n") + len(
        "[2026-01-20] Amina moved to Nakuru.\n")  # the fake tokenizer: one token per character
    assert m["reach"] == "global" and m["tier"] == "ssd" and m["context_tokens"] > 0
    assert m["history_tokens"] == told_tokens
    st = call("/api/chat/state")[1]
    assert st["last"]["context_tokens"] == m["context_tokens"]
    g = {r["kind"]: r for r in st["reaches"]}["global"]
    assert g["notes"] == 1 and g["room_bytes"] > 0 and g["moments"] == 1 and g["open"]
    assert st["history_tokens"] == sum(r["history_tokens"] for r in st["reaches"] if r["read"])


def test_memory_off_is_the_plain_model_keeping_nothing(chat):
    app, call = chat
    call("/api/chat", {"text": "Amina moved to Nakuru.", "intent": "tell"})
    st = call("/api/chat/settings", {"on": False})[1]
    assert st["on"] is False and app.session.on is False
    told = call("/api/chat", {"text": "Something said while memory was off."})[1]
    assert told["kept"] is False and told["on"] is False
    assert len(app.session.memory().rooms.moments) == 1
    got = call("/api/chat", {"text": "Where does Amina live?"})[1]
    assert got["on"] is False and "event" not in got and got["metric"]["tier"] is None
    assert got["metric"]["read_bytes"] == 0 and app.reader.calls[-1].cache is None
    assert call("/api/chat/settings", {"on": True})[1]["on"] is True


def test_the_reach_picker_reads_several_reaches_and_writes_one(chat, tmp_path):
    app, call = chat
    call("/api/chat", {"text": "The invoice template is the blue one.", "intent": "tell"})
    assert call("/api/chat/settings", {"reads": ["session", "project"]})[0] == 400  # a project needs its name
    assert call("/api/chat/settings", {"reads": ["team"]})[0] == 400
    assert call("/api/chat/settings", {"project": "../etc", "reads": ["project"]})[0] == 400
    assert call("/api/chat/settings", {"reads": "global"})[0] == 400
    st = call("/api/chat/settings", {"project": "tally", "reads": ["session", "project", "global"],
                                      "writes": "project"})[1]
    assert st["reads"] == ["session", "project", "global"] and st["writes"] == "project" and st["project"] == "tally"
    assert [r.label for r in app.session.reaches] == ["session:s1", "project:tally", "global"]
    assert app.session.home.label == "project:tally"
    told = call("/api/chat", {"text": "The fee is 1% rounded up to the next 5 shillings.", "intent": "tell"})[1]
    assert told["reach"] == "project:tally" and (tmp_path / "camr" / "project" / "tally" / "index.json").exists()
    assert len(app.session.memory("session").rooms.moments) == 1
    st = call("/api/chat/settings", {"reads": ["global"], "writes": "global"})[1]
    assert st["reads"] == ["global"] and [r.label for r in app.session.reaches] == ["global"]
    st = call("/api/chat/state")[1]
    project = {r["kind"]: r for r in st["reaches"]}["project"]
    assert not project["read"] and not project["open"] and project["moments"] == 1 and project["room_bytes"] > 0
    assert st["projects"] == ["tally"]
    # the written reach is always read
    assert call("/api/chat/settings", {"reads": ["global"], "writes": "session"})[1]["reads"] == ["session", "global"]


def test_an_errand_makes_one_tool_call_and_logs_it_beside_its_answer(tmp_path, looks, monkeypatch):
    from test_core import FakeReader

    from camr_engine.models import Reply

    class ToolReader(FakeReader):
        def generate(self, ids, cache=None, max_tokens=None):
            super().generate(ids, cache, max_tokens)
            pieces = ['<tool_call>{"name": "book_ride", ', '"arguments": {"destination": "Nakuru"}}</tool_call>']
            return Reply("".join(pieces), 0.001, 100.0, len(ids), 2, pieces)

    monkeypatch.setenv("CAMR_MEASURING", str(tmp_path / "measuring.json"))
    app = TalkApp(tmp_path / "camr", reader=ToolReader())
    call, httpd = serve(app)
    try:
        call("/api/chat/settings", {"writes": "global"})
        call("/api/chat", {"text": "Amina moved to Nakuru.", "intent": "tell"})
        status, got = call("/api/errand", {"text": "Book me a ride to Amina's home."})
        assert status == 200 and got["intent"] == "errand" and got["tool"] == "book_ride"
        assert got["args"] == {"destination": "Nakuru"} and got["result"] == "Book ride: destination = Nakuru"
        assert got["event"]["type"] == "agent" and got["event"]["reach"] == "global"
        log = app.session.memory("global").log.read()
        assert [e["type"] for e in log][-2:] == ["agent", "tool"] and log[-1]["args"] == {"destination": "Nakuru"}
        assert app.reader.calls[-1].ids  # the tools went in after the notes
        turns = call("/api/chat/thread")[1]["turns"]
        assert [t["who"] for t in turns] == ["you", "camr", "you", "camr"] and turns[-1]["tool"] == "book_ride"
    finally:
        httpd.shutdown()
        app.talk.close()


def test_chat_waits_while_a_benchmark_measures(tmp_path, looks, monkeypatch):
    monkeypatch.setenv("CAMR_MEASURING", str(tmp_path / "measuring.json"))
    app = TalkApp(tmp_path / "camr")
    call, httpd = serve(app)
    try:
        with measuring.measuring("longhaul"):
            status, st = call("/api/chat/state")
            assert status == 200 and not st["ready"] and st["measuring"]["job"] == "longhaul"
            assert getattr(app, "session", None) is None  # nothing was opened: that reads with the model
            assert call("/api/chat", {"text": "Where?"})[0] == 409
        assert call("/api/chat/state")[1]["ready"]
    finally:
        httpd.shutdown()
        if getattr(app, "talk", None) is not None:
            app.talk.close()


def test_an_app_without_a_reader_keeps_its_own_chat_and_a_recorded_memory_refuses(tmp_path):
    from camr_engine.app.fixture import Fixture

    class StandIn:
        def state(self):
            return {"moments": 0}

        def chat(self, text):
            return {"reply": f"heard {text}"}

    call, httpd = serve(StandIn())
    try:
        assert call("/api/chat", {"text": "hello"}) == (200, {"reply": "heard hello"})
        st = call("/api/chat/state")[1]
        assert st["ready"] is False and st["can"] is False and st["reaches"] == []
        assert call("/api/chat/settings", {"on": False})[0] == 409
        assert call("/api/chat/thread")[1]["turns"] == []
    finally:
        httpd.shutdown()
    (tmp_path / "rec").mkdir()
    call, httpd = serve(Fixture(tmp_path / "rec"))
    try:
        assert call("/api/chat", {"text": "hello"})[0] == 409 and call("/api/errand", {"text": "go"})[0] == 409
    finally:
        httpd.shutdown()


def test_bad_input_is_refused(chat):
    _, call = chat
    assert call("/api/chat", {"text": "hello", "intent": "shout"})[0] == 400
    assert call("/api/chat", {"text": "   "}) == (200, {"reply": "", "intent": None})
    assert call("/api/chat/settings", {"writes": "team"})[0] == 400


def test_a_hot_room_read_by_one_request_and_joined_by_another_still_answers(chat):
    """With mlx_lm loaded, every thread has its own default MLX stream and each request is served on a new thread;
    the session's lazy arrays (a hot room joined with new notes) are made and used on the session's one thread."""
    pytest.importorskip("mlx_lm")
    import mlx_lm.generate  # noqa: F401 (what the real reader imports: it turns on per-thread default streams)

    app, call = chat
    call("/api/chat/settings", {"writes": "global"})
    call("/api/chat", {"text": "Amina moved to Nakuru.", "intent": "tell"})
    assert call("/api/chat", {"text": "Where does Amina live now?"})[1]["event"]["tier"] == "ssd"
    call("/api/chat", {"text": "Amina's dog is called Simba.", "intent": "tell"})  # joins the hot copy
    status, got = call("/api/chat", {"text": "What is Amina's dog called?"})
    assert status == 200 and "error" not in got and got["event"]["tier"] == "ram"


def test_a_message_waiting_for_the_model_is_said_in_the_session_open_when_it_gets_the_lock(chat):
    """The session is taken under the lock: a settings change that won the lock first may have closed the one before,
    and a step on a closed session would write to a reach its new owner no longer knows about."""
    app, call = chat
    assert call("/api/chat/state")[1]["ready"]
    t = app.talk
    got = {}
    with app.lock:  # the model is busy (another job, or a settings change that got the lock first)
        th = threading.Thread(target=lambda: got.update(r=call("/api/chat", {"text": "Amina moved to Nakuru.",
                                                                              "intent": "tell"})))
        th.start()
        th.join(0.3)
        assert th.is_alive()  # waiting for the lock
        t.run(t.session.close)  # what configure() does under the lock: the old session closes, a new one opens
        t.session = app.session = None
        t.reads, t.writes = ["global"], "global"
        t._open()
    th.join(10)
    status, told = got["r"]
    assert status == 200 and told["kept"] and told["reach"] == "global"
    assert len(app.session.memory("global").rooms.moments) == 1


def test_a_poll_never_waits_for_the_model_and_a_failed_open_is_tried_again_only_every_30_s(tmp_path, looks,
                                                                                         monkeypatch):
    import camr_engine.reach

    from camr_engine.app.routes import chat as chat_routes

    monkeypatch.setenv("CAMR_MEASURING", str(tmp_path / "measuring.json"))
    real = camr_engine.reach.Session
    tries = []

    def busy(*a, **kw):
        tries.append(1)
        raise camr_engine.reach.ReachBusy("another camr holds global")

    monkeypatch.setattr(camr_engine.reach, "Session", busy)
    app = TalkApp(tmp_path / "camr")
    call, httpd = serve(app)
    try:
        st = call("/api/chat/state")[1]
        assert not st["ready"] and "ReachBusy" in st["why"] and len(tries) == 1
        for path in ("/api/memory/feed", "/api/memory/stage", "/api/memory/summary", "/api/chat/state"):
            assert call(path)[0] == 200
        assert len(tries) == 1  # the polls did not open it again
        assert call("/api/chat", {"text": "Where?"})[0] == 409 and len(tries) == 2  # a send tries at once
        monkeypatch.setattr(camr_engine.reach, "Session", real)
        app.talk.failed -= chat_routes.RETRY_S + 1
        with app.lock:  # the model is busy: a poll answers at once and opens nothing
            assert call("/api/memory/feed")[0] == 200 and app.talk.session is None
        assert call("/api/chat/state")[1]["ready"] and app.talk.error is None
    finally:
        httpd.shutdown()
        app.talk.close()


def test_a_message_too_long_is_refused_whole_never_kept_cut(chat):
    app, call = chat
    from camr_engine.app.routes.chat import TEXT_MAX

    status, got = call("/api/chat", {"text": "x" * (TEXT_MAX + 1), "intent": "tell"})
    assert status == 413 and f"{TEXT_MAX:,}" in got["error"]
    assert call("/api/errand", {"text": "y" * (TEXT_MAX + 1)})[0] == 413
    assert call("/api/chat/thread")[1]["turns"] == []
    told = call("/api/chat", {"text": "z" * TEXT_MAX, "intent": "tell"})[1]
    assert told["kept"] and told["tokens"] == len(f"[{TODAY.isoformat()}] " + "z" * TEXT_MAX + "\n")


def test_a_message_started_now_reports_its_room_and_reply_live(chat):
    import time

    app, call = chat
    status, job = call("/api/chat/message", {"text": "Amina moved to Nakuru."})
    assert status == 200 and job["id"]
    events, n, done = [], 0, False
    for _ in range(200):
        got = call(f"/api/live?id={job['id']}&from={n}")[1]
        events += got["events"]
        n, done = got["next"], got["done"]
        if done:
            break
        time.sleep(0.02)
    assert done and events[0]["kind"] == "start" and events[-1]["kind"] == "done"
    assert events[-1]["intent"] == "tell" and events[-1]["kept"] and [e["i"] for e in events] == list(range(len(events)))
    job = call("/api/chat/message", {"text": "Where did Amina move?"})[1]
    for _ in range(200):
        got = call(f"/api/live?id={job['id']}")[1]
        if got["done"]:
            break
        time.sleep(0.02)
    kinds = [e["kind"] for e in got["events"]]
    assert "room" in kinds and kinds[-1] == "done" and got["events"][-1]["intent"] == "ask"
    room = next(e for e in got["events"] if e["kind"] == "room")
    assert room["reach"] == "session:s1" and room["tier"] in ("ram", "ssd", "vault")
    assert call("/api/live?id=nope")[0] == 404


def test_a_layer_probe_measures_only_while_a_live_listens():
    mx = pytest.importorskip("mlx.core")
    from camr_engine.live import BINS, Live, measuring_layers, probe, reporting, taken

    class Block:
        def __call__(self, x):
            return x * 2

    class Model:
        layers = [Block(), Block(), Block()]

        def __call__(self, x):
            for layer in self.layers:
                x = layer(x)
            return x

    m = Model()
    assert probe(m) == 3 and probe(m) == 3  # wrapped once
    x = mx.ones((1, 2, BINS * 2))
    with measuring_layers():
        m(x)
        assert taken() is None  # nobody listening
        with reporting(Live()):
            m(x)
            rows = taken()
    assert len(rows) == 3 and len(rows[0]) == BINS and rows[0][0] == 2.0 and rows[2][0] == 8.0


def test_shelves_keep_kinds_of_work_apart_and_a_question_reads_them_all(chat, tmp_path):
    import time

    app, call = chat
    call("/api/chat/state")  # the session opens
    st = call("/api/chat/settings", {"shelf": "auto"})[1]
    assert st["shelf"] == "auto" and [s["name"] for s in st["shelves"]] == ["projects", "coding", "research",
                                                                              "personal"]
    assert "project:coding" in [r.label for r in app.session.reaches]
    told = call("/api/chat", {"text": "Fixed the bugs in the tests: split_bill errors on floats.",
                              "intent": "tell"})[1]
    assert told["shelf"] == "coding" and told["sorted"] and told["reach"] == "project:coding"
    told = call("/api/chat", {"text": "My family plans: birthdays and travel home.", "intent": "tell"})[1]
    assert told["shelf"] == "personal"
    job = call("/api/chat/message", {"text": "Amina's paper found memory beats long windows past 1M tokens.",
                                     "intent": "tell", "shelf": "research"})[1]
    for _ in range(200):
        got = call(f"/api/live?id={job['id']}")[1]
        if got["done"]:
            break
        time.sleep(0.02)
    assert got["events"][-1]["shelf"] == "research" and got["events"][-1]["sorted"] is False
    assert call("/api/chat/message", {"text": "x", "shelf": "kitchen"})[0] == 400
    asked = call("/api/chat", {"text": "Which errors did split_bill have?", "intent": "ask"})[1]
    assert asked["reach"] == "project:coding"  # read across every shelf: the closest note wins
    shelves = {s["name"]: s for s in call("/api/chat/state")[1]["shelves"]}
    assert shelves["coding"]["moments"] == 1 and shelves["personal"]["moments"] == 1
    assert (tmp_path / "camr" / "project" / "research" / "index.json").exists()
    warm = call("/api/live?id=warm")[1]
    assert warm["done"] and warm["events"][-1]["kind"] == "done"
    assert any(e["kind"] == "warmed" for e in warm["events"])
    call("/api/chat/settings", {"shelf": None})
    assert "project:coding" not in [r.label for r in app.session.reaches]  # shelves off: only the reaches picked
