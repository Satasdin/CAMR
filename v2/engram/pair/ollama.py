"""The Ollama pairing: a small local proxy that speaks Ollama's own HTTP API, so the ollama CLI gets memory from one
setting.

    python -m engram.pair.ollama --port 11435 --memory ~/.engram/default
    OLLAMA_HOST=127.0.0.1:11435 ollama run qwen3:1.7b

Everything is forwarded to the real Ollama at 127.0.0.1:11434. Ollama runs its own model and lets no outside code put
tensors into it, so memory goes in as words. Before a chat (``/api/chat`` or the OpenAI-style
``/v1/chat/completions``) is forwarded, the provider is asked for notes on the last user message, and they are put at
the front of that message, so they sit just before the question. They are not a system message: Ollama's templates
(qwen3's, read with ``/api/show``) print every system message once, at the top of the whole prompt, and notes that
change each turn there would make Ollama read the whole history again every turn. The client keeps its own history
without the notes, so the prompt stays the same up to the previous question and Ollama's prompt cache holds. For
``/api/generate``, which has no history, the notes go into its ``system`` field, after the model's own system prompt.
Once the answer has streamed back, the exchange is remembered on one background worker, so the connection is free at
once; the next recall waits for it, and that wait is counted in its ``recall_ms``. Answers stream through byte for
byte; every other path is passed through as it is.

Security, as in engram.app.server. The proxy listens on 127.0.0.1 only. A request must name this host (stops DNS
rebinding). What a web page sends is refused, since any page the user visits can reach 127.0.0.1 too: a request with
an Origin header, or with Sec-Fetch-Site "cross-site" or "same-site". The CLI sends neither. Sec-Fetch-Site
"same-origin" is let through: a browser says that only to the server that served the page, and this proxy serves no
pages, so it can only be a local app's own server relaying its page's request (as the Ollama app does).
``--allow-origin`` lets an origin in (a port may be ``*``, as in ``http://127.0.0.1:*``), but only on paths that never
touch memory: an Origin header on a chat path or ``/engram/metrics`` is always refused. Bodies are capped; a refused
body is read and dropped for a moment, so the client sees the refusal instead of a reset connection. The real Ollama
must be on this Mac too: notes are personal and never leave it.

Every request is measured: the ms the proxy added before the request reached Ollama, the wait for Ollama's first
byte, and the tokens per second Ollama reported (``eval_count`` over ``eval_duration``), with memory on or off.
``GET /engram/metrics`` returns the latest, and each is a line of ``<memory>/ollama/metrics.jsonl``.

The Ollama app (0.13.5) has no setting for its server's address. It reads OLLAMA_HOST from its own environment
(``launchctl setenv``) both for its chat window and for the server it starts, except that "Expose Ollama to the
network" makes that server listen on 0.0.0.0:11434 instead. So ``launchctl setenv OLLAMA_HOST 127.0.0.1:11435``,
Expose on and a restart of the app should send its chats through this proxy (read from its source, not yet tried);
start the proxy with ``--allow-origin 'http://127.0.0.1:*'`` for the app's model list (``/api/tags``, ``/api/show``
and ``/api/version`` come from its web view; its chat comes from its Go client, which sends no Origin). Expose also
opens Ollama to the local network. Without Expose, the app's server would fight this proxy for the port and stop
every other process named ollama.
"""

from __future__ import annotations

import argparse
import datetime as dt
import http.client
import json
import queue
import re
import socket
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from engram.pair.provider import NoMemory, Provider, VaultWords, clip

PORT = 11435
UPSTREAM = "127.0.0.1:11434"
BUDGET = 512  # tokens of notes per chat: about one room of the engine's desk
MAX_BODY = 32 * 2**20  # a chat with a few photos fits; model uploads (ollama create) go to Ollama directly
TIMEOUT_S = 600.0  # a big model can take minutes to load before its first word
DRAIN_S = 2.0  # how long a refused body is read and dropped, so the client gets to read the refusal
WAIT_S = 30.0  # how long a recall waits for the exchanges before it to be remembered
PIECE = 64 * 1024
KEEP = 500  # measurements kept for /engram/metrics
MEMORY = {"/api/chat": "chat", "/api/generate": "generate", "/v1/chat/completions": "openai"}
METRICS = "/engram/metrics"
NOTES_INTRO = "Notes from earlier conversations with this user, oldest first. Use them when they help."
NOTES_END = "The user's new message:"
HOP = {"connection", "keep-alive", "proxy-connection", "transfer-encoding", "te", "trailer", "upgrade",
       "proxy-authenticate", "proxy-authorization", "content-length", "host"}
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
_HEX = re.compile(rb"[0-9A-Fa-f]{1,8}")
_DIGITS = re.compile(r"[0-9]{1,15}")


