"""The shell: the logs the page follows, the measuring flag, a recorded memory served read-only, and the static files
(vendored with their hashes, no colour outside tokens.css, every screen with its mount). No model is loaded."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import socket
import subprocess
import sys
import threading

import pytest

from engram.app import measuring
from engram.app.fixture import Fixture
from engram.app.server import STATIC, make_server
from engram.app.tail import Tail
from engram.events import EventLog


def serve(app):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    httpd, token = make_server(app, port)
    threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.05), daemon=True).start()

    def get(path, method="GET", body=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        headers = {"Host": f"127.0.0.1:{port}", "X-Engram-Token": token}
        if body is not None:
            headers["Content-Type"] = "application/json"
        c.request(method, path, body=None if body is None else json.dumps(body), headers=headers)
        r = c.getresponse()
        return r.status, json.loads(r.read() or b"null")

    return get, httpd


# -- following a log


def test_a_tail_reads_only_whole_new_lines_numbered_as_the_event_log_numbers_them(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    for i in range(5):
        log.write("remember", moment=i)
    tail = Tail(log.path)
    got = tail.read(None, tail=2)
    assert [e["moment"] for e in got["events"]] == [3, 4] and [e["i"] for e in got["events"]] == [3, 4]
    assert got["next"] == 5 and got["total"] == 5
    assert tail.read(5)["events"] == []
    with log.path.open("a") as f:  # a line still being written waits for its newline
        f.write('{"type":"answer","room":1')
    assert tail.read(5)["events"] == [] and tail.read(5)["next"] == 5
    with log.path.open("a") as f:
        f.write("}\n\n")
    got = tail.read(5)
    assert got["events"] == [{"type": "answer", "room": 1, "i": 5}] and got["next"] == 6
    numbered = {i: e for i, e in enumerate(log.read())}
    assert all(numbered[e["i"]]["type"] == e["type"] for e in tail.read(0)["events"])
    assert len(tail.read(0, limit=2)["events"]) == 2 and tail.read(0, limit=2)["next"] == 2


def test_a_log_that_shrank_is_read_again_from_the_start(tmp_path):
    path = tmp_path / "metrics.jsonl"
    path.write_text("".join(json.dumps({"n": i}) + "\n" for i in range(4)))
    tail = Tail(path)
    assert tail.read(0)["next"] == 4
    path.write_text(json.dumps({"n": 99}) + "\n")
    got = tail.read(0)
    assert got["total"] == 1 and got["events"][0]["n"] == 99
    assert Tail(tmp_path / "missing.jsonl").read(0) == {"next": 0, "total": 0, "events": []}


# -- the measuring flag


def test_the_measuring_flag_holds_only_while_its_process_lives(tmp_path, monkeypatch):
    monkeypatch.setenv("ENGRAM_MEASURING", str(tmp_path / "measuring.json"))
    assert measuring.active() is None
    with measuring.measuring("longhaul"):
        job = measuring.active()
        assert job["job"] == "longhaul" and job["pid"] == os.getpid()
    assert measuring.active() is None and not (tmp_path / "measuring.json").exists()
    dead = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"], capture_output=True, text=True)
    (tmp_path / "measuring.json").write_text(json.dumps({"job": "crashed", "pid": int(dead.stdout)}))
    assert measuring.active() is None  # a crashed run never leaves the app paused
    (tmp_path / "measuring.json").write_text("not json")
    assert measuring.active() is None


# -- a recorded memory, read-only


@pytest.fixture
def recorded(tmp_path):
    folder = tmp_path / "memory"
    folder.mkdir()
    moments = [{"mid": i, "room": i // 2, "day": i, "text": f"moment {i}", "start": 0, "tokens": 10} for i in range(4)]
    rooms = [{"rid": 0, "members": [0, 1], "tokens": 20}, {"rid": 1, "members": [2, 3], "tokens": 20}]
    (folder / "index.json").write_text(json.dumps({"token_bytes": 8, "room_tokens": 512, "join": 0.8,
                                                   "moments": moments, "rooms": rooms}))
    (folder / "layout.json").write_text(json.dumps({"moments": 4, "xy": [[0, 0], [0.1, 0.1], [1, 1], [0.9, 0.9]]}))
    log = EventLog(folder / "events.jsonl")
    log.write("remember", moment=3, room=1, day=3, tokens=10, new_room=False)
    log.write("answer", question="where?", room=1, closest=[2, 3], nodes=[2, 3], share=[0.7, 0.3], used=[2],
              words=["Here"], looks=[[0.7, 0.3]], wait_s=0.07, seconds={"fetch": 0.01}, tier="ssd",
              read_bytes=160, asleep=False)
    log.write("verdict", event=1, verdict="right", expected="here")
    (folder / "metrics.jsonl").write_text(json.dumps({"first_word_s": 0.07, "read_bytes": 160, "gbps": 3.1,
                                                      "retrieval_ms": {"fetch": 10.0, "total": 12.0}, "tier": "ssd",
                                                      "total_s": 0.2, "prefill_tps": None, "decode_tps": 200.0,
                                                      "read_share": 0.1, "context_tokens": 60,
                                                      "history_tokens": 40, "peak_ram_bytes": 10,
                                                      "peak_mlx_bytes": None, "disk_bytes": 100}) + "\n")
    return folder


def test_a_fixture_serves_its_logs_and_brain_and_refuses_to_talk(recorded, tmp_path, monkeypatch):
    monkeypatch.setenv("ENGRAM_MEASURING", str(tmp_path / "measuring.json"))
    get, httpd = serve(Fixture(recorded))
    status, state = get("/api/state")
    assert status == 200 and state["fixture"] is True and state["moments"] == 4 and state["rooms"] == 2
    assert state["measuring"] is None and state["route_errors"] == {} and state["model"] is None
    status, events = get("/api/events?tail=1")
    assert events["next"] == 3 and events["events"][0]["type"] == "verdict" and events["events"][0]["i"] == 2
    _, events = get("/api/events?after=0&limit=2")
    assert [e["type"] for e in events["events"]] == ["remember", "answer"] and events["next"] == 2
    _, metrics = get("/api/metrics?after=0")
    assert metrics["events"][0]["gbps"] == 3.1
    assert get("/api/metrics/summary")[1]["answers"] == 1
    _, brain = get("/api/brain")
    assert len(brain["moments"]) == 4 and brain["answers"][0]["verdict"] == "right" and brain["answers"][0]["id"] == 1
    assert get("/api/chat", "POST", {"text": "hello"})[0] == 409
    assert get("/api/events?after=x")[0] == 400
    with measuring.measuring("suite"):
        assert get("/api/state")[1]["measuring"]["job"] == "suite"
    httpd.shutdown()


def test_the_strip_reads_ram_and_disk_from_this_mac(recorded):
    get, httpd = serve(Fixture(recorded))
    status, now = get("/api/sys")
    assert status == 200
    assert {"total_bytes", "used_bytes", "process_bytes", "pressure", "disk"} <= set(now)
    if sys.platform == "darwin":
        assert now["total_bytes"] > now["used_bytes"] > 0 and now["process_bytes"] > 0
        assert now["pressure"] in ("normal", "tight", "critical") and now["disk"]["free_bytes"] > 0
    httpd.shutdown()


# -- the static files


def test_every_vendored_file_matches_its_lock():
    lock = json.loads((STATIC / "vendor" / "LOCK.json").read_text())
    assert lock["cutoff"] <= "2026-10-21T23:59:59Z" and lock["tree"] >= 40
    names = {f["path"] for f in lock["files"]}
    for want in ["ui.js", "regl.js", "codemirror.js", "markdown.js", "icons.js",
                 "uplot@1.6.32/dist/uPlot.esm.js", "@xterm/xterm@6.0.0/lib/xterm.mjs",
                 "@xterm/addon-fit@0.11.0/lib/addon-fit.mjs",
                 "@fontsource-variable/martian-mono@5.3.0/files/martian-mono-latin-standard-normal.woff2",
                 "@fontsource-variable/geist@5.3.0/files/geist-latin-wght-normal.woff2",
                 "@fontsource-variable/geist-mono@5.3.0/files/geist-mono-latin-wght-normal.woff2"]:
        assert want in names, want
    for f in lock["files"]:
        data = (STATIC / "vendor" / f["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == f["sha256"], f["path"]
        assert f["licence"], f["path"]
    for bundle, packages in lock["bundles"].items():
        assert packages and all(p["published"] <= lock["cutoff"] for p in packages), bundle
    pins = {p["name"]: p["version"] for ps in lock["bundles"].values() for p in ps}
    assert pins["preact"] == "10.29.8" and pins["regl"] == "2.1.1" and pins["markdown-it"] == "14.3.2"
    assert pins["@lezer/common"] == "1.5.3" and pins["@lezer/lr"] == "1.4.11"


def test_the_page_loads_nothing_from_beyond_this_mac():
    page = (STATIC / "index.html").read_text()
    for url in re.findall(r'(?:src|href)="([^"]+)"', page):
        assert url.startswith("/static/") or url.startswith("data:"), url
    for css in ["tokens.css", "app.css", "screens/models.css"]:
        for url in re.findall(r"url\(([^)]+)\)", (STATIC / css).read_text()):
            assert url.startswith("/static/vendor/") or url.startswith("#"), url
            if url.startswith("/static/"):
                assert (STATIC / url[len("/static/"):]).is_file(), url
    for js in [STATIC / "shell.js", *sorted((STATIC / "screens").glob("*.js"))]:
        text = js.read_text()
        assert "http://" not in text and "https://" not in text, js.name
        for imp in re.findall(r'from "([^"]+)"', text) + re.findall(r'import\("([^"]+)"', text):
            assert imp.startswith("/static/"), (js.name, imp)


def test_no_colour_lives_outside_the_tokens():
    colour = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|oklch\(")
    for path in [STATIC / "app.css", STATIC / "shell.js", *(STATIC / "screens").glob("*.js"),
                 *(STATIC / "screens").glob("*.css")]:
        text = re.sub(r"url\(#[^)]+\)", "", path.read_text())  # SVG paint servers are ids, not colours
        assert not colour.search(text), (path.name, colour.search(text).group(0))
    tokens = (STATIC / "tokens.css").read_text()
    for name, hexa in [("--ssd", "#28B8E5"), ("--ram", "#FFB75E"), ("--used", "#9DFFB3"), ("--vault", "#9D63E3"),
                       ("--fault", "#EE333E"), ("--select", "#FFFFFF")]:
        assert f"{name}:{hexa}" in tokens.replace(" ", ""), name


def test_every_screen_has_a_mount_and_the_contract_is_written_down():
    for name in ["models", "chat", "code", "swarm", "memory", "bench"]:
        text = (STATIC / "screens" / f"{name}.js").read_text()
        assert re.search(r"export (async )?function mount\(el, api\)", text), name
    readme = (STATIC / "screens" / "README.md").read_text()
    for word in ["mount(el, api)", "show()", "hide()", "key(", "api.get", "api.post", "api.on", "routes/"]:
        assert word in readme, word
    shell = (STATIC / "shell.js").read_text()
    for name in ["models", "chat", "code", "swarm", "memory", "bench"]:
        assert f'id: "{name}"' in shell
