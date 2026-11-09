"""The engine talks only to the app that started it: the right host, JSON from its own origin, and the launch secret.
It serves nothing but its API, and every response carries the strict content security policy.
No model is loaded: a stand-in app answers."""

from __future__ import annotations

import http.client
import json
import socket
import threading
from types import SimpleNamespace

import pytest

from camr_engine.app.server import CSP, make_server
from camr_engine.app.web import Refused, Routes


class StandIn:
    memory = SimpleNamespace(rooms=SimpleNamespace(path="(a stand-in memory)"))

    def state(self):
        return {"moments": 0}

    def chat(self, text):
        return {"reply": "Noted."}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start(app=None, **kw):
    port = free_port()
    httpd, token = make_server(app or StandIn(), port, **kw)  # bound before the thread starts: no race
    threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.05), daemon=True).start()
    return port, token, httpd


def call(port, method, path, headers=None, body=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse()
    return r.status, r.read().decode(errors="replace"), dict(r.getheaders())


def test_only_the_holder_of_the_launch_token_can_use_the_api():
    port, token, httpd = start()
    host = {"Host": f"127.0.0.1:{port}"}
    assert len(token) > 20
    ok = {**host, "X-CAMR-Token": token}
    assert call(port, "GET", "/api/state", ok)[0] == 200
    assert call(port, "GET", "/api/state", host)[0] == 403                                  # no secret
    assert call(port, "GET", "/api/state", {**ok, "Host": f"evil.example:{port}"})[0] == 403  # DNS rebinding
    body = json.dumps({"text": "hello"})
    good_post = {**ok, "Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}"}
    assert call(port, "POST", "/api/chat", good_post, body)[0] == 200
    assert call(port, "POST", "/api/chat", {**good_post, "Content-Type": "text/plain"}, body)[0] == 403  # a form
    assert call(port, "POST", "/api/chat", {**good_post, "Origin": "https://evil.example"}, body)[0] == 403
    httpd.shutdown()


def test_the_token_is_new_each_launch_and_never_given_out():
    a, ta, ha = start()
    b, tb, hb = start()
    assert ta != tb
    for path in ["/", "/index.html", "/api/state"]:
        status, body, _ = call(a, "GET", path, {"Host": f"127.0.0.1:{a}"})
        assert status in (403, 404) and ta not in body, path
    # a token from another launch is refused
    assert call(a, "GET", "/api/state", {"Host": f"127.0.0.1:{a}", "X-CAMR-Token": tb})[0] == 403
    ha.shutdown()
    hb.shutdown()


def test_every_response_carries_the_strict_policy():
    port, token, httpd = start()
    host = {"Host": f"127.0.0.1:{port}"}
    for path, headers in [("/", host), ("/api/state", {**host, "X-CAMR-Token": token}),
                          ("/api/nothing", {**host, "X-CAMR-Token": token})]:
        _, _, h = call(port, "GET", path, headers)
        assert h["Content-Security-Policy"] == CSP
        assert h["X-Content-Type-Options"] == "nosniff"
        assert h["Cross-Origin-Resource-Policy"] == "same-origin"
    assert "default-src 'none'" in CSP and "frame-ancestors 'none'" in CSP
    httpd.shutdown()


def test_nothing_but_the_api_is_served():
    port, _, httpd = start()
    host = {"Host": f"127.0.0.1:{port}"}
    for bad in ["/", "/index.html", "/static/shell.js", "/static/../server.py", "/static/%2e%2e/server.py",
                "/server.py", "/etc/passwd"]:
        assert call(port, "GET", bad, host)[0] == 404, bad
    httpd.shutdown()


def test_the_host_and_origin_checks_hold_outside_the_api_too():
    port, _, httpd = start()
    host = {"Host": f"127.0.0.1:{port}"}
    assert call(port, "GET", "/", {"Host": f"evil.example:{port}"})[0] == 403
    assert call(port, "GET", "/", {"Host": "127.0.0.1:1"})[0] == 403
    assert call(port, "GET", "/", {**host, "Origin": "https://evil.example"})[0] == 403
    httpd.shutdown()


def test_api_requests_from_other_sites_and_bad_bodies_are_refused():
    port, token, httpd = start()
    ok = {"Host": f"127.0.0.1:{port}", "X-CAMR-Token": token}
    post = {**ok, "Content-Type": "application/json"}
    assert call(port, "GET", "/api/state", {**ok, "Sec-Fetch-Site": "cross-site"})[0] == 403
    assert call(port, "GET", "/api/state", {**ok, "Sec-Fetch-Site": "same-site"})[0] == 403
    assert call(port, "GET", "/api/state", {**ok, "Sec-Fetch-Site": "same-origin"})[0] == 200
    assert call(port, "POST", "/api/chat", post, "{not json")[0] == 400
    assert call(port, "POST", "/api/chat", post, "[1, 2]")[0] == 400
    assert call(port, "POST", "/api/chat", post, json.dumps({"text": "x" * (2 << 20)}))[0] == 413
    assert call(port, "POST", "/api/chat", {"Host": ok["Host"], "Content-Type": "application/json"}, "{}")[0] == 403
    assert call(port, "POST", "/api/nothing", post, "{}")[0] == 404
    assert call(port, "GET", "/api/nothing", ok)[0] == 404
    status, body, _ = call(port, "POST", "/api/life", post, "{}")  # a stand-in app has no lives to load
    assert status == 409 and "error" in json.loads(body)
    httpd.shutdown()


def test_a_route_reports_its_refusals_and_errors_as_json():
    routes = Routes()
    routes.add("GET", "/api/refuse", lambda req: (_ for _ in ()).throw(Refused(409, "busy")))
    routes.add("GET", "/api/break", lambda req: 1 / 0)
    routes.add("GET", "/api/echo", lambda req: {"n": req.int("n", 0, hi=10), "q": req.str("q")})
    port, token, httpd = start(routes=routes)
    ok = {"Host": f"127.0.0.1:{port}", "X-CAMR-Token": token}
    assert call(port, "GET", "/api/refuse", ok)[:2] == (409, json.dumps({"error": "busy"}))
    status, body, _ = call(port, "GET", "/api/break", ok)
    assert status == 500 and json.loads(body)["error"].startswith("ZeroDivisionError")
    assert json.loads(call(port, "GET", "/api/echo?n=99&q=hi", ok)[1]) == {"n": 10, "q": "hi"}
    assert call(port, "GET", "/api/echo?n=two", ok)[0] == 400
    httpd.shutdown()


def test_two_screens_cannot_answer_for_one_path():
    routes = Routes()
    routes.add("GET", "/api/x", lambda req: {}, "a")
    with pytest.raises(ValueError, match="twice"):
        routes.add("GET", "/api/x", lambda req: {}, "b")
    with pytest.raises(ValueError, match="/api/"):
        routes.add("GET", "/static/x", lambda req: {})


def test_the_server_listens_on_127_0_0_1_only():
    port, _, httpd = start()
    assert httpd.server_address[0] == "127.0.0.1"
    httpd.shutdown()


def test_every_route_module_loads(tmp_path):
    from camr_engine.app.routes import collect

    routes = collect()
    assert routes.errors == {}
    paths = {p for _, p in routes.table}
    for p in ["/api/state", "/api/sys", "/api/events", "/api/metrics", "/api/brain", "/api/chat", "/api/errand",
              "/api/models", "/api/models/search", "/api/models/load", "/api/sim/state", "/api/quiz"]:
        assert p in paths, p


def test_an_engine_started_by_the_mac_app_uses_the_token_it_was_given(monkeypatch):
    monkeypatch.setenv("CAMR_TOKEN", "made-by-the-mac-app")
    port, token, httpd = start()
    host = {"Host": f"127.0.0.1:{port}"}
    try:
        assert token == "made-by-the-mac-app"
        assert call(port, "GET", "/api/state", {**host, "X-CAMR-Token": token})[0] == 200
        assert call(port, "GET", "/api/state", host)[0] in (401, 403)
    finally:
        httpd.shutdown()