class TooBig(ValueError):
    pass


def _ms(a: float, b: float | None = None) -> float:
    return round(((b if b is not None else time.perf_counter()) - a) * 1000, 2)


def _text(content) -> str:
    """A message's words: a string, or the text parts of an OpenAI-style list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""


def last_user(kind: str, req: dict) -> tuple[str, int | None]:
    """The last user message's words, and its place in ``messages`` (None for /api/generate)."""
    if kind == "generate":
        return (_text(req.get("prompt")).strip(), None) if not req.get("raw") else ("", None)
    msgs = req.get("messages")
    if not isinstance(msgs, list):
        return "", None
    for i in range(len(msgs) - 1, -1, -1):
        if isinstance(msgs[i], dict) and msgs[i].get("role") == "user":
            return _text(msgs[i].get("content")).strip(), i
    return "", None


def model_of(raw: bytes):
    """The model a request names, for the measurements (None when the body is not a JSON object)."""
    try:
        req = json.loads(raw)
    except ValueError:
        return None
    return req.get("model") if isinstance(req, dict) else None


class Tap:
    """A copy of the answer read as it streams past: the words written, whether it finished, and Ollama's counts.

    ``kind`` is "chat" or "generate" (NDJSON lines, or one JSON object when not streaming) or "openai" (SSE
    ``data:`` lines, or one JSON object)."""

    def __init__(self, kind: str):
        self.kind, self.buf, self.parts, self.counts, self.done = kind, b"", [], {}, False

    def feed(self, data: bytes) -> None:
        *lines, self.buf = (self.buf + data).split(b"\n")
        for line in lines:
            self._line(line)

    def close(self) -> None:
        if self.buf.strip():
            self._line(self.buf)
        self.buf = b""

    @property
    def answer(self) -> str:
        return "".join(self.parts).strip()

    def _line(self, line: bytes) -> None:
        line = line.strip()
        if self.kind == "openai" and line.startswith(b"data:"):
            line = line[5:].strip()
            if line == b"[DONE]":
                self.done = True
                return
        if not line:
            return
        try:
            obj = json.loads(line)
        except ValueError:
            return
        if not isinstance(obj, dict):
            return
        if self.kind == "openai":
            for c in obj.get("choices") or []:
                part = (c.get("delta") or c.get("message") or {}).get("content")
                if isinstance(part, str):
                    self.parts.append(part)
                if c.get("finish_reason"):
                    self.done = True
            usage = obj.get("usage") or {}
            self.counts.update({k: usage[k] for k in ("prompt_tokens", "completion_tokens") if k in usage})
            return
        part = (obj.get("message") or {}).get("content") if self.kind == "chat" else obj.get("response")
        if isinstance(part, str):
            self.parts.append(part)
        if obj.get("done"):
            self.done = True
            self.counts.update({k: obj[k] for k in ("eval_count", "eval_duration", "prompt_eval_count",
                                                    "prompt_eval_duration", "load_duration", "total_duration")
                                if isinstance(obj.get(k), (int, float))})

    def stats(self) -> dict:
        """Ollama's own numbers: tokens per second as it reported them, and its load and total time in ms."""
        c, out = self.counts, {}
        for name, n, d in (("decode_tps", "eval_count", "eval_duration"),
                           ("prefill_tps", "prompt_eval_count", "prompt_eval_duration")):
            if c.get(d):
                out[name] = round(c[n] / (c[d] / 1e9), 1) if n in c else None
        for k in ("eval_count", "prompt_eval_count", "prompt_tokens", "completion_tokens"):
            if k in c:
                out[k] = c[k]
        for k in ("load_duration", "total_duration"):
            if k in c:
                out["ollama_" + k.replace("duration", "ms")] = round(c[k] / 1e6, 2)
        return out


