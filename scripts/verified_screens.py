"""Screenshots of verified answers in CAMR Personal (deterministic: the test doubles stand in for the model and web).

    python scripts/verified_screens.py --out docs/figures/app

Three turns in one chat: a fact read straight from memory (no model call), an answer memory does
not confirm, the same question in strict mode, and an answer confirmed from its own article.
Each in the dark and the light theme.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs/figures/app"))
    out = Path(ap.parse_args().out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright

    from camr.app.assistant import Assistant
    from camr.app.server import App, make_handler
    from camr.memory.embedder import HashingEmbedder
    from camr.memory.fetch import WebLookup
    from test_app_learning import ByModel
    from test_learning import INFOBOX_PAGE, FakeWeb, ddg_article

    web = FakeWeb({"The Burning Train": ddg_article("The Burning Train", "The Burning Train is a 1980 Indian "
                                                                         "Hindi-language disaster film."),
                   "The Loudwater Mystery": ddg_article("The Loudwater Mystery", "The Loudwater Mystery is a 1921 "
                                                                                 "British silent crime film."),
                   "Walter West": ddg_article("Walter West", "Walter West was a British film director and "
                                                             "producer. He directed The Loudwater Mystery in 1921."),
                   "Paris Express": ddg_article("Paris Express", "Paris Express is a 1953 British crime film.")},
                  html={"The Burning Train": INFOBOX_PAGE})
    answers = {"qwen2.5:0.5b": "Walter West"}
    home = Path(tempfile.mkdtemp(prefix="camr-shots-"))
    app = App(home, "http://127.0.0.1:11434")
    app.assistant = Assistant(home, model="qwen2.5:0.5b", embedder=HashingEmbedder(384),
                              session=ByModel(answers), min_similarity=0.3,
                              web_lookup=WebLookup(web, min_interval_s=0))
    app.ollama_models = lambda: [{"name": "qwen2.5:0.5b", "size_gb": 0.4, "parameters": "494M", "family": "qwen2",
                                  "embedding": False}]
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}"
    with sync_playwright() as pw:
        exe = "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None
        try:
            browser = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        except Exception:  # noqa: BLE001
            browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1180}, device_scale_factor=1.5)
        page.goto(url)
        page.wait_for_selector("#input")

        def ask(q):
            n = page.locator(".actions").count()
            page.fill("#input", q)
            page.keyboard.press("Enter")
            page.wait_for_function(f"document.querySelectorAll('.actions .act, .actions .verify').length > 0 && "
                                   f"document.querySelectorAll('.actions').length > {n}", timeout=20000)
            page.wait_for_timeout(400)

        ask("Who was the director of The Burning Train?")            # straight from memory, no model call
        ask("Who directed The Loudwater Mystery?")                   # memory lacks it: confirmed by his own article
        answers["qwen2.5:0.5b"] = "Carol Reed"
        ask("Who was the director of Paris Express?")               # nothing confirms it
        app.assistant.save_settings(verified_only=True)
        ask("Who directed Paris Express?")                          # strict mode: a lead, not a fact
        page.evaluate("document.querySelectorAll('details.recall').forEach(d => d.open = false)")
        for theme in ("dark", "light"):
            page.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            page.wait_for_timeout(200)
            page.screenshot(path=str(out / f"{theme}_7_verified.png"))
            print(out / f"{theme}_7_verified.png")
        browser.close()
    httpd.shutdown()
    app.assistant.close()


if __name__ == "__main__":
    main()
