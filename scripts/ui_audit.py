"""Accessibility and design audit of CAMR Personal's interface.

1. Colour contrast of the design tokens (WCAG 2.2 relative-luminance formula) for every text/background
   pair the stylesheet uses, in the dark and light themes.
2. An automated audit with axe-core (Deque) in Chromium, for both themes at desktop and phone width,
   on a populated chat (a remembered fact, an answer with recalled memory, the memory panel open).

The app runs with the deterministic test doubles (no model needed); the audit is of the interface.

    python scripts/ui_audit.py --axe <path to axe.min.js> --out docs/results/ui_audit.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

CSS = ROOT / "camr/app/static/app.css"
# (foreground token, background token, what uses it, text size class)
PAIRS = [("text", "bg", "Body text, answers", "normal"), ("text", "surface-2", "User message bubble", "normal"),
         ("muted", "bg", "Secondary text, timings, chat list", "normal"),
         ("muted", "surface", "Secondary text on cards", "normal"),
         ("faint", "bg", "Group labels, keyboard hints (11–12 px)", "normal"),
         ("faint", "bg-2", "Sidebar group labels", "normal"),
         ("accent-2", "bg", "Glyphs, links", "normal"), ("accent", "bg", "Accent text and focus ring", "large"),
         ("good", "bg", "Grounded meter, success", "large"), ("warn", "bg", "Warnings", "large")]


def tokens(css: str) -> dict[str, dict[str, str]]:
    def block(sel):
        m = re.search(re.escape(sel) + r"\s*\{(.*?)\}", css, re.S)
        return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", m.group(1))) if m else {}
    dark = block(":root")
    light = {**dark, **block(':root[data-theme="light"]')}
    return {"dark": dark, "light": light}


def luminance(hex_: str) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def contrast_table() -> list[dict]:
    out = []
    for theme, t in tokens(CSS.read_text()).items():
        for fg, bg, use, size in PAIRS:
            ratio = contrast(t[fg], t[bg])
            need = 3.0 if size == "large" else 4.5
            out.append({"theme": theme, "fg": fg, "bg": bg, "fg_hex": t[fg], "bg_hex": t[bg], "use": use, "size": size,
                        "ratio": round(ratio, 2), "required_AA": need, "pass_AA": ratio >= need})
    return out


def serve():
    from camr.app.assistant import Assistant
    from camr.app.server import App, make_handler
    from camr.memory.embedder import HashingEmbedder
    from test_app import FakeOllama

    home = Path(tempfile.mkdtemp())
    app = App(home, "http://127.0.0.1:11434")
    app.assistant = Assistant(home, model="qwen2.5:1.5b", embedder=HashingEmbedder(384), session=FakeOllama(),
                              min_similarity=0.3)
    app.ollama_models = lambda: [{"name": "qwen2.5:1.5b", "size_gb": 1.0, "parameters": "1.5B", "family": "qwen2",
                                  "embedding": False}]
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, app


def axe_audit(axe_js: Path) -> list[dict]:
    from playwright.sync_api import sync_playwright

    httpd, app = serve()
    url = f"http://127.0.0.1:{httpd.server_address[1]}"
    results = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        for theme in ("dark", "light"):
            for name, vp in (("desktop", {"width": 1366, "height": 860}), ("phone", {"width": 390, "height": 844})):
                page = browser.new_page(viewport=vp)
                page.add_init_script(f"try {{ localStorage.setItem('camr-theme', '{theme}') }} catch (e) {{}}")
                page.goto(url)
                page.wait_for_selector("#input")
                page.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
                for msg in ("remember that my bike lock code is 4471", "what is my bike lock code"):
                    page.fill("#input", msg)
                    page.click("#send")
                    page.wait_for_timeout(1200)
                if name == "desktop":
                    page.click("#panel-btn")
                    page.wait_for_timeout(400)
                page.add_script_tag(path=str(axe_js))
                res = page.evaluate("""async () => {
                    const r = await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21aa','wcag22aa','best-practice']}});
                    return {violations: r.violations.map(v => ({id: v.id, impact: v.impact, help: v.help,
                                nodes: v.nodes.length, targets: v.nodes.slice(0, 4).map(n => n.target.join(' '))})),
                            passes: r.passes.length, incomplete: r.incomplete.length};
                }""")
                results.append({"theme": theme, "viewport": name, **res})
                page.close()
        browser.close()
    httpd.shutdown()
    app.assistant.close()
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--axe", required=True, help="path to axe.min.js (axe-core 4.x)")
    ap.add_argument("--out", default=str(ROOT / "docs/results/ui_audit.json"))
    ap.add_argument("--label", default="after", help="before/after a fix, kept side by side in the output file")
    a = ap.parse_args()
    out = Path(a.out)
    data = json.loads(out.read_text()) if out.exists() else {}
    data[a.label] = {"contrast": contrast_table(), "axe": axe_audit(Path(a.axe))}
    out.write_text(json.dumps(data, indent=2))
    c = data[a.label]["contrast"]
    print("contrast failures:", [(r["theme"], r["fg"], r["bg"], r["ratio"]) for r in c if not r["pass_AA"]])
    for r in data[a.label]["axe"]:
        print(r["theme"], r["viewport"], "passes", r["passes"], "violations",
              [(v["id"], v["impact"], v["nodes"]) for v in r["violations"]])


if __name__ == "__main__":
    main()
