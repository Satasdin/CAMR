"""The Ollama pairing, against a stand-in Ollama and a stand-in memory: answers stream through byte for byte, notes go
in at the front of the question, the exchange is remembered, and what a web page sends is refused. No model is
loaded."""

from __future__ import annotations

import datetime as dt
import http.client
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest

from camr_engine.pair.ollama import BUDGET, NOTES_END, NOTES_INTRO, Pairing, Tap, build, make_server
from camr_engine.pair.provider import QUERY_CHARS, UNDATED, NoMemory, VaultWords, clip, pieces
from camr_engine.vault import split

OWN_SYSTEM = "You are Fake, a model's own system prompt."
NOTE = "[2026-11-03 10:00] The user said: Mama Njeri's main colour is terracotta, #C2410C."
# The answer is cut at awkward places: mid-line and inside a two-byte and a three-byte character.
ANSWER = ["Hello", " there!", " café ☕"]


def ndjson(kind: str) -> list[bytes]:
    field = (lambda t: {"message": {"role": "assistant", "content": t}}) if kind == "chat" else \
        (lambda t: {"response": t})
    lines = [json.dumps({"model": "fake", **field(t), "done": False}, ensure_ascii=False) for t in ANSWER]
    lines.append(json.dumps({"model": "fake", **field(""), "done": True, "done_reason": "stop",
                             "total_duration": 300_000_000, "load_duration": 5_000_000, "prompt_eval_count": 12,
                             "prompt_eval_duration": 60_000_000, "eval_count": 3, "eval_duration": 150_000_000}))
    raw = ("\n".join(lines) + "\n").encode()
    a, b = raw.index("é".encode()) + 1, raw.index("☕".encode()) + 2
    return [raw[:20], raw[20:a], raw[a:b], raw[b:]]


def sse() -> list[bytes]:
    events = [{"id": "c1", "object": "chat.completion.chunk", "model": "fake",
               "choices": [{"index": 0, "delta": {"role": "assistant", "content": t}, "finish_reason": None}]}
              for t in ANSWER]
    events.append({"id": "c1", "object": "chat.completion.chunk", "model": "fake",
                   "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
    raw = "".join(f"data: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events).encode() + b"data: [DONE]\n\n"
    return [raw[:7], raw[7:150], raw[150:]]


class FakeOllama:
    """Speaks enough of Ollama's API for the pairing and the ollama CLI, and keeps every request it was sent."""

    def __init__(self):
        self.seen: list[tuple[str, str, dict, bytes]] = []  # method, path, headers, body
        self.gate: threading.Event | None = None  # when set up, a stream waits here after its first piece
        fake = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _plain(self, code, body: bytes, kind="application/json"):
                self.send_response(code)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)

            def _stream(self, chunks, kind):
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                for i, c in enumerate(chunks):
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(c), c))
                    self.wfile.flush()
                    if i == 0 and fake.gate is not None:
                        fake.gate.wait(5)
                self.wfile.write(b"0\r\n\r\n")

            def _any(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n)
                fake.seen.append((self.command, self.path, dict(self.headers), body))
                try:
                    req = json.loads(body) if body else {}
                except ValueError:
                    req = {}
                path = self.path.split("?")[0]
                if path == "/":
                    return self._plain(200, b"Ollama is running", "text/plain; charset=utf-8")
                if path == "/api/version":
                    return self._plain(200, b'{"version":"0.13.5"}')
                if path == "/api/tags":
                    return self._plain(200, json.dumps(TAGS).encode())
                if path == "/api/show":
                    return self._plain(200, json.dumps(SHOW).encode())
                if path in ("/api/chat", "/api/generate"):
                    kind = "chat" if path == "/api/chat" else "generate"
                    if kind == "chat" and not req.get("messages"):  # the CLI loading the model
                        return self._plain(200, json.dumps({"model": "fake", "done": True,
                                                            "done_reason": "load"}).encode())
                    if req.get("stream") is False:
                        whole = b"".join(ndjson(kind)).strip().split(b"\n")
                        out = {**json.loads(whole[-1]), **json.loads(whole[0])}
                        out.update(done=True, eval_count=3, eval_duration=150_000_000)
                        out["message" if kind == "chat" else "response"] = (
                            {"role": "assistant", "content": "".join(ANSWER)} if kind == "chat" else "".join(ANSWER))
                        return self._plain(200, json.dumps(out, ensure_ascii=False).encode())
                    return self._stream(ndjson(kind), "application/x-ndjson")
                if path == "/v1/chat/completions":
                    return self._stream(sse(), "text/event-stream")
                if path == "/api/delete":
                    return self._plain(200, b"")
                return self._plain(404, b"404 page not found", "text/plain")

            do_GET = do_POST = do_HEAD = do_DELETE = _any

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def last(self, path: str) -> dict:
        return json.loads([s for s in self.seen if s[1] == path][-1][3])


