"""CAMR Personal web server: static app, JSON API, streamed chat, and local-only request checks."""

from __future__ import annotations

import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from camr.app.assistant import Assistant
from camr.app.server import App, make_handler
from camr.memory.embedder import HashingEmbedder
from test_app import FakeOllama


@pytest.fixture
def server(tmp_path):
    app = App(tmp_path, "http://127.0.0.1:11434")
    app.assistant = Assistant(tmp_path, model="tiny:1b", embedder=HashingEmbedder(384), session=FakeOllama(),
                              min_similarity=0.3)
    app.ollama_models = lambda: [{"name": "tiny:1b", "size_gb": 1.0, "parameters": "1B", "family": "x",
                                  "embedding": False}]
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield httpd.server_address[1]
    httpd.shutdown()
    app.assistant.close()


def call(port, method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    h = {"Content-Type": "application/json", **(headers or {})}
    c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
    r = c.getresponse()
    data = r.read().decode()
    return r.status, data


def test_serves_the_single_page_app_and_state(server):
    status, html = call(server, "GET", "/")
    assert status == 200 and "CAMR" in html and "app.js" in html
    status, js = call(server, "GET", "/app.js")
    assert status == 200 and "api/chat" in js
    status, st = call(server, "GET", "/api/state")
    st = json.loads(st)
    assert st["ollama"] and st["ready"] and st["settings"]["model"] == "tiny:1b"


def test_teach_chat_stream_feedback_memory_and_rename(server):
    assert json.loads(call(server, "POST", "/api/teach", {"text": "The office wifi password is orchid-42.",
                                                          "title": "Office"})[1])["notes"] == 1
    status, stream = call(server, "POST", "/api/chat", {"message": "What is the office wifi password?"})
    events = [json.loads(line[6:]) for line in stream.split("\n\n") if line.startswith("data: ")]
    kinds = [e["type"] for e in events]
    assert kinds[0] == "recall" and kinds[-1] == "done" and "token" in kinds
    assert events[0]["sources"] and events[0]["sources"][0]["title"] == "Office"  # memory shown before the answer
    turn = events[-1]["turn"]
    assert "orchid-42" in turn["answer"]
    conv = turn["conversation_id"]
    chats = json.loads(call(server, "GET", "/api/conversations")[1])
    assert chats[0]["id"] == conv and chats[0]["title"].startswith("What is the office")
    assert json.loads(call(server, "GET", f"/api/conversations/{conv}")[1])[0]["sources"]
    call(server, "PATCH", f"/api/conversations/{conv}", {"title": "Wifi"})
    assert json.loads(call(server, "GET", "/api/conversations")[1])[0]["title"] == "Wifi"
    call(server, "POST", "/api/feedback", {"turn_id": turn["turn_id"], "helpful": True})
    mem = json.loads(call(server, "GET", "/api/memory?kind=learned")[1])
    assert len(mem) == 1
    assert json.loads(call(server, "DELETE", f"/api/memory/{mem[0]['source_id']}")[1])["removed"] == 1
    status, body = call(server, "GET", "/api/export")
    assert status == 200 and "orchid" not in body  # metrics only by default


def test_file_teaching_via_base64(server):
    import base64

    data = base64.b64encode(b"# Recipes\nGrandma's chapati uses 3 cups of flour and warm water.").decode()
    assert json.loads(call(server, "POST", "/api/teach", {"filename": "recipes.md", "data_base64": data})[1])["notes"] >= 1


def test_refuses_foreign_hosts_and_cross_site_posts(server):
    assert call(server, "GET", "/api/state", headers={"Host": "evil.example"})[0] == 403  # DNS rebinding
    status, _ = call(server, "POST", "/api/teach", {"text": "x y z w"},
                     headers={"Origin": "https://evil.example"})
    assert status == 403


def test_path_traversal_falls_back_to_index(server):
    status, body = call(server, "GET", "/../../etc/passwd")
    assert status == 200 and "CAMR" in body


def test_empty_message_is_rejected_without_calling_the_model(server):
    status, stream = call(server, "POST", "/api/chat", {"message": "   "})
    events = [json.loads(line[6:]) for line in stream.split("\n\n") if line.startswith("data: ")]
    assert [e["type"] for e in events] == ["error"] and "empty message" in events[0]["error"]
    assert json.loads(call(server, "GET", "/api/conversations")[1]) == []  # no chat created
