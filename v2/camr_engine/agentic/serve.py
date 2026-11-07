"""The project's files over HTTP on this Mac only (127.0.0.1), for a browser plugin to test the page in: Playwright,
like most browsers driven by a tool, refuses file: addresses. Read-only, GET and HEAD only, and every path goes through
the workspace (camr_engine.agentic.workspace), so nothing outside the project, no symlink out of it and no file of
secrets is ever served. One server per workspace, started when first asked for, on a port the system picks.

Pages may load the project's own files only: vendored libraries (``vendor/``, ES modules with import maps) and models
(``.glb``, ``.gltf``) are served with the types a browser insists on for them, and every response carries a content
security policy that lets the page reach this server and nothing else, so a page tested in Chrome is as shut off from
the network as in the app's own preview.
"""

from __future__ import annotations

import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

_servers: dict[str, "PageServer"] = {}
TYPES = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".html": "text/html",
         ".htm": "text/html", ".json": "application/json", ".map": "application/json", ".svg": "image/svg+xml",
         ".glb": "model/gltf-binary", ".gltf": "model/gltf+json", ".bin": "application/octet-stream",
         ".wasm": "application/wasm", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".webp": "image/webp", ".ktx2": "image/ktx2", ".hdr": "image/vnd.radiance", ".woff2": "font/woff2",
         ".woff": "font/woff", ".txt": "text/plain", ".md": "text/markdown"}
# the project's own files, inline code and data: nothing on any other host (the app's preview blocks the same)
POLICY = ("default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; "
          "img-src 'self' data: blob:; font-src 'self' data:; media-src 'self' data: blob:; "
          "connect-src 'self' data: blob:; worker-src 'self' blob:; frame-src 'none'; form-action 'none'")


def kind_of(name: str) -> str:
    """The media type a browser needs for a file: a module script must be JavaScript, a model a glTF type."""
    from pathlib import PurePosixPath

    return TYPES.get(PurePosixPath(name).suffix.lower()) or mimetypes.guess_type(name)[0] or "application/octet-stream"

_lock = threading.Lock()


class PageServer:
    def __init__(self, ws):
        self.ws = ws
        workspace = ws

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # quiet: nothing about the person's files goes to the console
                pass

            def _file(self) -> tuple[bytes, str] | None:
                rel = unquote(urlsplit(self.path).path).lstrip("/") or "index.html"
                if rel.endswith("/"):
                    rel += "index.html"
                try:
                    p = workspace.path(rel)
                    if not p.is_file():
                        return None
                    data = p.read_bytes()
                except Exception:  # noqa: BLE001 (Outside, or unreadable: not found, saying nothing more)
                    return None
                return data, kind_of(p.name)

            def do_GET(self):  # noqa: N802
                self._send(body=True)

            def do_HEAD(self):  # noqa: N802
                self._send(body=False)

            def _send(self, body: bool) -> None:
                got = self._file()
                if got is None and urlsplit(self.path).path == "/favicon.ico":  # asked by every browser: not a problem
                    self.send_response(204)
                    self.end_headers()
                    return
                if got is None:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                data, kind = got
                self.send_response(200)
                self.send_header("Content-Type", kind + ("; charset=utf-8" if kind.startswith("text/") else ""))
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", POLICY)
                self.end_headers()
                if body:
                    self.wfile.write(data)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="camr-pages", daemon=True)
        self.thread.start()

    def url(self, rel: str = "index.html") -> str:
        return f"http://127.0.0.1:{self.port}/{rel.lstrip('/')}"

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def serving(ws) -> PageServer:
    """The server for a workspace, started on first use."""
    key = str(ws.root)
    with _lock:
        got = _servers.get(key)
        if got is None:
            got = _servers[key] = PageServer(ws)
        return got


def close_all() -> None:
    with _lock:
        for s in _servers.values():
            s.close()
        _servers.clear()