TAGS = {"models": [{"name": "fake:latest", "model": "fake:latest", "modified_at": "2026-11-04T00:00:00Z",
                    "size": 1000, "digest": "0" * 64, "details": {"format": "gguf", "family": "qwen3",
                                                                   "parameter_size": "1.7B",
                                                                   "quantization_level": "Q4_K_M"}}]}
SHOW = {"modelfile": "FROM fake", "parameters": "", "template": "{{ .Prompt }}", "system": OWN_SYSTEM,
        "details": TAGS["models"][0]["details"], "model_info": {"general.architecture": "qwen3"},
        "capabilities": ["completion"]}


class Notebook:
    """A stand-in memory: always the same note, and a list of what it was asked to keep."""

    def __init__(self, notes: str = NOTE):
        self.notes, self.asked, self.kept = notes, [], []

    def recall_text(self, query, budget_tokens):
        self.asked.append((query, budget_tokens))
        return self.notes

    def remember(self, text, role):
        self.kept.append((role, text))


class Broken(Notebook):
    def recall_text(self, query, budget_tokens):
        raise RuntimeError("the memory is unwell")


def start(provider=None, **kw):
    fake = FakeOllama()
    pairing = Pairing(provider if provider is not None else Notebook(), f"127.0.0.1:{fake.port}", **kw)
    httpd = make_server(pairing, 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return fake, pairing, httpd.server_address[1]


def call(port, method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    h = {"Host": f"127.0.0.1:{port}", **({"Content-Type": "application/json"} if body is not None else {}),
         **(headers or {})}
    c.request(method, path, body=body, headers={k: v for k, v in h.items() if v is not None})
    r = c.getresponse()
    out = r.status, r.read(), dict(r.getheaders())
    c.close()
    return out


def settle(ok) -> None:
    """Wait for ``ok()``: the exchange is remembered and measured just after the answer's last byte goes out."""
    for _ in range(300):
        if ok():
            return
        time.sleep(0.01)


def chat_body(*msgs, **extra) -> bytes:
    return json.dumps({"model": "fake", "messages": [{"role": r, "content": t} for r, t in msgs], **extra}).encode()


# --- streaming and notes


def test_a_chat_streams_through_byte_for_byte_with_notes_before_the_question():
    fake, pairing, port = start()
    status, body, headers = call(port, "POST", "/api/chat", chat_body(("user", "What is the main colour?")))
    assert status == 200 and body == b"".join(ndjson("chat"))
    assert headers["Content-Type"] == "application/x-ndjson"
    sent = fake.last("/api/chat")["messages"]
    # the notes open the question itself: no system message is added, so the model's own system prompt stays
    assert [m["role"] for m in sent] == ["user"]
    assert sent[0]["content"] == f"{NOTES_INTRO}\n\n{NOTE}\n\n{NOTES_END}\n\nWhat is the main colour?"
    assert not [s for s in fake.seen if s[1] == "/api/show"]
    assert pairing.provider.asked == [("What is the main colour?", BUDGET)]
    settle(lambda: len(pairing.latest()) >= 1)
    assert pairing.provider.kept == [("user", "What is the main colour?"), ("assistant", "Hello there! café ☕")]


def test_notes_open_the_last_user_message_and_the_history_is_left_as_it_was():
    fake, pairing, port = start()
    msgs = (("system", "Be brief."), ("user", "Hi"), ("assistant", "Hello."), ("user", "And the colour?"))
    assert call(port, "POST", "/api/chat", chat_body(*msgs))[0] == 200
    sent = fake.last("/api/chat")["messages"]
    # the roles stay, and everything before the question is sent as the client keeps it, so Ollama's prompt
    # cache still matches the last turn's prompt up to the previous question
    assert [m["role"] for m in sent] == ["system", "user", "assistant", "user"]
    assert sent[:3] == [{"role": r, "content": t} for r, t in msgs[:3]]
    assert sent[3]["content"].startswith(NOTES_INTRO) and sent[3]["content"].endswith("\n\nAnd the colour?")
    assert not [s for s in fake.seen if s[1] == "/api/show"]


def test_an_answer_is_passed_on_as_it_comes_not_held_back():
    fake, pairing, port = start()
    fake.gate = threading.Event()
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    c.request("POST", "/api/chat", chat_body(("user", "Hi")), {"Host": f"127.0.0.1:{port}"})
    r = c.getresponse()
    first = r.read1(1 << 16)  # arrives while the stand-in is still holding the rest of the answer
    assert first == ndjson("chat")[0]
    assert pairing.provider.kept == []  # nothing is remembered before the answer ends
    fake.gate.set()
    assert first + r.read() == b"".join(ndjson("chat"))
    c.close()


def test_generate_gets_the_notes_as_its_system_prompt():
    fake, pairing, port = start()
    body = json.dumps({"model": "fake", "prompt": "What is the main colour?"}).encode()
    status, out, _ = call(port, "POST", "/api/generate", body)
    assert status == 200 and out == b"".join(ndjson("generate"))
    assert fake.last("/api/generate")["system"] == f"{OWN_SYSTEM}\n\n{NOTES_INTRO}\n\n{NOTE}"
    settle(lambda: len(pairing.latest()) >= 1)
    assert pairing.provider.kept[-1] == ("assistant", "Hello there! café ☕")
    raw = json.dumps({"model": "fake", "prompt": "<|im_start|>user\nHi", "raw": True}).encode()
    call(port, "POST", "/api/generate", raw)
    assert [s for s in fake.seen if s[1] == "/api/generate"][-1][3] == raw  # a raw prompt has no place for notes


def test_the_openai_endpoint_streams_its_events_through_and_gets_notes():
    fake, pairing, port = start()
    body = json.dumps({"model": "fake", "stream": True, "messages": [
        {"role": "user", "content": [{"type": "text", "text": "What is the main colour?"}]}]}).encode()
    status, out, headers = call(port, "POST", "/v1/chat/completions", body)
    assert status == 200 and out == b"".join(sse()) and headers["Content-Type"] == "text/event-stream"
    sent = fake.last("/v1/chat/completions")["messages"]
    assert [m["role"] for m in sent] == ["user"]
    lead, question = sent[0]["content"]  # a text part of its own, in front of the client's parts
    assert lead == {"type": "text", "text": f"{NOTES_INTRO}\n\n{NOTE}\n\n{NOTES_END}"}
    assert question == {"type": "text", "text": "What is the main colour?"}
    settle(lambda: len(pairing.latest()) >= 1)
    assert pairing.provider.kept == [("user", "What is the main colour?"), ("assistant", "Hello there! café ☕")]


def test_a_whole_answer_without_streaming_is_remembered_too():
    fake, pairing, port = start()
    status, out, _ = call(port, "POST", "/api/chat", chat_body(("user", "Hi"), stream=False))
    assert status == 200 and json.loads(out)["message"]["content"] == "Hello there! café ☕"
    settle(lambda: len(pairing.latest()) >= 1)
    assert pairing.provider.kept[-1] == ("assistant", "Hello there! café ☕")


def test_a_chunked_request_body_is_read_and_still_gets_notes():
    fake, pairing, port = start()
    body = chat_body(("user", "What is the main colour?"))
    with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
        s.sendall(f"POST /api/chat HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Type: application/json\r\n"
                  f"Transfer-Encoding: chunked\r\n\r\n".encode())
        for part in (body[:10], body[10:]):
            s.sendall(b"%x\r\n%s\r\n" % (len(part), part))
        s.sendall(b"0\r\n\r\n")
        reply = b""
        while not reply.endswith(b"0\r\n\r\n"):
            reply += s.recv(65536)
    assert reply.startswith(b"HTTP/1.1 200")
    assert NOTE in fake.last("/api/chat")["messages"][0]["content"]


def test_two_requests_share_one_kept_alive_connection():
    fake, pairing, port = start()
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    socks = []
    for _ in range(2):
        c.request("POST", "/api/chat", chat_body(("user", "Hi")), {"Host": f"127.0.0.1:{port}"})
        r = c.getresponse()
        assert r.read() == b"".join(ndjson("chat")) and (r.getheader("Connection") or "").lower() != "close"
        socks.append(c.sock)
    assert socks[0] is not None and socks[1] is socks[0]  # http.client would have opened a new one after a close
    c.close()


# --- passthrough


def test_other_endpoints_pass_through_as_they_are():
    fake, pairing, port = start()
    assert call(port, "GET", "/api/tags")[1] == json.dumps(TAGS).encode()
    assert call(port, "GET", "/api/version")[1] == b'{"version":"0.13.5"}'
    show = json.dumps({"model": "fake"}).encode()
    assert call(port, "POST", "/api/show", show)[1] == json.dumps(SHOW).encode()
    assert fake.seen[-1][3] == show
    status, out, headers = call(port, "HEAD", "/")
    assert status == 200 and out == b"" and headers["Content-Length"] == "17"
    assert call(port, "GET", "/api/tags?x=1")[0] == 200 and fake.seen[-1][1] == "/api/tags?x=1"
    gone = json.dumps({"model": "old"}).encode()
    assert call(port, "DELETE", "/api/delete", gone)[0] == 200 and fake.seen[-1][:2] == ("DELETE", "/api/delete")
    assert fake.seen[-1][3] == gone
    assert call(port, "GET", "/nowhere")[:2] == (404, b"404 page not found")
    assert fake.seen[-1][2]["Host"] == f"127.0.0.1:{fake.port}"  # Ollama's own host check sees itself
    assert pairing.provider.asked == []


def test_memory_can_be_turned_off_per_request_and_a_load_request_is_left_alone():
    fake, pairing, port = start()
    body = chat_body(("user", "Hi"))
    assert call(port, "POST", "/api/chat", body, {"X-CAMR-Memory": "off"})[1] == b"".join(ndjson("chat"))
    assert fake.seen[-1][3] == body and "X-CAMR-Memory" not in fake.seen[-1][2]
    settle(lambda: len(pairing.latest()) >= 1)
    off = pairing.latest()[-1]  # the baseline to compare against: Ollama's speeds, with no memory
    assert not off["memory"] and off["model"] == "fake" and off["decode_tps"] == 20.0 and off["prefill_tps"] == 200.0
    assert "recall_ms" not in off and "remember_ms" not in off
    load = json.dumps({"model": "fake"}).encode()  # what `ollama run` sends first, to load the model
    assert call(port, "POST", "/api/chat", load)[0] == 200 and fake.seen[-1][3] == load
    assert pairing.provider.asked == [] and pairing.provider.kept == []


def test_a_broken_memory_never_breaks_the_chat():
    fake, pairing, port = start(Broken())
    status, out, _ = call(port, "POST", "/api/chat", chat_body(("user", "Hi")))
    assert status == 200 and out == b"".join(ndjson("chat"))
    settle(lambda: len(pairing.latest()) >= 1)
    assert pairing.metrics[-1]["error"] == "recall: RuntimeError"


def test_a_missing_ollama_is_a_clear_error():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        closed = s.getsockname()[1]
    httpd = make_server(Pairing(Notebook(), f"127.0.0.1:{closed}"), 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    status, out, _ = call(httpd.server_address[1], "GET", "/api/tags")
    assert status == 502 and "not answering" in json.loads(out)["error"]


# --- security


def test_only_this_mac_and_never_a_web_page():
    fake, pairing, port = start(max_body=4096)
    before = len(fake.seen)
    body = chat_body(("user", "Hi"))
    assert call(port, "GET", "/api/tags", headers={"Host": f"evil.example:{port}"})[0] == 403  # DNS rebinding
    assert call(port, "GET", "/api/tags", headers={"Host": "127.0.0.1:11434"})[0] == 403
    for origin in ("https://evil.example", f"http://127.0.0.1:{port}", "null", "chrome-extension://abc"):
        assert call(port, "POST", "/api/chat", body, {"Origin": origin})[0] == 403
    assert call(port, "GET", "/api/tags", headers={"Sec-Fetch-Site": "cross-site"})[0] == 403  # an <img> tag
    assert call(port, "OPTIONS", "/api/chat", headers={"Origin": "https://evil.example"})[0] == 403  # preflight
    big = chat_body(("user", "x" * 5000))
    assert call(port, "POST", "/api/chat", big)[0] == 413
    assert len(fake.seen) == before  # none of it reached Ollama
    assert pairing.provider.asked == []
    assert call(port, "GET", "/api/tags", headers={"Sec-Fetch-Site": "same-site"})[0] == 403  # another local page
    assert call(port, "GET", "/api/tags", headers={"Sec-Fetch-Site": "none"})[0] == 200  # typed in the address bar
    # a local app's own server relaying its page's request (the Ollama app's model list does this)
    assert call(port, "GET", "/api/tags", headers={"Sec-Fetch-Site": "same-origin"})[0] == 200


def test_a_chunked_body_over_the_cap_is_refused():
    fake, pairing, port = start(max_body=64)
    with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
        s.sendall(f"POST /api/chat HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nTransfer-Encoding: chunked\r\n\r\n"
                  f"{100:x}\r\n".encode() + b"x" * 100 + b"\r\n0\r\n\r\n")
        assert s.recv(65536).startswith(b"HTTP/1.1 413")
    assert fake.seen == []


@pytest.mark.parametrize("size", [b"-1", b"+40", b"0x40", b" ", b"1_0", b"123456789"])
def test_a_chunk_size_that_is_not_plain_hex_is_refused_at_once(size):
    fake, pairing, port = start(max_body=64)
    with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
        s.sendall(f"POST /api/chat HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nTransfer-Encoding: chunked\r\n\r\n"
                  .encode() + size + b"\r\n" + b"x" * 200_000)  # and the client keeps the connection open
        t = time.perf_counter()
        assert s.recv(65536).startswith(b"HTTP/1.1 400")
        assert time.perf_counter() - t < 1.0  # not after reading until the client gives up
    assert fake.seen == []


def test_a_chunk_shorter_than_it_says_is_refused():
    fake, pairing, port = start()
    with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
        s.sendall(f"POST /api/chat HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nTransfer-Encoding: chunked\r\n\r\n"
                  "10\r\nonly eight\r\n0\r\n\r\n".encode())
        s.shutdown(socket.SHUT_WR)
        assert s.recv(65536).startswith(b"HTTP/1.1 400")
    assert fake.seen == []


def test_a_body_megabytes_over_the_cap_still_gets_its_413():
    fake, pairing, port = start(max_body=2**20)
    big = chat_body(("user", "x" * (6 * 2**20)))
    status, out, headers = call(port, "POST", "/api/chat", big)  # http.client sends it all before it reads
    assert status == 413 and "body over" in json.loads(out)["error"] and headers["Connection"] == "close"
    assert fake.seen == []


def test_an_allowed_origin_gets_in_and_the_proxy_listens_on_loopback_only():
    fake, pairing, port = start(allow_origins=("app://obsidian.md", "http://127.0.0.1:*"))
    assert call(port, "GET", "/api/tags", headers={"Origin": "app://obsidian.md"})[0] == 200
    show = json.dumps({"model": "fake"}).encode()
    assert call(port, "POST", "/api/show", show, {"Origin": "http://127.0.0.1:61889"})[0] == 200
    # but never where memory is: any page on any local port could read the notes back through the answers
    before = len(fake.seen)
    body = chat_body(("user", "What is the main colour?"))
    for origin in ("http://127.0.0.1:61889", "app://obsidian.md"):
        for path in ("/api/chat", "/api/generate", "/v1/chat/completions", "/api/chat/", "//api//chat",
                     "/api/%63hat", "/camr_engine/metrics"):
            assert call(port, "POST", path, body, {"Origin": origin})[0] == 403, path
        assert call(port, "GET", "/camr_engine/metrics", headers={"Origin": origin})[0] == 403
        assert call(port, "OPTIONS", "/api/chat", headers={"Origin": origin})[0] == 403  # the preflight too
    assert len(fake.seen) == before and pairing.provider.asked == []
    for origin in ("http://127.0.0.1:80.evil.example", "http://127.0.0.1.evil.example", "http://127.0.0.1:",
                   "https://127.0.0.1:443"):
        assert call(port, "POST", "/api/show", show, {"Origin": origin})[0] == 403
    httpd = make_server(Pairing(NoMemory()), 0)
    assert httpd.server_address[0] == "127.0.0.1"
    httpd.server_close()
    with pytest.raises(ValueError):
        Pairing(NoMemory(), "192.168.1.20:11434")  # notes never leave this Mac
    assert Pairing(NoMemory(), "http://localhost").upstream == "localhost:11434"


# --- measurements


def test_each_request_is_measured_with_ollamas_own_speeds(tmp_path):
    fake, pairing, port = start(metrics_path=tmp_path / "metrics.jsonl")
    status, _, headers = call(port, "POST", "/api/chat", chat_body(("user", "Hi")))
    assert float(headers["X-CAMR-Added-Ms"]) >= 0 and headers["X-CAMR-Notes-Chars"] == str(len(NOTE))
    settle(lambda: len(pairing.latest()) >= 1)
    m = json.loads(call(port, "GET", "/camr_engine/metrics")[1])["requests"][0]
    assert m["path"] == "/api/chat" and m["model"] == "fake" and m["status"] == 200 and m["memory"]
    assert m["decode_tps"] == 20.0 and m["prefill_tps"] == 200.0 and m["eval_count"] == 3
    assert m["ollama_load_ms"] == 5.0 and m["ollama_total_ms"] == 300.0  # Ollama's own clock, kept apart
    assert m["total_ms"] >= m["first_byte_ms"] >= m["added_ms"] >= m["recall_ms"] >= 0
    assert m["upstream_first_byte_ms"] >= 0 and m["remember_ms"] >= 0 and m["bytes"] == len(b"".join(ndjson("chat")))
    assert json.loads((tmp_path / "metrics.jsonl").read_text().splitlines()[0]) == m
    assert "Hi" not in (tmp_path / "metrics.jsonl").read_text()  # measurements, never what was said


def test_the_tap_reads_every_format():
    t = Tap("openai")
    for c in sse():
        t.feed(c)
    t.close()
    assert t.done and t.answer == "Hello there! café ☕"
    t = Tap("generate")
    t.feed(b'{"response":"4","done":true,"eval_count":10,"eval_duration":500000000}')
    t.close()
    assert t.done and t.answer == "4" and t.stats()["decode_tps"] == 20.0


# --- the memory that ships: words in a folder, found by the embedder


class Words:
    """A stand-in embedder: hashed words, unit length."""

    name = "fake-words"

    def encode(self, texts, is_query=False):
        out = np.zeros((len(texts), 64), dtype=np.float32)
        for i, t in enumerate(texts):
            for w in re.findall(r"[a-z0-9]+", t.lower()):
                out[i, zlib.crc32(w.encode()) % 64] += 1
        return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)


class Recording(Words):
    """A stand-in embedder that keeps the length of every text it was given, one list per call."""

    def __init__(self):
        self.calls: list[list[int]] = []

    def encode(self, texts, is_query=False):
        self.calls.append([len(t) for t in texts])
        return super().encode(texts, is_query)


class Clock:
    def __init__(self):
        self.t = dt.datetime(2026, 11, 4, 9, 0)
        self.step = dt.timedelta(minutes=1)

    def __call__(self):
        self.t += self.step
        return self.t


def test_vault_words_recalls_the_closest_notes_in_the_order_they_were_told(tmp_path):
    v = VaultWords(tmp_path, Words(), clock=Clock())
    assert v.recall_text("anything", 100) == ""
    v.remember("The main colour is terracotta.", "user")
    v.remember("Wanjiru Kamau handles the catering orders.", "user")
    v.remember("Noted: terracotta it is.", "assistant")
    out = v.recall_text("what is the main colour", 1000)
    assert out.index("The user said: The main colour is terracotta.") < out.index("You answered: Noted: terracotta")
    assert v.recall_text("what is the main colour", 1000).startswith("[2026-11-04 09:01] The user said:")
    one = v.recall_text("what is the main colour", v.tokens(v._line(v.notes[0])))
    assert one == v._line(v.notes[0])  # the budget holds only the closest note
    assert v.recall_text("colour", 0) == "" and v.recall_text("   ", 100) == ""
    again = VaultWords(tmp_path, Words())
    assert [n["text"] for n in again.notes] == [n["text"] for n in v.notes] and again.vectors.shape == (3, 64)
    page = v.note_file(1).read_text()  # one note per piece, in the engine vault's format, for Obsidian
    meta, words = split(page)
    assert v.note_file(1).name == "ollama-000001.md" and words.strip() == "Wanjiru Kamau handles the catering orders."
    assert meta["id"] == "ollama-000001" and meta["date"] == "2026-11-04" and meta["time"] == "09:02"
    assert meta["tags"] == ["ollama", "user"] and meta["reach"] == "ollama"


def test_a_note_whose_file_a_person_deleted_is_never_recalled_and_an_edited_one_has_its_new_words(tmp_path):
    v = VaultWords(tmp_path, Words(), clock=Clock())
    v.remember("The main colour is terracotta.", "user")
    v.remember("The main colour is terracotta, said again.", "assistant")
    assert "said again" in v.recall_text("main colour", 1000)
    v.note_file(1).unlink()  # deleted in Obsidian
    assert v.recall_text("main colour", 1000) == "[2026-11-04 09:01] The user said: The main colour is terracotta."
    f = v.note_file(0)
    f.write_text(f.read_text().replace("terracotta.", "terracotta (the old one)."))  # edited by hand
    assert v.recall_text("main colour", 1000).endswith("The main colour is terracotta (the old one).")
    again = VaultWords(tmp_path, Words(), clock=Clock())
    assert "said again" not in again.recall_text("main colour", 1000)  # forgotten after a restart too
    again.remember("A new fact.", "user")
    assert again.note_file(2).exists() and v.note_file(1).exists() is False


def test_notes_from_both_memories_come_oldest_first_by_their_dates(tmp_path):
    # the app changed the colour on 5 Nov; a chat through Ollama on 3 Nov still had the old one
    moments = ["[2026-11-05] The main colour is now forest green, #166534.", "[2026-11-01] Paid the rent."]
    (tmp_path / "index.json").write_text(json.dumps({"moments": [{"text": t} for t in moments]}))
    np.save(tmp_path / "vectors.npy", Words().encode(moments))
    clock = Clock()
    clock.t = dt.datetime(2026, 11, 3, 10, 0)
    v = VaultWords(tmp_path, Words(), clock=clock, limit=2)
    v.remember("The main colour is terracotta.", "user")
    out = v.recall_text("what is the main colour", 1000)
    assert out == ("[2026-11-03 10:01] The user said: The main colour is terracotta.\n\n"
                   "[2026-11-05] The main colour is now forest green, #166534.")


def test_engine_moments_with_no_date_get_a_heading_of_their_own(tmp_path):
    moments = ["The main colour is now forest green.", "The main colour was once blue."]
    (tmp_path / "index.json").write_text(json.dumps({"moments": [{"text": t} for t in moments]}))
    np.save(tmp_path / "vectors.npy", Words().encode(moments))
    v = VaultWords(tmp_path, Words(), clock=Clock())
    assert v.recall_text("main colour", 1000) == "\n\n".join(moments)  # one memory alone: as they were told
    v.remember("The main colour is terracotta.", "user")
    out = v.recall_text("main colour", 1000).split("\n\n")
    assert out == ["[2026-11-04 09:01] The user said: The main colour is terracotta.", UNDATED, *moments]


def test_the_engine_memory_is_read_again_when_its_vectors_land_after_its_index(tmp_path):
    first = ["[2026-01-05] My sister Amina moved to Nakuru."]
    (tmp_path / "index.json").write_text(json.dumps({"moments": [{"text": t} for t in first]}))
    np.save(tmp_path / "vectors.npy", Words().encode(first))
    v = VaultWords(tmp_path, Words(), limit=1)
    assert "Amina" in v.recall_text("sister Amina", 500)
    both = first + ["[2026-01-06] The new kitchen opens on Moi Avenue."]
    (tmp_path / "index.json").write_text(json.dumps({"moments": [{"text": t} for t in both]}))  # Rooms.save: index,
    assert "Amina" in v.recall_text("kitchen Moi Avenue", 500)  # a recall lands here, between the two writes,
    np.save(tmp_path / "vectors.npy", Words().encode(both))  # then the vectors
    assert v.recall_text("kitchen Moi Avenue", 500) == both[1]
    (tmp_path / "vectors.npy").write_bytes(b"\x93NUMPY cut short")  # caught mid-write: what was read stays
    assert v.recall_text("kitchen Moi Avenue", 500) == both[1]


def test_what_goes_into_the_embedder_is_bounded(tmp_path):
    emb = Recording()
    v = VaultWords(tmp_path, emb, clock=Clock())
    pasted = "\n\n".join(f"Line {i} of a pasted file, with some words in it to make it long." for i in range(2000))
    left = v.remember(pasted + "\n\nExplain this file.", "user")
    assert len(emb.calls[-1]) == 16 and all(n <= 800 for n in emb.calls[-1])  # first 8 pieces and last 8
    assert left > 100_000 and v.notes[-1]["text"].endswith("Explain this file.")
    v.recall_text(pasted + "\n\nWhat does it do?", 500)
    assert emb.calls[-1] == [QUERY_CHARS]
    assert clip("short") == "short" and clip("a" * 5000).endswith("a" * 999) and len(clip("a" * 5000)) == QUERY_CHARS


def test_a_long_message_is_looked_up_by_its_ends_and_what_was_left_out_is_measured(tmp_path):
    fake, pairing, port = start(VaultWords(tmp_path, Recording(), clock=Clock()))
    pasted = "\n\n".join(f"Line {i} of a pasted file, with some words in it to make it long." for i in range(2000))
    status, _, _ = call(port, "POST", "/api/chat", chat_body(("user", pasted + "\n\nExplain this file.")))
    assert status == 200
    settle(lambda: len(pairing.latest()) >= 1)
    m = pairing.latest()[-1]
    assert m["query_cut"] and m["left_out_chars"] > 100_000 and "error" not in m
    assert max(n for call_ in pairing.provider.embedder.calls for n in call_) <= QUERY_CHARS


def test_a_chat_waits_for_the_exchange_before_it_to_be_remembered():
    events = []

    class Slow(Notebook):
        def recall_text(self, query, budget_tokens):
            events.append(("recall", query))
            return super().recall_text(query, budget_tokens)

        def remember(self, text, role):
            time.sleep(0.25)  # an embedder at work
            events.append(("remember", text))

    fake, pairing, port = start(Slow())
    t = time.perf_counter()
    assert call(port, "POST", "/api/chat", chat_body(("user", "The colour is terracotta.")))[0] == 200
    assert time.perf_counter() - t < 0.4  # the answer is not held back by remembering (0.5 s)
    assert call(port, "POST", "/api/chat", chat_body(("user", "What is the colour?")))[0] == 200
    settle(lambda: len(pairing.latest()) >= 2)
    assert events[:4] == [("recall", "The colour is terracotta."), ("remember", "The colour is terracotta."),
                          ("remember", "Hello there! café ☕"), ("recall", "What is the colour?")]
    second = [m for m in pairing.latest() if m["recall_ms"] >= m["wait_ms"] > 100]
    assert len(second) == 1  # the wait shows in the measurements, not hidden before the request was timed


def test_notes_from_another_embedder_are_refused_before_anything_is_written(tmp_path):
    v = VaultWords(tmp_path, Words(), clock=Clock())
    v.remember("The main colour is terracotta.", "user")
    sizes = {f.name: f.stat().st_size for f in (tmp_path / "ollama").rglob("*") if f.is_file()}

    class Other(Words):
        name = "another-embedder"

    class Narrow(Words):  # the same name, but fewer numbers per note
        def encode(self, texts, is_query=False):
            return super().encode(texts, is_query)[:, :32] * np.sqrt(2)

    for emb in (Other(), Narrow()):
        w = VaultWords(tmp_path, emb, clock=Clock())
        with pytest.raises(ValueError):
            w.remember("Second fact.", "user")
        assert {f.name: f.stat().st_size for f in (tmp_path / "ollama").rglob("*") if f.is_file()} == sizes
    with pytest.raises(ValueError, match="embedded by fake-words"):
        VaultWords(tmp_path, Other()).recall_text("main colour", 100)
    assert VaultWords(tmp_path, Words()).recall_text("main colour", 100).endswith("terracotta.")


def test_vault_words_searches_an_engine_memory_in_the_same_folder(tmp_path):
    moments = ["[2026-01-05] My sister Amina moved to Nakuru.", "[2026-01-06] Paid the electricity bill."]
    (tmp_path / "index.json").write_text(json.dumps({"token_bytes": 1, "moments": [{"text": t} for t in moments]}))
    np.save(tmp_path / "vectors.npy", Words().encode(moments))
    v = VaultWords(tmp_path, Words(), limit=1)
    assert v.recall_text("where does my sister Amina live", 500) == moments[0]
    np.save(tmp_path / "vectors.npy", np.ones((2, 8), dtype=np.float32) / np.sqrt(8))  # another embedder's
    os.utime(tmp_path / "index.json", (1, 1))
    assert v.recall_text("where does my sister live", 500) == ""


def test_vault_words_survives_a_crash_between_its_two_writes(tmp_path):
    v = VaultWords(tmp_path, Words(), clock=Clock())
    v.remember("First fact.", "user")
    with (tmp_path / "ollama" / "vectors.f32").open("ab") as f:
        f.write(np.ones(64, dtype=np.float32).tobytes())  # a vector whose note was never written
    again = VaultWords(tmp_path, Words())
    assert len(again.notes) == 1 and again.vectors.shape == (1, 64)
    assert (tmp_path / "ollama" / "vectors.f32").stat().st_size == 64 * 4
    with (tmp_path / "ollama" / "notes.jsonl").open("a") as f:
        f.write('{"id": 1, "at": "2026-11-04T09:0')  # a note cut short, with no vector
    again = VaultWords(tmp_path, Words(), clock=Clock())
    again.remember("Second fact.", "user")
    third = VaultWords(tmp_path, Words())
    assert [n["text"] for n in third.notes] == ["First fact.", "Second fact."] and third.vectors.shape == (2, 64)


def test_a_first_vector_without_its_note_is_cut_off(tmp_path):
    (tmp_path / "ollama").mkdir()
    (tmp_path / "ollama" / "meta.json").write_text('{"dim": 64, "embedder": "fake-words"}')
    (tmp_path / "ollama" / "vectors.f32").write_bytes(np.ones(64, dtype=np.float32).tobytes())
    v = VaultWords(tmp_path, Words(), clock=Clock())
    v.remember("Only fact.", "user")
    again = VaultWords(tmp_path, Words())
    assert len(again.notes) == 1 and np.allclose(again.vectors, Words().encode(["Only fact."]))


def test_long_turns_are_kept_as_pieces_that_fit_a_budget():
    text = "\n\n".join(["word " * 100] * 3 + ["short"])
    cut = pieces(text, 300)
    assert all(len(p) <= 300 for p in cut) and " ".join(" ".join(cut).split()) == " ".join(text.split())


def test_the_command_line_builds_without_loading_a_model(tmp_path):
    pairing, port = build(["--port", "11500", "--memory", str(tmp_path), "--budget", "256"])
    assert port == 11500 and pairing.budget_tokens == 256 and pairing.upstream == "127.0.0.1:11434"
    assert isinstance(pairing.provider, VaultWords) and pairing.provider._embedder is None
    assert pairing.metrics_path == tmp_path / "ollama" / "metrics.jsonl"
    bare = build(["--no-memory", "--memory", str(tmp_path / "unused")])[0]
    assert isinstance(bare.provider, NoMemory) and bare.metrics_path is None


# --- the real ollama CLI, pointed at the proxy with OLLAMA_HOST (the proxy talks to the stand-in, so no model runs)


@pytest.mark.skipif(shutil.which("ollama") is None, reason="the ollama CLI is not installed")
def test_the_ollama_cli_reaches_the_proxy_through_ollama_host():
    fake, pairing, port = start()
    env = {**os.environ, "OLLAMA_HOST": f"127.0.0.1:{port}", "OLLAMA_NOHISTORY": "1"}
    listed = subprocess.run(["ollama", "list"], env=env, capture_output=True, text=True, timeout=30)
    assert listed.returncode == 0 and "fake:latest" in listed.stdout
    ran = subprocess.run(["ollama", "run", "fake", "What is the main colour?"], env=env, capture_output=True,
                         text=True, timeout=30)
    assert ran.returncode == 0 and "Hello there! café ☕" in ran.stdout
    settle(lambda: len(pairing.provider.kept) >= 2)
    assert pairing.provider.asked and pairing.provider.asked[-1][0] == "What is the main colour?"
    assert pairing.provider.kept[-1] == ("assistant", "Hello there! café ☕")
