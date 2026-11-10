import http.server, sys, os, re
OUT = sys.argv[1]
class H(http.server.BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); body = self.rfile.read(n)
        if "urlencoded" in (self.headers.get("Content-Type") or ""):
            import urllib.parse
            body = urllib.parse.parse_qs(body.decode("utf-8"), keep_blank_values=True).get("d", [""])[0].encode("utf-8")
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", self.path.strip("/")) or "x"
        open(os.path.join(OUT, name), "wb").write(body)
        self.send_response(200); self._cors(); self.end_headers(); self.wfile.write(b"ok %d" % n)
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", 8765), H).serve_forever()
