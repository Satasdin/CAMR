"""The Code and Swarm screens' routes, through the real server with a stand-in app and a scripted brain (no model).
A workspace is chosen and checked, files open and save inside it only, a run waits for the person before any
command, the approval must be an exact yes from the page, a saved fix to the agent's code is marked and told to the
next run, and a swarm reports every agent."""

from __future__ import annotations

import http.client
import json
import socket
import threading
import time

import pytest

from camr_engine.app import measuring
from camr_engine.app.server import make_server
from test_agentic import FakeBrain, call as tool_call


class StandIn:
    def __init__(self, root, replies=None):
        self.agentic_root = root / "code"
        self.skills_dir = root / "skills"
        self.lock = threading.Lock()
        self.made: list[dict] = []
        self.brains: list[FakeBrain] = []
        self.replies = replies if replies is not None else []

        def brains(spec):
            self.made.append(spec)
            self.brains.append(FakeBrain(list(self.replies), memory=spec["memory"]))
            return self.brains[-1]

        self.brain_factory = brains

    def state(self):
        return {"moments": 0}


def serve(app):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    httpd, token = make_server(app, port)
    threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.05), daemon=True).start()

    def api(path, body=None, *, token_=token, extra=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        headers = {"Host": f"127.0.0.1:{port}", "X-CAMR-Token": token_, **(extra or {})}
        if body is not None:
            headers["Content-Type"] = "application/json"
        c.request("GET" if body is None else "POST", path, body=None if body is None else json.dumps(body),
                  headers=headers)
        r = c.getresponse()
        return r.status, json.loads(r.read() or b"null")

    return api, httpd


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "kitchen"
    (root / "src").mkdir(parents=True)
    (root / "src" / "fees.py").write_text("def fee(amount):\n    return 10\n")
    return root


@pytest.fixture(autouse=True)
def no_measuring(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMR_MEASURING", str(tmp_path / "measuring.json"))


def wait_for(api, rid, until, limit=5.0):
    t = time.monotonic()
    while time.monotonic() - t < limit:
        status, snap = api(f"/api/code/run?id={rid}")
        assert status == 200
        if until(snap):
            return snap
        time.sleep(0.02)
    raise AssertionError(f"run {rid} never got there: {snap['state']}")


def test_a_workspace_is_chosen_checked_and_its_files_open_inside_it_only(tmp_path, project):
    api, httpd = serve(StandIn(tmp_path))
    status, s = api("/api/code/state")
    assert status == 200 and s["workspace"] is None and s["can_run"] == "choose a workspace first"
    assert [p["id"] for p in s["personas"]] == ["coder", "reviewer", "tester"] and s["persona"] == "coder"
    for bad in ["/", "relative", str(tmp_path / "missing")]:
        assert api("/api/code/workspace", {"path": bad})[0] == 400
    status, s = api("/api/code/workspace", {"path": str(project)})
    assert status == 200 and s["workspace"]["name"] == "kitchen" and s["recent"] == [str(project.resolve())]
    files = api("/api/code/files")[1]["files"]
    assert {"path": "src/fees.py", "dir": False, "size": 31, "secret": False} in files
    status, f = api("/api/code/file?path=src/fees.py")
    assert status == 200 and f["text"].startswith("def fee") and f["marks"] == {}
    for bad in ["../../etc/passwd", "/etc/passwd", "src/../../x"]:
        assert api(f"/api/code/file?path={bad}")[0] == 400
        assert api("/api/code/file", {"path": bad, "text": "x"})[0] == 400
    assert api("/api/code/file", {"path": "src/fees.py", "text": "x", "base": "stale"})[0] == 409
    status, saved = api("/api/code/file", {"path": "src/new.py", "text": "x = 1\n", "base": None})
    assert status == 200 and (project / "src" / "new.py").read_text() == "x = 1\n" and saved["fix"] is None
    httpd.shutdown()


def test_a_run_waits_for_an_exact_yes_before_its_command(tmp_path, project):
    app = StandIn(tmp_path, [tool_call("run_shell", command="echo hi > shell.txt"), "I ran it."])
    api, httpd = serve(app)
    api("/api/code/workspace", {"path": str(project)})
    tid = api("/api/code/thread", {"title": "try the shell"})[1]["id"]
    status, run = api("/api/code/run", {"thread": tid, "task": "Write hi to shell.txt"})
    assert status == 200 and run["state"] in ("queued", "thinking", "tool", "waiting")
    assert app.made[-1]["reads"] == ["session", "project", "global"] and app.made[-1]["project"] == "kitchen"
    snap = wait_for(api, run["id"], lambda s: s["waiting"])
    (ask,) = snap["waiting"]
    assert ask["what"]["command"] == "echo hi > shell.txt" and not (project / "shell.txt").exists()
    assert api("/api/code/state")[1]["waiting"][0]["id"] == ask["id"]
    for almost in ["true", 1, "yes", None]:
        assert api("/api/code/approve", {"id": ask["id"], "allow": almost})[0] == 400
    assert api("/api/code/approve", {"id": ask["id"], "allow": True}, token_="wrong")[0] == 403
    assert api("/api/code/approve", {"id": ask["id"], "allow": True}, extra={"Origin": "http://evil.example"})[0] == 403
    assert api("/api/code/approve", {"id": ask["id"], "allow": True},
               extra={"Sec-Fetch-Site": "cross-site"})[0] == 403
    assert api("/api/code/approve", {"id": "not-an-ask", "allow": True})[0] == 404
    assert not (project / "shell.txt").exists()
    status, got = api("/api/code/approve", {"id": ask["id"], "allow": True})
    assert status == 200 and got["decision"] == "allowed"
    snap = wait_for(api, run["id"], lambda s: s["state"] == "done")
    assert (project / "shell.txt").read_text() == "hi\n" and snap["answer"] == "I ran it."
    assert "hi" in "".join(snap["term"])
    more = api(f"/api/code/run?id={run['id']}&turns=3&term={snap['term_next']}")[1]
    assert more["turns_from"] == 3 and more["turns"] == snap["turns"][3:] and more["term"] == []
    assert api("/api/code/approve", {"id": ask["id"], "allow": True})[0] == 404  # one yes runs one command once
    thread = api(f"/api/code/thread?id={tid}")[1]
    assert thread["runs"][-1]["answer"] == "I ran it." and thread["live"] is None
    listed = api("/api/code/state")[1]["threads"][0]
    assert listed["id"] == tid and listed["last"]["state"] == "done" and "run_shell" in api(
        "/api/code/state")[1]["used_tools"]
    assert api("/api/code/run?id=nope")[0] == 404 and api("/api/code/thread?id=../x")[0] == 404
    httpd.shutdown()


def test_a_saved_fix_to_the_agents_code_is_marked_and_told_to_the_next_run(tmp_path, project):
    write = tool_call("write_file", path="src/total.py", content="def total(x):\n    return x + 1\n")
    app = StandIn(tmp_path, [write, "Wrote total()."])
    api, httpd = serve(app)
    api("/api/code/workspace", {"path": str(project)})
    tid = api("/api/code/thread", {})[1]["id"]
    rid = api("/api/code/run", {"thread": tid, "task": "Add total()"})[1]["id"]
    wait_for(api, rid, lambda s: s["state"] == "done")
    f = api("/api/code/file?path=src/total.py")[1]
    status, saved = api("/api/code/file", {"path": "src/total.py", "text": "def total(x):\n    return x + fee(x)\n",
                                           "base": f["sha"]})
    assert status == 200 and saved["marks"]["2"] == {"kind": "yours"} and saved["fix"].startswith("Your fix in "
                                                                                                    "src/total.py")
    assert api("/api/code/state")[1]["fixes"] == [saved["fix"]]
    rid = api("/api/code/run", {"thread": tid, "task": "Check total()"})[1]["id"]
    wait_for(api, rid, lambda s: s["state"] == "done")
    assert api("/api/code/state")[1]["fixes"] == []
    httpd.shutdown()


def test_memory_off_personas_settings_and_skills(tmp_path, project):
    app = StandIn(tmp_path, ["Nothing to do."])
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "style.md").write_text("# House style\nPlain words.\n")
    api, httpd = serve(app)
    api("/api/code/workspace", {"path": str(project)})
    s = api("/api/code/settings", {"memory": False, "persona": "reviewer"})[1]
    assert s["memory"] is False and s["persona"] == "reviewer" and s["skills"][0]["name"] == "style"
    assert api("/api/code/settings", {"persona": "nobody"})[0] == 404
    tid = api("/api/code/thread", {})[1]["id"]
    rid = api("/api/code/run", {"thread": tid, "task": "Review fees.py"})[1]["id"]
    wait_for(api, rid, lambda x: x["state"] == "done")
    assert app.made[-1]["memory"] is False and app.made[-1]["reads"] == ["project", "global"]
    assert api("/api/code/skill?name=style")[1]["text"] == "# House style\nPlain words."
    assert api("/api/code/skill?name=nope")[0] == 404
    status, got = api("/api/code/persona", {"id": "ops", "name": "Ops", "system": "Deploy.", "reads": ["agent"],
                                            "writes": "agent", "tools": ["read_file"]})
    assert status == 200 and got["saved"]["id"] == "ops" and "ops" in [p["id"] for p in got["personas"]]
    assert api("/api/code/persona", {"id": "BAD ID", "name": "x", "system": "s", "reads": ["agent"]})[0] == 400
    assert "ops" not in [p["id"] for p in api("/api/code/persona/delete", {"id": "ops"})[1]["personas"]]
    status, got = api("/api/code/mcp/add", {"name": "notes", "command": "python server.py", "env": {"K": "secret-v"}})
    assert status == 200 and got["servers"][0]["env"] == ["K"] and "secret-v" not in json.dumps(got)
    assert api("/api/code/mcp/add", {"name": "x", "command": "y", "env": {"K": 1}})[0] == 400
    assert api("/api/code/mcp/remove", {"name": "notes"})[1]["servers"] == []
    httpd.shutdown()


def test_no_run_starts_without_a_model_or_while_a_benchmark_measures(tmp_path, project):
    from camr_engine.app.fixture import Fixture

    (tmp_path / "rec").mkdir()
    fixture = Fixture(tmp_path / "rec")
    fixture.agentic_root = tmp_path / "code-fixture"
    api, httpd = serve(fixture)
    api("/api/code/workspace", {"path": str(project)})
    tid = api("/api/code/thread", {})[1]["id"]
    status, got = api("/api/code/run", {"thread": tid, "task": "x"})
    assert status == 409 and "no model" in got["error"]
    assert api("/api/code/files")[0] == 200  # the editor still works on a fixture
    assert api("/api/swarm/start", {"task": "x", "n": 2})[0] == 409
    httpd.shutdown()
    api, httpd = serve(StandIn(tmp_path))
    api("/api/code/workspace", {"path": str(project)})
    tid = api("/api/code/thread", {})[1]["id"]
    with measuring.measuring("longhaul"):
        status, got = api("/api/code/run", {"thread": tid, "task": "x"})
        assert status == 409 and "measuring (longhaul)" in got["error"]
        assert api("/api/swarm/start", {"task": "x", "n": 2})[0] == 409
    httpd.shutdown()


def test_a_swarm_starts_reports_every_agent_and_stops(tmp_path, project):
    app = StandIn(tmp_path, [tool_call("list_files"), "Done."])
    api, httpd = serve(app)
    status, s = api("/api/swarm/state")
    assert status == 200 and s["swarm"] is None and s["can_run"] is None
    api("/api/code/workspace", {"path": str(project)})
    status, snap = api("/api/swarm/start", {"task": "List the files", "n": 3})
    assert status == 200 and [a["label"] for a in snap["agents"]] == ["A1", "A2", "A3"]
    assert [m["agent"] for m in app.made] == ["swarm-a1", "swarm-a2", "swarm-a3"]
    assert all(m["writes"] == "agent" and m["reads"][0] == "agent" for m in app.made)
    assert api("/api/swarm/start", {"task": "again", "n": 2})[0] in (200, 409)
    t = time.monotonic()
    while api("/api/swarm/state")[1]["swarm"]["live"] and time.monotonic() - t < 5:
        time.sleep(0.02)
    snap = api("/api/swarm/state")[1]["swarm"]
    assert snap["done"] == snap["total"] and all(a["tokens"]["written"] > 0 for a in snap["agents"])
    assert api("/api/swarm/stop", {})[0] == 200
    assert api("/api/swarm/start", {"task": "", "n": 2})[0] == 400
    httpd.shutdown()


def test_looking_at_the_screens_leaves_no_folder_behind(tmp_path):
    app = StandIn(tmp_path)
    api, httpd = serve(app)
    assert api("/api/code/state")[0] == 200 and api("/api/swarm/state")[0] == 200 and api("/api/code/files")[0] == 200
    assert not app.agentic_root.exists()
    httpd.shutdown()


def test_the_persona_chosen_in_the_rack_runs_even_in_a_thread_made_as_another(tmp_path, project):
    write = tool_call("write_file", path="src/b.py", content="b = 1\n")
    app = StandIn(tmp_path, [write, "Reviewed."])
    api, httpd = serve(app)
    api("/api/code/workspace", {"path": str(project)})
    tid = api("/api/code/thread", {"persona": "coder"})[1]["id"]
    assert api(f"/api/code/thread?id={tid}")[1]["persona"] == "coder"
    api("/api/code/settings", {"persona": "reviewer"})
    rid = api("/api/code/run", {"thread": tid, "task": "Review fees.py"})[1]["id"]
    snap = wait_for(api, rid, lambda s: s["state"] == "done")
    assert snap["persona"] == "reviewer" and not (project / "src" / "b.py").exists()
    (wrote,) = [t for t in snap["turns"] if t["kind"] == "call"]
    assert not wrote["ok"] and "no tool 'write_file'" in wrote["text"]
    assert app.made[-1]["agent"] == "reviewer" and api(f"/api/code/thread?id={tid}")[1]["persona"] == "reviewer"
    rid = api("/api/code/run", {"thread": tid, "task": "Write b.py", "persona": "coder"})[1]["id"]
    wait_for(api, rid, lambda s: s["state"] == "done")
    assert (project / "src" / "b.py").read_text() == "b = 1\n"  # the page sends the rack's choice
    httpd.shutdown()


def test_a_saved_fix_is_kept_in_the_projects_memory_and_the_marks_survive_a_later_run(tmp_path, project):
    first = tool_call("write_file", path="src/total.py", content="def total(x):\n    return x + 1\n")
    app = StandIn(tmp_path, [first, "Wrote total()."])
    api, httpd = serve(app)
    api("/api/code/workspace", {"path": str(project)})
    tid = api("/api/code/thread", {})[1]["id"]
    rid = api("/api/code/run", {"thread": tid, "task": "Add total()"})[1]["id"]
    wait_for(api, rid, lambda s: s["state"] == "done")
    f = api("/api/code/file?path=src/total.py")[1]
    status, saved = api("/api/code/file", {"path": "src/total.py", "text": "def total(x):\n    return x + fee(x)\n",
                                           "base": f["sha"]})
    assert status == 200 and saved["kept"] == "project:kitchen"
    t = time.monotonic()
    while not any(b.kept for b, m in zip(app.brains, app.made) if m["reads"] == ["project"]) and \
            time.monotonic() - t < 5:
        time.sleep(0.02)
    (keeper,) = [b for b, m in zip(app.brains, app.made) if m["reads"] == ["project"]]
    assert keeper.kept == [saved["fix"]] and keeper.kept_to == "project" and keeper.closed
    assert app.made[-1]["writes"] == "project" and app.made[-1]["project"] == "kitchen"
    app.replies = [tool_call("write_file", path="src/other.py", content="x = 2\n"), "Wrote other.py."]
    rid = api("/api/code/run", {"thread": tid, "task": "Add other.py"})[1]["id"]
    wait_for(api, rid, lambda s: s["state"] == "done")
    assert api("/api/code/file?path=src/total.py")[1]["marks"]["2"] == {"kind": "yours"}  # one gutter, not two
    api("/api/code/settings", {"memory": False})
    f = api("/api/code/file?path=src/total.py")[1]
    status, saved = api("/api/code/file", {"path": "src/total.py", "text": "def total(x):\n    return x + 2 * fee(x)\n",
                                           "base": f["sha"]})
    assert status == 200 and saved["fix"] and saved["kept"] is None  # memory off: told to the next run only
    httpd.shutdown()


def test_a_chatty_command_never_swells_the_thread_file(tmp_path, project):
    from camr_engine.agentic.desk import TERM_FILED

    app = StandIn(tmp_path, [tool_call("run_shell", command="yes | head -c 3000000"), "Printed a lot."])
    api, httpd = serve(app)
    api("/api/code/workspace", {"path": str(project)})
    tid = api("/api/code/thread", {})[1]["id"]
    rid = api("/api/code/run", {"thread": tid, "task": "Print a lot"})[1]["id"]
    ask = wait_for(api, rid, lambda s: s["waiting"])["waiting"][0]
    time.sleep(0.8)  # as the page waits before "allow once" wakes
    api("/api/code/approve", {"id": ask["id"], "allow": True})
    snap = wait_for(api, rid, lambda s: s["state"] == "done")
    assert len("".join(snap["term"])) <= 200_000 and snap["term_cut"] > 2_000_000
    filed = api(f"/api/code/thread?id={tid}")[1]["runs"][-1]
    assert len("".join(filed["term"])) <= TERM_FILED + 100 and "left out" in filed["term"][0]
    path = app.agentic_root / "threads" / f"{tid}.json"
    assert path.stat().st_size < 200_000
    httpd.shutdown()


def test_a_workspace_may_not_hold_the_apps_own_folder(tmp_path, project):
    app = StandIn(tmp_path)
    api, httpd = serve(app)
    api("/api/code/state")
    status, got = api("/api/code/workspace", {"path": str(tmp_path)})  # holds tmp_path/code, the Desk's folder
    assert status == 400 and "own settings or memory" in got["error"]
    assert api("/api/code/workspace", {"path": str(project)})[0] == 200
    httpd.shutdown()
