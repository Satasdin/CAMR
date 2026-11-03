"""The app's server talks only to its own page: the right host, JSON from its own origin, and the launch secret.
No model is loaded: a stand-in app answers."""

from __future__ import annotations

import http.client
import json
import re
import socket
import threading
from types import SimpleNamespace

from engram.app.server import serve


class StandIn:
    memory = SimpleNamespace(rooms=SimpleNamespace(path="(a stand-in memory)"))

    def state(self):
        return {"moments": 0}

    def chat(self, text):
        return {"reply": "Noted."}


def start():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    threading.Thread(target=serve, args=(StandIn(), port), daemon=True).start()
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.05).close()
            break
        except OSError:
            pass
    return port


def call(port, method, path, headers=None, body=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse()
    return r.status, r.read().decode()


def test_only_the_served_page_can_use_the_api():
    port = start()
    host = {"Host": f"127.0.0.1:{port}"}
    status, page = call(port, "GET", "/", host)
    token = re.search(r'const TOKEN = "([^"]+)"', page).group(1)
    assert status == 200 and len(token) > 20
    ok = {**host, "X-Engram-Token": token}
    assert call(port, "GET", "/api/state", ok)[0] == 200
    assert call(port, "GET", "/api/state", host)[0] == 403                                  # no secret
    assert call(port, "GET", "/api/state", {**ok, "Host": f"evil.example:{port}"})[0] == 403  # DNS rebinding
    body = json.dumps({"text": "hello"})
    good_post = {**ok, "Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}"}
    assert call(port, "POST", "/api/chat", good_post, body)[0] == 200
    assert call(port, "POST", "/api/chat", {**good_post, "Content-Type": "text/plain"}, body)[0] == 403  # a form
    assert call(port, "POST", "/api/chat", {**good_post, "Origin": "https://evil.example"}, body)[0] == 403
