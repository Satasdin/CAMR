"""The Memory screen's data: every reach's events and metrics merged into one feed the page polls, the stage's
snapshot (moments, rooms, layout, vault notes, the core and the hot shelf), and one room, moment or note for a sheet;
the same for a recorded memory, which is never written. No model is loaded (the fakes from test_core and test_app_chat)."""

from __future__ import annotations

import json
import re

import numpy as np
import pytest

from camr_engine.events import EventLog



@pytest.fixture
def live(tmp_path, monkeypatch):
    pytest.importorskip("mlx")
    from test_app_chat import FakeLooks, TalkApp, serve

    import camr_engine.memory

    monkeypatch.setattr(camr_engine.memory, "Looks", FakeLooks)
    monkeypatch.setenv("CAMR_MEASURING", str(tmp_path / "measuring.json"))
    app = TalkApp(tmp_path / "camr")
    call, httpd = serve(app)
    call("/api/chat", {"text": "I asked for the invoice template today.", "intent": "tell"})
    call("/api/chat/settings", {"writes": "global"})
    call("/api/chat", {"text": "Amina moved to Nakuru.", "intent": "tell"})
    call("/api/chat", {"text": "Amina's dog is called Simba.", "intent": "tell"})
    yield app, call
    httpd.shutdown()
    app.talk.close()


def test_the_feed_merges_every_reach_in_time_order_and_follows_each_from_its_cursor(live):
    app, call = live
    status, got = call("/api/memory/feed?tail=50")
    assert status == 200 and got["reaches"] == ["session:s1", "global"]
    kinds = [(e["type"], e["reach"]) for e in got["events"]]
    assert kinds == [("remember", "session:s1"), ("remember", "global"), ("remember", "global")]
    assert [e["at"] for e in got["events"]] == sorted(e["at"] for e in got["events"])
    assert got["ev"] == {"session:s1": 1, "global": 2} and got["mx"] == {"session:s1": 0, "global": 0}
    assert call("/api/memory/feed")[1]["events"] == []  # no cursor and no tail: from the end
    asked = call("/api/chat", {"text": "Where does Amina live now?"})[1]
    ev = ",".join(f"{k}@{v}" for k, v in got["ev"].items())
    mx = ",".join(f"{k}@{v}" for k, v in got["mx"].items())
    new = call(f"/api/memory/feed?ev={ev}&mx={mx}")[1]
    assert [(e["type"], e["reach"], e["i"]) for e in new["events"]] == [("answer", "global", 2)]
    assert new["events"][0]["i"] == asked["event"]["i"] and new["events"][0]["looks"] == asked["event"]["looks"]
    assert len(new["metrics"]) == 1 and new["metrics"][0]["reach"] == "global" and new["metrics"][0]["i"] == 0
    assert new["ev"]["global"] == 3 and new["mx"]["global"] == 1
    assert call("/api/memory/feed?ev=global@x")[0] == 400 and call("/api/memory/feed?ev=global")[0] == 400


def test_the_stage_snapshot_holds_each_reach_its_layout_notes_core_and_hot_shelf(live):
    app, call = live
    call("/api/chat", {"text": "Where does Amina live now?"})
    status, s = call("/api/memory/stage")
    assert status == 200 and s["session"] == "s1" and s["on"] is True and s["fixture"] is False
    session = app.session
    assert s["token_bytes"] == session.notebook.shape.token_bytes and s["layers"] == session.notebook.shape.layers
    assert s["header_tokens"] == session.notebook.p and s["watched"] == [12, 16, 20, 24]
    assert s["core"]["on"] is True and s["core"]["tokens"] == 0
    reaches = {r["label"]: r for r in s["reaches"]}
    assert list(reaches) == ["session:s1", "global"] and reaches["global"]["written"]
    g = reaches["global"]
    assert len(g["moments"]) == 2 and len(g["layout"]) == 2 and len(g["texts"]) == 2
    room, day, tokens, start = g["moments"][0]
    assert tokens == len("[2026-01-20] Amina moved to Nakuru.\n") and start == 0
    assert all(len(xy) == 2 and 0 <= xy[0] <= 1 for xy in g["layout"])
    assert g["stats"]["reads"] == {str(room): 1} and g["stats"]["answers"] == 1
    assert g["room_bytes"] == g["history_tokens"] * s["token_bytes"]
    assert len(g["notes"]) == 2 and g["notes"][0][0] == "global-000000" and g["doors"] is None
    rid = g["rooms"][0][0]
    assert g["rooms"][0][3] == 1  # read from the SSD and kept hot
    assert s["ram"]["hot"] == [{"reach": "global", "room": rid, "bytes": g["rooms"][0][1] * s["token_bytes"]}]
    assert s["ram"]["budget_bytes"] == 512 * 2**20 and s["ram"]["used_bytes"] >= s["ram"]["hot"][0]["bytes"]
    summary = call("/api/memory/summary")[1]
    assert summary["answers"] == 1 and sum(summary["tiers"].values()) == 1
    layout = json.loads((session.memory("global").path / "layout.json").read_text())
    assert layout["moments"] == 2  # the brain view's t-SNE, cached beside the rooms
    call("/api/chat", {"text": "Amina's cat is called Mosi.", "intent": "tell"})
    again = {r["label"]: r for r in call("/api/memory/stage")[1]["reaches"]}["global"]
    assert len(again["layout"]) == 3 and again["layout"][:2] == g["layout"]  # extended in RAM, not laid out again
    assert json.loads((session.memory("global").path / "layout.json").read_text())["moments"] == 2
    with_doors = call("/api/memory/stage?doors=1")[1]
    doors = {r["label"]: r for r in with_doors["reaches"]}["global"]["doors"]
    assert doors and all(a < b and w > 0 for a, b, w in doors)