class Pairing:
    """What the proxy needs: the memory provider, where the real Ollama listens, and the limits."""

    def __init__(self, provider: Provider, upstream: str = UPSTREAM, *, budget_tokens: int = BUDGET,
                 max_body: int = MAX_BODY, timeout_s: float = TIMEOUT_S, allow_origins: tuple[str, ...] = (),
                 metrics_path: Path | None = None, keep: int = KEEP, wait_s: float = WAIT_S):
        u = urlsplit(upstream if "://" in upstream else f"http://{upstream}")
        if u.scheme != "http" or u.hostname not in LOOPBACK:
            raise ValueError("the real Ollama must be on this Mac: notes are personal and never leave it")
        self.provider, self.host, self.port = provider, u.hostname, u.port or 11434
        self.upstream = f"[{self.host}]:{self.port}" if ":" in self.host else f"{self.host}:{self.port}"
        self.budget_tokens, self.max_body, self.timeout_s, self.wait_s = budget_tokens, max_body, timeout_s, wait_s
        self.allow_origins = tuple(allow_origins)
        self.metrics: deque[dict] = deque(maxlen=keep)
        self.metrics_path = metrics_path
        self.lock = threading.Lock()  # one memory call at a time: the embedder runs one job at a time
        self._log_lock = threading.Lock()
        self._systems: dict[str, str] = {}
        self._jobs: queue.Queue = queue.Queue()
        self._turns = threading.Condition()
        self._told = self._kept = 0  # exchanges handed to the worker, and how many it has kept
        self._worker: threading.Thread | None = None

    def allowed(self, origin: str) -> bool:
        """Whether ``origin`` was let in, exactly or as ``scheme://host:*`` (any port)."""
        for a in self.allow_origins:
            if origin == a or (a.endswith(":*") and origin.startswith(a[:-1]) and origin[len(a) - 1:].isdigit()):
                return True
        return False

    def connect(self) -> http.client.HTTPConnection:
        return http.client.HTTPConnection(self.host, self.port, timeout=self.timeout_s)

    def model_system(self, model) -> str:
        """The model's own system prompt (from its Modelfile), asked of Ollama once per model."""
        if not isinstance(model, str) or not model:
            return ""
        if model not in self._systems:
            try:
                c = self.connect()
                c.request("POST", "/api/show", json.dumps({"model": model}),
                          {"Host": self.upstream, "Content-Type": "application/json"})
                r = c.getresponse()
                body = r.read()
                c.close()
                if r.status != 200:
                    return ""
                self._systems[model] = str(json.loads(body).get("system") or "")
            except (OSError, ValueError, http.client.HTTPException):
                return ""
        return self._systems[model]

    def prepare(self, kind: str, raw: bytes, m: dict) -> tuple[bytes, str]:
        """The request with notes added, and the user's words to remember ('' when there is nothing to remember).
        Only the start and end of a long message are used to look the notes up."""
        try:
            req = json.loads(raw)
        except ValueError:
            return raw, ""
        if not isinstance(req, dict):
            return raw, ""
        m["model"] = req.get("model")
        query, at = last_user(kind, req)
        if not query:
            return raw, ""
        asked = clip(query)
        if len(asked) < len(query):
            m["query_cut"] = True
        t = time.perf_counter()
        if not self.settled(self.wait_s):
            m["error"] = "recall: earlier exchanges not yet remembered"
        m["wait_ms"] = _ms(t)
        try:
            with self.lock:
                notes = self.provider.recall_text(asked, self.budget_tokens)
        except Exception as e:  # memory must never break the chat
            m["error"] = f"recall: {type(e).__name__}"
            notes = ""
        m["recall_ms"] = _ms(t)
        m["notes_chars"] = len(notes)
        if not notes:
            return raw, query
        block = f"{NOTES_INTRO}\n\n{notes}"
        if kind == "generate":
            own = req.get("system") or self.model_system(req.get("model"))
            req["system"] = f"{own}\n\n{block}" if own else block
        else:  # at the front of the question itself: the roles and the client's system prompt stay as they were
            msg = req["messages"][at]
            content = msg.get("content")
            lead = f"{block}\n\n{NOTES_END}"
            msg["content"] = ([{"type": "text", "text": lead}, *content] if isinstance(content, list)
                              else f"{lead}\n\n{content}")
        return json.dumps(req, ensure_ascii=False).encode(), query

    def remember(self, query: str, answer: str, m: dict) -> None:
        t = time.perf_counter()
        left = 0
        try:
            with self.lock:
                for text, role in ((query, "user"), (answer, "assistant")):
                    n = self.provider.remember(text, role)
                    left += n if isinstance(n, int) else 0
        except Exception as e:
            m["error"] = f"remember: {type(e).__name__}"
        m["remember_ms"] = _ms(t)
        if left:
            m["left_out_chars"] = left  # a long turn kept only its first and last pieces

    def later(self, query: str, answer: str, m: dict) -> None:
        """Remember an exchange on the memory worker, then record ``m``: the client's connection is free at once."""
        with self._turns:
            if self._worker is None:
                self._worker = threading.Thread(target=self._work, name="engram-remember", daemon=True)
                self._worker.start()
            self._told += 1
        self._jobs.put((query, answer, m))

    def settled(self, timeout: float | None = None) -> bool:
        """Wait until every exchange handed to the worker so far is remembered; False if ``timeout`` ran out."""
        with self._turns:
            told = self._told
            return self._turns.wait_for(lambda: self._kept >= told, timeout)

    def _work(self) -> None:
        while True:
            query, answer, m = self._jobs.get()
            try:
                self.remember(query, answer, m)
                self.record(m)
            except Exception:  # a worker that died would hold up every later chat
                pass
            finally:
                with self._turns:
                    self._kept += 1
                    self._turns.notify_all()

    def latest(self) -> list[dict]:
        with self._log_lock:
            return list(self.metrics)

    def record(self, m: dict) -> None:
        with self._log_lock:
            self.metrics.append(m)
            if self.metrics_path is not None:
                self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
                with self.metrics_path.open("a") as out:
                    out.write(json.dumps(m) + "\n")


