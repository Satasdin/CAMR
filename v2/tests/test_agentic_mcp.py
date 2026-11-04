"""MCP servers over stdio with the official ``mcp`` package: a tiny server written here, started with this Python (no
network). Its tools reach the model under ``mcp__<server>__<tool>``, every call waits at the gate, a denied call
never reaches the server, and a server that will not start says why."""

from __future__ import annotations

import os
import sys
import threading
import time

import pytest

from camr_engine.agentic.gate import Gate
from camr_engine.agentic.servers import Servers, arguments, spec, split_name, tool_name
from camr_engine.agentic.tools import Toolbox

pytest.importorskip("mcp")

SERVER = '''
import sys
from pathlib import Path
from mcp.server.mcpserver import MCPServer

s = MCPServer("notes")
MARK = Path(sys.argv[1])

@s.tool()
def add_note(text: str, times: int = 1) -> str:
    """Keep a note."""
    MARK.write_text(text * times)
    return f"kept {text!r} x{times}"

s.run()
'''


@pytest.fixture
def servers(tmp_path):
    script = tmp_path / "server.py"
    script.write_text(SERVER)
    sv = Servers(tmp_path / "code" / "mcp.json", tmp_path / "code" / "logs")
    sv.add(spec("notes", f"{sys.executable} {script} {tmp_path / 'called.txt'}", {"NOTES_TOKEN": "t-not-real"}))
    yield sv
    sv.close()


def test_a_server_is_added_and_kept_privately_and_shows_no_secret(servers, tmp_path):
    p = tmp_path / "code" / "mcp.json"
    assert oct(p.stat().st_mode & 0o777) == "0o600"
    (shown,) = servers.show()
    assert shown["env"] == ["NOTES_TOKEN"] and "t-not-real" not in str(shown) and shown["state"] == "idle"
    assert Servers(p, tmp_path / "logs").show()[0]["args"][-1].endswith("called.txt")
    for bad in [("../x", "python"), ("ok", ""), ("ok", "'unclosed")]:
        with pytest.raises(ValueError):
            spec(*bad)
    with pytest.raises(ValueError):
        spec("ok", "python", {"BAD NAME": "x"})
    assert split_name(tool_name("notes", "add_note")) == ("notes", "add_note") and split_name("read_file") is None


def test_a_connected_servers_tools_run_only_when_allowed(servers, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    link = servers.connect("notes", tmp_path)
    assert link.state == "connected", link.error
    assert [t["name"] for t in link.tools] == ["add_note"]
    gate = Gate()
    box = Toolbox(None, gate, servers=servers)
    assert "mcp__notes__add_note" in box.names()
    called = tmp_path / "called.txt"
    out = {}

    def go():
        out["done"] = box.run("mcp__notes__add_note", {"text": "hi", "times": "2"}, owner="r1", label="t")

    th = threading.Thread(target=go)
    th.start()
    while not gate.waiting():
        time.sleep(0.01)
    (ask,) = gate.waiting()
    assert ask["kind"] == "mcp" and ask["what"] == {"server": "notes", "tool": "add_note",
                                                     "arguments": {"text": "hi", "times": 2}}
    assert not called.exists()
    gate.decide(ask["id"], False)
    th.join(10)
    assert not out["done"].ok and not called.exists()  # denied: the server never heard of it
    th = threading.Thread(target=go)
    th.start()
    while not gate.waiting():
        time.sleep(0.01)
    gate.decide(gate.waiting()[0]["id"], True)
    th.join(10)
    assert out["done"].ok and out["done"].text == "kept 'hi' x2" and called.read_text() == "hihi"
    servers.disconnect("notes")
    assert servers.show()[0]["state"] == "idle" and "mcp__notes__add_note" not in box.names()


def test_a_server_that_will_not_start_says_why(tmp_path):
    sv = Servers(tmp_path / "mcp.json", tmp_path / "logs")
    sv.add(spec("gone", "/nonexistent/server"))
    sv.add(spec("dies", f"{sys.executable} -c \"import sys; print('no such config', file=sys.stderr); sys.exit(2)\""))
    assert sv.connect("gone", tmp_path).state == "failed" and "No such file" in sv.show()[0]["error"]
    dies = sv.connect("dies", tmp_path)
    assert dies.state == "failed" and "no such config" in dies.error
    with pytest.raises(KeyError):
        sv.connect("missing", tmp_path)
    sv.remove("gone")
    assert [s["name"] for s in sv.show()] == ["dies"]


def test_arguments_follow_the_tools_schema():
    schema = {"properties": {"n": {"type": "integer"}, "x": {"type": "number"}, "on": {"type": "boolean"},
                             "tags": {"type": "array"}, "name": {"type": "string"}}}
    got = arguments(schema, {"n": "3", "x": "2.5", "on": "true", "tags": '["a"]', "name": "7"})
    assert got == {"n": 3, "x": 2.5, "on": True, "tags": ["a"], "name": "7"}
    assert arguments(schema, "not an object") == {}
    assert os.environ.get("NOTES_TOKEN") is None