def test_a_room_a_moment_and_a_note_open_for_their_sheets(live):
    app, call = live
    call("/api/chat", {"text": "Where does Amina live now?"})
    s = call("/api/memory/stage")[1]
    g = {r["label"]: r for r in s["reaches"]}["global"]
    rid = g["moments"][0][0]
    status, r = call(f"/api/memory/room?reach=global&id={rid}")
    assert status == 200 and r["reads"] == 1 and r["bytes"] == r["file_bytes"] > 0 and not r["asleep"]
    assert r["hot"] is True and r["moments"][0]["text"].endswith("Amina moved to Nakuru.")
    assert r["last_answer"] is not None and r["last_share"] == pytest.approx(sum(r["shares"].values()), abs=1e-3)
    assert call("/api/memory/room?reach=global&id=99")[0] == 404
    assert call("/api/memory/room?reach=project:none&id=0")[0] == 404
    status, m = call("/api/memory/moment?reach=global&id=1")
    assert status == 200 and m["text"].endswith("Simba.") and m["tokens"] > 0
    status, n = call("/api/memory/note?reach=global&id=global-000000")
    assert status == 200 and n["text"].strip().endswith("Amina moved to Nakuru.") and n["moment"] == 0
    if g["moments"][1][0] == rid:  # the two moments share a room, so their notes share a door
        assert [x["id"] for x in n["links"]] == ["global-000001"] and n["backlinks"][0]["id"] == "global-000001"
    for bad in ("../index", "..%2Findex", ".camr-index", "a/b"):
        assert call(f"/api/memory/note?reach=global&id={bad}")[0] in (400, 404), bad
    assert call("/api/memory/note?reach=global&id=global-999999")[0] == 404


@pytest.fixture
def recorded(tmp_path):
    folder = tmp_path / "rec"
    (folder / "vault").mkdir(parents=True)
    moments = [{"mid": i, "room": i // 2, "day": i, "text": f"moment {i} " + "x" * 200, "start": (i % 2) * 10,
                "tokens": 10} for i in range(6)]
    rooms = [{"rid": r, "members": [2 * r, 2 * r + 1], "tokens": 20} for r in range(3)]
    (folder / "index.json").write_text(json.dumps({"token_bytes": 8, "room_tokens": 512, "join": 0.8,
                                                   "moments": moments, "rooms": rooms}))
    rng = np.random.default_rng(0)
    np.save(folder / "vectors.npy", rng.normal(size=(6, 16)).astype(np.float32))
    for r in (0, 1):  # room 2 is asleep: its file is gone
        (folder / f"room-{r:06d}.notes").write_bytes(b"\0" * 160)
    notes = {f"project-x-{i:06d}": {"id": f"project-x-{i:06d}", "day": i, "room": i // 2, "moment": i,
                                    "strength": 1.0 - i / 10, "asleep": i >= 4, "tags": [], "pinned": False,
                                    "links": {f"project-x-{i ^ 1:06d}": 0.5}, "file": [0, 100]} for i in range(6)}
    (folder / "vault" / ".camr-index.json").write_text(json.dumps({"reach": "project:x", "notes": notes}))
    (folder / "vault" / "project-x-000000.md").write_text(
        "---\nid: project-x-000000\nday: 0\nlinks:\n  - \"[[project-x-000001]]\"\ndoors:\n  - 0.5\n---\nmoment 0\n")
    log = EventLog(folder / "events.jsonl")
    log.write("answer", question="where?", room=1, closest=[2, 3], nodes=[2, 3], share=[0.7, 0.3], used=[2],
              words=["Here"], looks=[[0.7, 0.3]], wait_s=0.07, seconds={"fetch": 0.01}, tier="ssd", read_bytes=160,
              asleep=False, reach="project:x")
    return folder


