"""The app's server talks only to its own page: the right host, JSON from its own origin, and the launch secret.
Static files come only from the static folder, and every response carries the strict content security policy.
No model is loaded: a stand-in app answers."""

from __future__ import annotations

import http.client
import json
import os
import re
import socket
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from camr_engine.app.server import CSP, STATIC, make_server, static_file
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


def page_token(port) -> str:
    _, page, _ = call(port, "GET", "/", {"Host": f"127.0.0.1:{port}"})
    return re.search(r'<meta name="camr-token" content="([^"]+)"', page).group(1)


def test_only_the_served_page_can_use_the_api():
    port, _, httpd = start()
    host = {"Host": f"127.0.0.1:{port}"}
    status, page, _ = call(port, "GET", "/", host)
    token = re.search(r'<meta name="camr-token" content="([^"]+)"', page).group(1)
    assert status == 200 and len(token) > 20
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


def test_the_token_is_new_each_launch_and_never_in_a_script():
    a, ta, ha = start()
    b, tb, hb = start()
    assert page_token(a) == ta and page_token(b) == tb and ta != tb
    _, page, _ = call(a, "GET", "/", {"Host": f"127.0.0.1:{a}"})
    assert "__CAMR_TOKEN__" not in page
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", page, re.S)
    assert scripts and all(not s.strip() for s in scripts)  # no inline script: script-src 'self' holds
    assert ta not in (STATIC / "shell.js").read_text()
    # a token from another launch is refused
    assert call(a, "GET", "/api/state", {"Host": f"127.0.0.1:{a}", "X-CAMR-Token": tb})[0] == 403
    ha.shutdown()
    hb.shutdown()


def test_every_response_carries_the_strict_policy():
    port, token, httpd = start()
    host = {"Host": f"127.0.0.1:{port}"}
    for path, headers in [("/", host), ("/static/shell.js", host), ("/api/state", {**host, "X-CAMR-Token": token}),
                          ("/api/nothing", {**host, "X-CAMR-Token": token})]:
        _, _, h = call(port, "GET", path, headers)
        assert h["Content-Security-Policy"] == CSP
        assert h["X-Content-Type-Options"] == "nosniff"
        assert h["Cross-Origin-Resource-Policy"] == "same-origin"
    assert "script-src 'self';" in CSP and "unsafe-eval" not in CSP and "frame-ancestors 'none'" in CSP
    assert "connect-src 'self'" in CSP  # the page itself can never call Hugging Face or anything else
    httpd.shutdown()


def test_static_files_come_only_from_the_static_folder():
    port, _, httpd = start()
    host = {"Host": f"127.0.0.1:{port}"}
    status, body, h = call(port, "GET", "/static/shell.js", host)
    assert status == 200 and h["Content-Type"].startswith("text/javascript") and "mount" in body
    assert call(port, "GET", "/static/tokens.css", host)[2]["Content-Type"].startswith("text/css")
    font = "/static/vendor/@fontsource-variable/geist@5.3.0/files/geist-latin-wght-normal.woff2"
    assert call(port, "GET", font, host)[2]["Content-Type"] == "font/woff2"
    for bad in ["/static/../server.py", "/static/%2e%2e/server.py", "/static/vendor/../../server.py",
                "/static/..%2fserver.py", "/static//etc/passwd", "/static/%2fetc%2fpasswd", "/static/",
                "/static/index.html",            # the page is served only at /, with its token
                "/static/screens/README.md",     # not a type the app serves
                "/static/vendor/uplot@1.6.32/LICENSE", "/static/.DS_Store", "/static/a%00.js",
                "/static/nothing.js", "/server.py", "/etc/passwd"]:
        status, _, _ = call(port, "GET", bad, host)
        assert status == 404, bad
    httpd.shutdown()


def test_the_host_and_origin_checks_hold_for_static_files_too():
    port, _, httpd = start()
    host = {"Host": f"127.0.0.1:{port}"}
    assert call(port, "GET", "/static/shell.js", {"Host": f"evil.example:{port}"})[0] == 403
    assert call(port, "GET", "/static/shell.js", {"Host": "127.0.0.1:1"})[0] == 403
    assert call(port, "GET", "/static/shell.js", {**host, "Origin": "https://evil.example"})[0] == 403
    assert call(port, "GET", "/", {"Host": f"evil.example:{port}"})[0] == 403
    assert call(port, "GET", "/static/shell.js", {"Host": f"localhost:{port}"})[0] == 200
    httpd.shutdown()


def test_a_symlink_out_of_the_static_folder_is_refused(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "ok.js").write_text("export const ok = 1;")
    secret = tmp_path / "secret.js"
    secret.write_text("export const key = 'not for the page';")
    os.symlink(secret, static / "leak.js")
    assert static_file("ok.js", static) == (static / "ok.js").resolve()
    assert static_file("leak.js", static) is None
    assert static_file("../secret.js", static) is None
    assert static_file(str(secret), static) is None


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
    assert Path(STATIC / "index.html").read_text().count("__CAMR_TOKEN__") == 1


def test_an_engine_started_by_the_mac_app_never_puts_its_token_in_the_page(monkeypatch):
    monkeypatch.setenv("CAMR_TOKEN", "made-by-the-mac-app")
    port, token, httpd = start()
    host = {"Host": f"127.0.0.1:{port}"}
    try:
        status, page, _ = call(port, "GET", "/", host)
        assert token == "made-by-the-mac-app" and status == 200 and token not in page
        assert call(port, "GET", "/api/state", {**host, "X-CAMR-Token": token})[0] == 200
        assert call(port, "GET", "/api/state", host)[0] in (401, 403)
    finally:
        httpd.shutdown()
