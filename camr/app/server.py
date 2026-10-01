"""CAMR Personal web server: standard library only, so the app packages into a small native download.

    camr app                 # serves http://127.0.0.1:8502 and opens it
    camr app --window        # native window instead of a browser tab (needs `pywebview`)

The server binds to 127.0.0.1 only. The API is used by camr/app/static/app.js:

  GET  /api/state                     Ollama status, installed models, settings, memory stats
  POST /api/setup                     pull the embedding model (progress in /api/state)
  GET  /api/conversations             list chats            POST /api/conversations   new chat
  GET  /api/conversations/<id>        transcript            PATCH/DELETE same path   rename / delete
  POST /api/chat                      {"message", "conversation_id"} -> Server-Sent Events
  POST /api/feedback                  {"turn_id", "helpful"}
  POST /api/teach                     {"text", "title"}  or  {"filename", "data_base64"}
  GET  /api/memory?q=&kind=           memory items        DELETE /api/memory/<source_id>
  POST /api/settings                  {"model", "token_budget", "history_turns", "remember_chat"}
  GET  /api/export?text=0|1           metrics-only feedback file (text only when asked)
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

from camr.app.assistant import DEFAULT_EMBED_MODEL, DEFAULT_HOME, DEFAULT_HOST, Assistant, installed_models

STATIC = Path(__file__).resolve().parent / "static"
VERSION = "0.2.1"


class App:
    """Owns the Assistant once Ollama and the embedding model are available."""

    def __init__(self, home: Path, host: str):
        self.home, self.host = home, host
        self.assistant: Assistant | None = None
        self.pull: dict = {"status": "idle"}
        self._lock = threading.Lock()

    def ollama_models(self) -> list[dict] | None:
        try:
            return installed_models(self.host)
        except requests.RequestException:
            return None

    def ensure(self) -> Assistant | None:
        with self._lock:
            if self.assistant is None:
                models = self.ollama_models()
                if models is None:
                    return None
                names = {m["name"].split(":")[0] for m in models}
                if DEFAULT_EMBED_MODEL not in names:
                    return None
                self.assistant = Assistant(self.home, host=self.host)
                if not self.assistant.model:  # first run: pick the smallest chat model the user has
                    chat = [m for m in models if not m["embedding"]]
                    if chat:
                        self.assistant.save_settings(model=chat[0]["name"])
                threading.Thread(target=self.assistant.warm, daemon=True).start()
            return self.assistant

    def start_pull(self, name: str = DEFAULT_EMBED_MODEL) -> None:
        if self.pull.get("status") == "pulling":
            return

        def run():
            self.pull = {"status": "pulling", "model": name, "completed": 0, "total": 0}
            try:
                with requests.post(f"{self.host}/api/pull", json={"name": name, "stream": True}, stream=True,
                                   timeout=3600) as r:
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if line:
                            ev = json.loads(line)
                            self.pull.update({k: ev[k] for k in ("completed", "total", "status") if k in ev})
                            if ev.get("error"):
                                raise RuntimeError(ev["error"])
                self.pull = {"status": "done", "model": name}
            except Exception as exc:  # surfaced to the UI
                self.pull = {"status": "error", "model": name, "error": str(exc)}

        threading.Thread(target=run, daemon=True).start()

    def state(self) -> dict:
        models = self.ollama_models()
        a = self.ensure() if models is not None else None
        return {
            "version": VERSION,
            "ollama": models is not None,
            "host": self.host,
            "models": [m for m in (models or []) if not m["embedding"]],
            "embed_model": DEFAULT_EMBED_MODEL,
            "ready": a is not None,
            "pull": self.pull,
            "settings": a.settings() if a else None,
            "stats": a.stats() if a else None,
            "home": str(self.home),
        }


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = f"CAMR/{VERSION}"

        def log_message(self, fmt, *args):  # quiet console
            pass

        # ------------------------------------------------ helpers
        def _json(self, obj, status: int = 200) -> None:
            body = json.dumps(obj, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}") if n else {}

        def _assistant(self) -> Assistant | None:
            a = app.ensure()
            if a is None:
                self._json({"error": "not ready: start Ollama and finish setup"}, 503)
            return a

        def _host_ok(self) -> bool:
            """Answer only requests addressed to this machine (defends against DNS rebinding)."""
            name = self.headers.get("Host", "").rsplit(":", 1)[0].strip("[]")
            if name not in ("127.0.0.1", "localhost", "::1"):
                self._json({"error": "forbidden host"}, 403)
                return False
            return True

        def _origin_ok(self) -> bool:
            """Refuse cross-site requests: only pages served by this app may call the API."""
            if not self._host_ok():
                return False
            origin = self.headers.get("Origin")
            host = self.headers.get("Host", "")
            if origin and urlparse(origin).netloc != host:
                self._json({"error": "cross-origin request refused"}, 403)
                return False
            return True

        # ------------------------------------------------ GET
        def do_GET(self):  # noqa: N802
            if not self._host_ok():
                return
            url = urlparse(self.path)
            path = url.path
            if path == "/api/state":
                return self._json(app.state())
            if path == "/api/conversations":
                a = self._assistant()
                return a and self._json(a.conversations())
            m = re.fullmatch(r"/api/conversations/(\d+)", path)
            if m:
                a = self._assistant()
                return a and self._json(a.transcript(int(m.group(1))))
            if path == "/api/memory":
                a = self._assistant()
                q = parse_qs(url.query)
                return a and self._json(a.sources(q.get("kind", [None])[0] or None, q.get("q", [""])[0]))
            if path == "/api/export":
                a = self._assistant()
                with_text = parse_qs(url.query).get("text", ["0"])[0] == "1"
                if a:
                    body = json.dumps(a.export_feedback(with_text), indent=2).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Disposition", 'attachment; filename="camr-feedback.json"')
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                return
            # static files (single-page app)
            rel = "index.html" if path in ("/", "") else path.lstrip("/")
            f = (STATIC / rel).resolve()
            if not str(f).startswith(str(STATIC)) or not f.is_file():
                f = STATIC / "index.html"
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", (mimetypes.guess_type(f.name)[0] or "application/octet-stream")
                             + ("; charset=utf-8" if f.suffix in (".html", ".js", ".css", ".svg") else ""))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)

        # ------------------------------------------------ POST
        def do_POST(self):  # noqa: N802
            if not self._origin_ok():
                return
            path = urlparse(self.path).path
            data = self._body()
            if path == "/api/setup":
                app.start_pull(data.get("model") or DEFAULT_EMBED_MODEL)
                return self._json({"ok": True})
            a = self._assistant()
            if a is None:
                return
            if path == "/api/conversations":
                return self._json({"id": a.new_conversation()})
            if path == "/api/feedback":
                a.feedback(int(data["turn_id"]), bool(data["helpful"]))
                return self._json({"ok": True})
            if path == "/api/teach":
                if data.get("data_base64") is not None:
                    n = a.teach_file(data["filename"], base64.b64decode(data["data_base64"]))
                else:
                    n = a.teach(data.get("text", ""), title=data.get("title", ""))
                return self._json({"notes": n})
            if path == "/api/settings":
                changed = "model" in data and data["model"] != a.model
                a.save_settings(**{k: data[k] for k in ("model", "token_budget", "history_turns", "remember_chat")
                                   if k in data})
                if changed:  # load the newly chosen model now, not on the next question
                    threading.Thread(target=a.warm, daemon=True).start()
                return self._json(a.settings())
            if path == "/api/chat":
                return self._chat(a, data)
            self._json({"error": "not found"}, 404)

        def _chat(self, a: Assistant, data: dict) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                for ev in a.events(data.get("message", ""), data.get("conversation_id")):
                    self.wfile.write(f"data: {json.dumps(ev, default=str)}\n\n".encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):  # user pressed stop
                return
            except Exception as exc:
                self.wfile.write(f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n".encode())

        # ------------------------------------------------ PATCH / DELETE
        def do_PATCH(self):  # noqa: N802
            if not self._origin_ok():
                return
            m = re.fullmatch(r"/api/conversations/(\d+)", urlparse(self.path).path)
            a = self._assistant()
            if a and m:
                a.rename_conversation(int(m.group(1)), self._body().get("title", ""))
                self._json({"ok": True})

        def do_DELETE(self):  # noqa: N802
            if not self._origin_ok():
                return
            path = urlparse(self.path).path
            a = self._assistant()
            if a is None:
                return
            m = re.fullmatch(r"/api/conversations/(\d+)", path)
            if m:
                a.delete_conversation(int(m.group(1)))
                return self._json({"ok": True})
            m = re.fullmatch(r"/api/memory/(\d+)", path)
            if m:
                return self._json({"removed": a.forget(int(m.group(1)))})
            self._json({"error": "not found"}, 404)

    return Handler


def serve(home: Path = DEFAULT_HOME, host: str = DEFAULT_HOST, port: int = 8502, open_browser: bool = True,
          window: bool = False) -> None:
    app = App(Path(home).expanduser(), host)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    url = f"http://127.0.0.1:{httpd.server_address[1]}"
    print(f"CAMR Personal is running at {url}  (Ctrl+C to quit)")
    if window:
        try:
            import webview  # type: ignore

            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            webview.create_window("CAMR", url, width=1240, height=820, min_size=(720, 560))
            webview.start()
            return
        except ImportError:
            print("pywebview is not installed; opening a browser tab instead")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        if app.assistant:
            app.assistant.close()


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="camr-app", description="CAMR Personal: your model, a memory that grows")
    p.add_argument("--home", default=str(DEFAULT_HOME))
    p.add_argument("--host", default=DEFAULT_HOST, help="Ollama address (must be on this machine)")
    p.add_argument("--port", type=int, default=8502)
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--window", action="store_true", help="open in a native window (pywebview)")
    a = p.parse_args(argv)
    serve(Path(a.home), a.host, a.port, not a.no_browser, a.window)


if __name__ == "__main__":
    main()