def test_a_recorded_memory_is_shown_whole_and_never_written(recorded):
    from test_app_chat import serve

    from camr_engine.app.fixture import Fixture

    before = sorted((p.name, p.stat().st_mtime_ns) for p in recorded.rglob("*"))
    call, httpd = serve(Fixture(recorded))
    try:
        status, s = call("/api/memory/stage?doors=1")
        assert status == 200 and s["fixture"] is True and s["header_tokens"] is None and s["ram"] is None
        (r,) = s["reaches"]
        assert r["label"] == "project:x" and r["written"] and len(r["layout"]) == 6
        assert [x[2] for x in r["rooms"]] == [0, 0, 1]  # asleep: no file
        assert r["room_bytes"] == 2 * 20 * 8 and r["history_tokens"] == 60
        assert r["stats"]["reads"] == {"1": 1} and r["stats"]["last_share"] == {"1": 1.0}
        assert len(r["texts"][0]) == 120 and len(r["notes"]) == 6 and r["notes"][4][4] == 1
        assert r["doors"] == [[0, 1, 0.5], [2, 3, 0.5], [4, 5, 0.5]]
        got = call("/api/memory/feed?tail=10")[1]
        assert got["events"][0]["reach"] == "project:x" and got["events"][0]["src"] == "project:x"
        room = call("/api/memory/room?reach=project:x&id=1")[1]
        assert room["reads"] == 1 and room["shares"] == {"2": 0.7, "3": 0.3} and room["doors"] == []
        assert call("/api/memory/room?reach=project:x&id=2")[1]["asleep"] is True
        n = call("/api/memory/note?reach=project:x&id=project-x-000000")[1]
        assert n["text"].strip() == "moment 0" and n["links"][0]["id"] == "project-x-000001"
        assert n["backlinks"][0]["id"] == "project-x-000001"
        assert call("/api/chat/settings", {"on": False})[0] == 409
    finally:
        httpd.shutdown()
    assert sorted((p.name, p.stat().st_mtime_ns) for p in recorded.rglob("*")) == before


def test_a_note_named_as_obsidian_allows_opens_and_a_path_never_does(recorded):
    from urllib.parse import quote

    from test_app_chat import serve

    from camr_engine.app.fixture import Fixture

    for name in ("Fee rule (draft)", "café", "Wanjiru's menu"):
        (recorded / "vault" / f"{name}.md").write_text(f"---\nid: {name}\n---\nabout {name}\n", encoding="utf-8")
    call, httpd = serve(Fixture(recorded))
    try:
        for name in ("Fee rule (draft)", "café", "Wanjiru's menu"):
            status, n = call(f"/api/memory/note?reach=project:x&id={quote(name)}")
            assert status == 200 and n["id"] == name and n["text"].strip() == f"about {name}", name
        for bad in ("../index", ".camr-index", "a/b", "a:b", "[[x]]", " padded", "x" * 201):
            assert call(f"/api/memory/note?reach=project:x&id={quote(bad)}")[0] == 400, bad
    finally:
        httpd.shutdown()


def test_a_big_live_memory_is_laid_out_once_per_size_and_cached_beside_its_rooms(tmp_path):
    from types import SimpleNamespace

    from camr_engine.app.routes import memory as mem

    n = mem.TSNE_MAX + 50
    rng = np.random.default_rng(0)
    rooms = SimpleNamespace(vectors=rng.normal(size=(n + 400, 8)).astype(np.float32))
    s = mem.Source("global", tmp_path, SimpleNamespace(rooms=rooms), True)
    app = SimpleNamespace()
    moments = [(i // 4, i, 10, 0, "m") for i in range(n)]
    xy = mem._layout(app, s, moments)
    assert len(xy) == n and json.loads((tmp_path / "layout.json").read_text()) == {"moments": n, "xy": xy}
    more = mem._layout(app, s, moments + [(n // 4, n, 10, 0, "m")] * 10)
    assert more[:n] == xy and len(more) == n + 10  # extended from the cache, not projected again
    far = [(i // 4, i, 10, 0, "m") for i in range(n + 400)]
    assert len(mem._layout(app, s, far)) == n + 400  # too far behind: projected again, and cached again
    assert json.loads((tmp_path / "layout.json").read_text())["moments"] == n + 400
    assert list(app._memory_layouts) == [str(tmp_path)]  # one layout per folder, never one per size
    assert not list(tmp_path.glob(".layout.json.*"))