def make_server(pairing: Pairing, port: int = PORT) -> ThreadingHTTPServer:
    """The proxy, bound to 127.0.0.1 only (``port`` 0 picks a free one). Call ``serve_forever`` to run it."""

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"  # chunked answers and kept-alive connections, as the CLI expects
        timeout = pairing.timeout_s  # a client gone quiet frees its thread
        hosts: set[str] = set()
        unread = False  # the request's body has not been read: drop it before closing

        def log_message(self, *args) -> None:  # keep the terminal quiet
            pass

        def do_GET(self) -> None:
            self._proxy()

        do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = do_GET

        def _forbidden(self, path: str) -> str:
            if self.headers.get("Host") not in self.hosts:
                return "wrong host"
            origin = self.headers.get("Origin")
            if origin is not None:
                plain = re.sub(r"/+", "/", unquote(path)).rstrip("/")  # however a page spells the path
                if plain in MEMORY or plain == METRICS:
                    return "web pages may not reach memory"
                return "" if pairing.allowed(origin) else "web pages may not use this proxy"
            if self.headers.get("Sec-Fetch-Site", "none") not in ("none", "same-origin"):
                return "web pages may not use this proxy"
            return ""

        def _refuse(self, code: int, why: str) -> None:
            body = json.dumps({"error": why}).encode()
            self.close_connection = True  # the body may be unread: never parse it as the next request
            self.send_response_only(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            self.wfile.flush()
            if self.unread:
                self._drain()

        def _drain(self) -> None:
            """Read and drop what is left of the body, for at most DRAIN_S. Closing with it unread would reset the
            connection, and a client still sending would never read the refusal."""
            n = self.headers.get("Content-Length")
            chunked = "chunked" in (self.headers.get("Transfer-Encoding") or "").lower()
            if n is None and not chunked:
                return
            left = int(n) if not chunked and _DIGITS.fullmatch(n.strip()) else None
            try:
                self.connection.shutdown(socket.SHUT_WR)  # the refusal is all out: the client sees it end
                end = time.monotonic() + DRAIN_S
                while left is None or left > 0:
                    rest = end - time.monotonic()
                    if rest <= 0:
                        break
                    self.connection.settimeout(rest)
                    data = self.rfile.read1(PIECE if left is None else min(PIECE, left))
                    if not data:
                        break
                    if left is not None:
                        left -= len(data)
            except OSError:
                pass

        def _body(self) -> bytes:
            if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
                out = bytearray()
                while True:
                    line = self.rfile.readline(1024).split(b";")[0].strip()
                    if not _HEX.fullmatch(line):
                        raise ValueError("bad chunk size")
                    size = int(line, 16)
                    if size == 0:
                        break
                    if len(out) + size > pairing.max_body:
                        raise TooBig
                    data = self.rfile.read(size)
                    if len(data) != size or self.rfile.readline(3) not in (b"\r\n", b"\n"):
                        raise ValueError("short chunk")
                    out += data
                for _ in range(64):  # trailers
                    if not self.rfile.readline(1024).strip():
                        break
                else:
                    raise ValueError("too many trailers")
                return bytes(out)
            n = self.headers.get("Content-Length")
            if n is None:
                return b""
            if not _DIGITS.fullmatch(n.strip()):
                raise ValueError("bad Content-Length")
            if int(n) > pairing.max_body:
                raise TooBig
            body = self.rfile.read(int(n))
            if len(body) != int(n):
                raise ValueError("short body")
            return body

        def _proxy(self) -> None:
            t0 = time.perf_counter()
            self.unread = True
            if not self.path.startswith("/"):
                return self._refuse(400, "bad request target")
            path = self.path.split("?", 1)[0]
            why = self._forbidden(path)
            if why:
                return self._refuse(403, why)
            try:
                body = self._body()
            except TooBig:
                return self._refuse(413, f"body over {pairing.max_body} bytes")
            except ValueError:
                return self._refuse(400, "bad body")
            self.unread = False
            if path == METRICS and self.command == "GET":
                out = json.dumps({"requests": pairing.latest()}).encode()
                self.send_response_only(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                return self.wfile.write(out)
            kind = MEMORY.get(path) if self.command == "POST" else None  # an answer the tap can read
            memory = bool(kind) and self.headers.get("X-Engram-Memory", "").lower() != "off"
            m = {"at": dt.datetime.now().isoformat(timespec="milliseconds"), "method": self.command, "path": path,
                 "memory": False}
            query = ""
            if memory:
                body, query = pairing.prepare(kind, body, m)
                m["memory"] = bool(query)  # a request with no user message (loading a model) has nothing to recall
            elif kind:
                m["model"] = model_of(body)
            self._forward(body, kind, memory, query, m, t0)

        def _forward(self, body: bytes, kind: str | None, memory: bool, query: str, m: dict, t0: float) -> None:
            skip = HOP | {"x-engram-memory", "expect"} | ({"accept-encoding"} if kind else set())
            conn = pairing.connect()
            try:
                conn.putrequest(self.command, self.path, skip_host=True, skip_accept_encoding=True)
                conn.putheader("Host", pairing.upstream)
                for k, v in self.headers.items():
                    if k.lower() not in skip:
                        conn.putheader(k, v)
                if body or self.command in ("POST", "PUT", "PATCH"):
                    conn.putheader("Content-Length", str(len(body)))
                conn.endheaders(body or None)
                sent = time.perf_counter()
                m["added_ms"] = _ms(t0, sent)
                resp = conn.getresponse()
            except (OSError, http.client.HTTPException) as e:
                conn.close()
                m.update(status=502, error=f"upstream: {type(e).__name__}", total_ms=_ms(t0))
                pairing.record(m)
                return self._refuse(502, f"Ollama is not answering at {pairing.upstream}")
            headed = time.perf_counter()
            no_body = self.command == "HEAD" or resp.status in (204, 304) or 100 <= resp.status < 200
            length = resp.getheader("Content-Length")
            chunked = length is None and not no_body
            self.send_response_only(resp.status, resp.reason)
            for k, v in resp.getheaders():
                if k.lower() not in HOP:
                    self.send_header(k, v)
            if length is not None:
                self.send_header("Content-Length", length)
            elif chunked and self.request_version != "HTTP/1.1":
                chunked, self.close_connection = False, True  # an HTTP/1.0 client reads until the connection closes
                self.send_header("Connection", "close")
            elif chunked:
                self.send_header("Transfer-Encoding", "chunked")
            if memory:
                self.send_header("X-Engram-Added-Ms", str(m["added_ms"]))
                self.send_header("X-Engram-Notes-Chars", str(m.get("notes_chars", 0)))
            self.end_headers()
            tap = Tap(kind) if kind and resp.status == 200 else None
            first, out, whole = None, 0, False
            try:
                while not no_body:
                    data = resp.read1(PIECE)
                    if not data:
                        break
                    first = first or time.perf_counter()
                    if tap:
                        tap.feed(data)
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data) if chunked else data)
                    out += len(data)
                if chunked:
                    self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
                whole = True
            except (BrokenPipeError, ConnectionResetError):
                m["error"] = "the client left before the answer ended"
                self.close_connection = True
            except (OSError, http.client.HTTPException) as e:
                m["error"] = f"upstream: {type(e).__name__}"
                self.close_connection = True
            finally:
                conn.close()
            m.update(status=resp.status, bytes=out, upstream_first_byte_ms=_ms(sent, first or headed),
                     first_byte_ms=_ms(t0, first or headed), total_ms=_ms(t0))
            if tap:
                tap.close()
                m.update(tap.stats())
                if memory and query and whole and tap.done and tap.answer:
                    return pairing.later(query, tap.answer, m)  # recorded once it is remembered
            pairing.record(m)

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    port = httpd.server_address[1]
    Handler.hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    return httpd


