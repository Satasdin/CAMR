"""The OpenAI-compatible endpoint, against a stand-in backend and a stand-in memory: chats stream through byte for
byte with notes before the question, whole answers too, the exchange is remembered once the turn ends (not when it
ends by calling a tool), /v1/models passes through, and nothing outside /v1/ is served. No model is loaded."""

from __future__ import annotations

import http.client
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from camr_engine import cli
from camr_engine.pair.ollama import NOTES_END, NOTES_INTRO, make_server
from camr_engine.pair.openai import BACKENDS, PORT, Endpoint, build
from camr_engine.pair.provider import NoMemory, VaultWords

NOTE = "[2026-11-03 10:00] The user said: Mama Njeri's main colour is terracotta, #C2410C."
ANSWER = ["Terra", "cotta, ", "#C2410C ☕"]
MODELS = {"object": "list", "data": [{"id": "qwen3:1.7b", "object": "model", "created": 0, "owned_by": "library"}]}
CALL = {"index": 0, "id": "call_1", "type": "function", "function": {"name": "read", "arguments": '{"path": "a"}'}}


def sse(parts=ANSWER, finish="stop", tool=False) -> bytes:
    events = [{"id": "c1", "object": "chat.completion.chunk", "model": "fake",
               "choices": [{"index": 0, "delta": {"role": "assistant", "content": t}, "finish_reason": None}]}
              for t in parts]
    if tool:
        events.append({"id": "c1", "object": "chat.completion.chunk", "model": "fake",
                       "choices": [{"index": 0, "delta": {"tool_calls": [CALL]}, "finish_reason": None}]})
    events.append({"id": "c1", "object": "chat.completion.chunk", "model": "fake",
                   "choices": [{"index": 0, "delta": {}, "finish_reason": finish}]})
    return "".join(f"data: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events).encode() + b"data: [DONE]\n\n"


class FakeBackend:
    """Speaks enough of the OpenAI API (as Ollama, LM Studio and mlx_lm.server do), and keeps what it was sent. A
    request whose last message is the user's and whose tools are set is answered with a tool call."""

    def __init__(self):
        self.seen: list[tuple[str, str, dict, bytes]] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _send(self, code, body: bytes, kind="application/json", chunked=False):
                self.send_response(code)
                self.send_header("Content-Type", kind)
                if chunked:
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    for i in range(0, len(body), 61):  # cut at awkward places, inside characters too
                        piece = body[i:i + 61]
                        self.wfile.write(b"%x\r\n%s\r\n" % (len(piece), piece))
                        self.wfile.flush()
                    return self.wfile.write(b"0\r\n\r\n")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _any(self):
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                fake.seen.append((self.command, self.path, dict(self.headers), body))
                if self.path == "/v1/models":
                    return self._send(200, json.dumps(MODELS).encode())
                if self.path != "/v1/chat/completions":
                    return self._send(404, b'{"error": "not here"}')
                req = json.loads(body)
                calls = bool(req.get("tools")) and req["messages"][-1]["role"] == "user"
                if req.get("stream"):
                    return self._send(200, sse(["Let me look."] if calls else ANSWER,
                                               "tool_calls" if calls else "stop", calls), "text/event-stream", True)
                msg = {"role": "assistant", "content": "".join(ANSWER)}
                out = {"id": "c1", "object": "chat.completion", "model": req.get("model"),
                       "choices": [{"index": 0, "message": msg, "finish_reason": "stop"}],
                       "usage": {"prompt_tokens": 40, "completion_tokens": 6, "total_tokens": 46}}
                return self._send(200, json.dumps(out, ensure_ascii=False).encode())

            do_GET = do_POST = _any

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def last(self, path: str = "/v1/chat/completions") -> dict:
        return json.loads([s for s in self.seen if s[1] == path][-1][3])


class Notebook:
    def __init__(self):
        self.asked, self.kept = [], []

    def recall_text(self, query, budget_tokens):
        self.asked.append(query)
        return NOTE

    def remember(self, text, role):
        self.kept.append((role, text))


def start(backend="lmstudio", **kw):
    fake = FakeBackend()
    endpoint = Endpoint(Notebook(), backend, f"127.0.0.1:{fake.port}", **kw)
    httpd = make_server(endpoint, 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return fake, endpoint, httpd.server_address[1]


def call(port, method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    h = {"Host": f"127.0.0.1:{port}", "Authorization": "Bearer camr",
         **({"Content-Type": "application/json"} if body is not None else {}), **(headers or {})}
    c.request(method, path, body=body, headers=h)
    r = c.getresponse()
    out = r.status, r.read(), dict(r.getheaders())
    c.close()
    return out


def settle(ok) -> None:
    for _ in range(300):
        if ok():
            return
        time.sleep(0.01)


def chat(*msgs, **extra) -> bytes:
    return json.dumps({"model": "qwen3:1.7b", "messages": [m if isinstance(m, dict) else {"role": m[0], "content": m[1]}
                                                           for m in msgs], **extra}).encode()


# --- chats


def test_a_streamed_chat_comes_through_byte_for_byte_with_notes_before_the_question():
    fake, endpoint, port = start()
    status, out, headers = call(port, "POST", "/v1/chat/completions",
                                chat(("system", "Be brief."), ("user", "What is the main colour?"), stream=True))
    assert status == 200 and out == sse() and headers["Content-Type"] == "text/event-stream"
    assert headers["X-CAMR-Notes-Chars"] == str(len(NOTE))
    sent = fake.last()["messages"]
    assert sent[0] == {"role": "system", "content": "Be brief."}  # the client's system prompt is left alone
    assert sent[1]["content"] == f"{NOTES_INTRO}\n\n{NOTE}\n\n{NOTES_END}\n\nWhat is the main colour?"
    assert fake.seen[-1][2]["Authorization"] == "Bearer camr"  # passed on: LM Studio may check it
    settle(lambda: len(endpoint.provider.kept) >= 2)
    assert endpoint.provider.kept == [("user", "What is the main colour?"), ("assistant", "Terracotta, #C2410C ☕")]


def test_a_whole_answer_is_passed_on_and_remembered():
    fake, endpoint, port = start("ollama")
    status, out, _ = call(port, "POST", "/v1/chat/completions", chat(("user", "Main colour?")))
    assert status == 200 and json.loads(out)["choices"][0]["message"]["content"] == "Terracotta, #C2410C ☕"
    settle(lambda: len(endpoint.latest()) >= 1)
    assert endpoint.provider.kept[-1] == ("assistant", "Terracotta, #C2410C ☕")
    m = endpoint.latest()[-1]
    assert m["memory"] and m["model"] == "qwen3:1.7b" and m["prompt_tokens"] == 40 and m["completion_tokens"] == 6


def test_an_agent_turn_is_remembered_once_when_it_ends_not_at_each_tool_call():
    fake, endpoint, port = start()
    tools = [{"type": "function", "function": {"name": "read", "parameters": {"type": "object"}}}]
    ask = ("user", "Fix the colour in a.css")
    status, out, _ = call(port, "POST", "/v1/chat/completions", chat(ask, tools=tools, stream=True))
    assert status == 200 and b"tool_calls" in out
    time.sleep(0.1)
    assert endpoint.provider.kept == []  # it ended by calling a tool: the turn is not over
    step = {"role": "assistant", "content": "Let me look.", "tool_calls": [CALL]}
    result = {"role": "tool", "tool_call_id": "call_1", "content": "body { color: #000 }"}
    status, out, _ = call(port, "POST", "/v1/chat/completions", chat(ask, step, result, tools=tools, stream=True))
    assert status == 200 and out == sse()
    sent = fake.last()["messages"]
    assert sent[0]["content"].startswith(NOTES_INTRO) and sent[0]["content"].endswith("Fix the colour in a.css")
    assert sent[1:] == [step, result]  # the notes stay with the question through the tool loop
    settle(lambda: len(endpoint.provider.kept) >= 2)
    assert endpoint.provider.kept == [("user", "Fix the colour in a.css"), ("assistant", "Terracotta, #C2410C ☕")]


def test_models_pass_through_and_memory_can_be_turned_off_per_request():
    fake, endpoint, port = start()
    status, out, _ = call(port, "GET", "/v1/models")
    assert status == 200 and json.loads(out) == MODELS
    status, _, headers = call(port, "POST", "/v1/chat/completions", chat(("user", "Hi"), stream=True),
                              {"X-CAMR-Memory": "off"})
    assert status == 200 and fake.last()["messages"] == [{"role": "user", "content": "Hi"}]
    assert "X-CAMR-Notes-Chars" not in headers and endpoint.provider.asked == []


def test_nothing_outside_v1_is_served_and_a_missing_backend_is_named():
    fake, endpoint, port = start()
    for method, path in (("POST", "/api/chat"), ("GET", "/api/tags"), ("GET", "/"), ("POST", "/v2/chat")):
        assert call(port, method, path, b"{}" if method == "POST" else None)[0] == 404, path
    assert fake.seen == []
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        closed = s.getsockname()[1]
    httpd = make_server(Endpoint(Notebook(), "lmstudio", f"127.0.0.1:{closed}"), 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    status, out, _ = call(httpd.server_address[1], "GET", "/v1/models")
    assert status == 502 and json.loads(out)["error"] == f"LM Studio is not answering at 127.0.0.1:{closed}"


def test_a_web_page_never_reaches_memory_even_from_an_allowed_origin():
    fake, endpoint, port = start(allow_origins=("http://127.0.0.1:*",))
    assert call(port, "GET", "/v1/models", headers={"Origin": "http://127.0.0.1:5173"})[0] == 200
    body = chat(("user", "What is the main colour?"))
    for origin in ("http://127.0.0.1:5173", "https://evil.example"):
        for path in ("/v1/chat/completions", "/v1//chat/completions/", "/camr_engine/metrics"):
            assert call(port, "POST", path, body, {"Origin": origin})[0] == 403, path
    assert call(port, "GET", "/v1/models", headers={"Host": "evil.example"})[0] == 403  # DNS rebinding
    assert endpoint.provider.asked == [] and [s[1] for s in fake.seen] == ["/v1/models"]
    with pytest.raises(ValueError):
        Endpoint(NoMemory(), "ollama", "192.168.1.20:11434")  # notes never leave this Mac


# --- the command line


def test_the_command_line_picks_a_backend_without_loading_a_model(tmp_path):
    endpoint, port = build(["--memory", str(tmp_path)])
    assert port == PORT == 11436 and endpoint.backend == "ollama" and endpoint.upstream == "127.0.0.1:11434"
    assert isinstance(endpoint.provider, VaultWords) and endpoint.provider._embedder is None
    assert endpoint.provider.home == tmp_path / "ollama"  # the same notes as the Ollama pairing's
    assert endpoint.metrics_path == tmp_path / "openai" / "metrics.jsonl"
    for name, (_, where) in BACKENDS.items():
        assert build(["--backend", name, "--no-memory"])[0].upstream == where
    lm = build(["--backend", "lmstudio", "--upstream", "localhost:4321", "--port", "9000", "--no-memory"])
    assert lm[0].upstream == "localhost:4321" and lm[0].name == "LM Studio" and lm[1] == 9000
    assert lm[0].metrics_path is None
    with pytest.raises(ValueError):
        Endpoint(NoMemory(), "vllm")


def test_camr_dispatches_each_subcommand(monkeypatch, capsys):
    got = {}
    monkeypatch.setattr("camr_engine.pair.openai.main", lambda argv, prog: got.update(serve=(argv, prog)))
    monkeypatch.setattr("camr_engine.pair.ollama.main", lambda argv, prog: got.update(ollama=(argv, prog)))
    assert cli.main(["serve", "--backend", "lmstudio"]) == 0
    assert cli.main(["ollama", "--port", "11435"]) == 0
    assert got == {"serve": (["--backend", "lmstudio"], "camr serve"), "ollama": (["--port", "11435"], "camr ollama")}
    assert cli.main(["version"]) == 0 and "camr 0.0.1" in capsys.readouterr().out
    assert cli.main(["bench"]) == 0 and "records/bench" in capsys.readouterr().out
    assert cli.main([]) == 0 and "camr serve" in capsys.readouterr().out
    assert cli.main(["fly"]) == 2 and "no command 'fly'" in capsys.readouterr().err


def test_doctor_only_looks(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "LOCAL", (("Nothing here", 1, "/"),))
    monkeypatch.setattr(cli, "_cached", lambda repo: False)
    code = cli.doctor(["--memory", str(tmp_path)])
    out = capsys.readouterr().out
    assert "Listening on this Mac:" in out and "Nothing here, 127.0.0.1:1  (not running)" in out
    assert f"memory {tmp_path}" in out and "0 notes" in out and "downloaded on first use" in out
    assert code in (0, 1)  # 1 only off Apple silicon or without MLX


def test_the_package_installs_the_camr_command():
    import tomllib
    from pathlib import Path

    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())["project"]
    assert project["scripts"] == {"camr": "camr_engine.cli:main"}