def build(argv: list[str] | None = None) -> tuple[Pairing, int]:
    """The pairing and port the command line asks for. Nothing is loaded yet."""
    ap = argparse.ArgumentParser(prog="python -m engram.pair.ollama",
                                 description="Memory for the ollama CLI: run this, then OLLAMA_HOST=127.0.0.1:11435.")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--memory", type=Path, default=Path.home() / ".engram" / "default",
                    help="the memory folder (an engine memory, or a new folder)")
    ap.add_argument("--upstream", default=UPSTREAM, help="where the real Ollama listens (this Mac only)")
    ap.add_argument("--budget", type=int, default=BUDGET, help="tokens of notes added to each chat")
    ap.add_argument("--no-memory", action="store_true", help="a plain passthrough, to measure the proxy alone")
    ap.add_argument("--allow-origin", action="append", default=[],
                    help="an origin allowed in on paths that never touch memory, port may be * (repeatable); "
                         "the Ollama app's model list needs http://127.0.0.1:*")
    ap.add_argument("--max-body-mb", type=float, default=MAX_BODY / 2**20)
    ap.add_argument("--metrics", type=Path, help="where measurements go (default <memory>/ollama/metrics.jsonl)")
    a = ap.parse_args(argv)
    memory = a.memory.expanduser()
    provider = NoMemory() if a.no_memory else VaultWords(memory)
    metrics = a.metrics or (None if a.no_memory else memory / "ollama" / "metrics.jsonl")
    pairing = Pairing(provider, a.upstream, budget_tokens=a.budget, max_body=int(a.max_body_mb * 2**20),
                      allow_origins=tuple(a.allow_origin), metrics_path=metrics)
    return pairing, a.port


def main(argv: list[str] | None = None) -> None:
    pairing, port = build(argv)
    if isinstance(pairing.provider, VaultWords):  # load the embedder now, and refuse notes another one wrote
        print("Loading the embedder...", flush=True)
        try:
            pairing.provider.warm()
        except ValueError as e:
            raise SystemExit(f"engram pairing: {e}")
    httpd = make_server(pairing, port)
    port = httpd.server_address[1]
    where = "no memory" if isinstance(pairing.provider, NoMemory) else f"memory: {pairing.provider.folder}"
    print(f"Ollama pairing on http://127.0.0.1:{port} -> http://{pairing.upstream}  ({where})\n"
          f"Use it with:  OLLAMA_HOST=127.0.0.1:{port} ollama run <model>", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        pairing.settled(WAIT_S)  # the last exchanges are kept before the process ends


if __name__ == "__main__":
    main()
