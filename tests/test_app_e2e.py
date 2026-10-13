"""End-to-end interface tests: a real browser (Chromium via Playwright) drives CAMR Personal.

The model and embedder are the deterministic test doubles of test_app.py, so the tests check the
interface's behaviour (what the user sees and can do), not model quality. They are skipped where
no browser is installed.
"""

from __future__ import annotations

import os
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from camr.app.assistant import Assistant
from camr.app.server import App, make_handler
from camr.memory.embedder import HashingEmbedder
from test_app import FakeOllama

sync_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser():
    pw = sync_api.sync_playwright().start()
    # a pinned browser build, else a system Chromium (e.g. one installed beside a different Playwright version)
    candidates = [None, os.environ.get("CAMR_CHROMIUM"), "/opt/pw-browsers/chromium"]
    b = None
    for exe in candidates:
        if exe is not None and not Path(exe).exists():
            continue
        try:
            b = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
            break
        except Exception:
            continue
    if b is None:
        pw.stop()
        pytest.skip("no Chromium available")
    yield b
    b.close()
    pw.stop()


@pytest.fixture
def url(tmp_path):
    app = App(tmp_path, "http://127.0.0.1:11434")
    app.assistant = Assistant(tmp_path, model="tiny:1b", embedder=HashingEmbedder(384), session=FakeOllama(),
                              min_similarity=0.3)
    app.ollama_models = lambda: [{"name": "tiny:1b", "size_gb": 1.0, "parameters": "1B", "family": "x",
                                  "embedding": False}]
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    app.assistant.close()


def send(page, text):
    page.fill("#input", text)
    page.click("#send")
    page.wait_for_function("document.querySelectorAll('.msg.assistant .acts, .msg.assistant .actions').length > 0 "
                           "|| document.querySelectorAll('.msg.assistant').length >= 1 && !document.querySelector('.thinking')",
                           timeout=15000)


def test_remember_then_ask_shows_recalled_memory_before_the_answer(browser, url):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(url)
    page.wait_for_selector("#input")
    send(page, "remember that my bike lock code is 4471")
    page.wait_for_selector("text=I'll remember that", timeout=15000)
    send(page, "what is my bike lock code")
    page.wait_for_selector(".msg.assistant >> nth=1", timeout=15000)
    page.wait_for_selector("text=4471", timeout=15000)
    recall = page.locator(".recall").last.inner_text()
    assert "Recalled 1" in recall or "memor" in recall.lower()
    assert page.locator("#mem-badge").inner_text().strip() not in ("", "0")
    page.close()


def test_empty_message_is_not_sent(browser, url):
    page = browser.new_page()
    page.goto(url)
    page.wait_for_selector("#input")
    page.fill("#input", "   ")
    page.click("#send")
    page.wait_for_timeout(500)
    assert page.locator(".msg.user").count() == 0
    page.close()


def test_thumbs_up_teaches_the_answer(browser, url):
    page = browser.new_page()
    page.goto(url)
    page.wait_for_selector("#input")
    send(page, "remember that the gym opens at 06:00")
    send(page, "when does the gym open")
    page.wait_for_selector("button.act.up", timeout=15000)
    before = int(page.locator("#mem-badge").inner_text() or 0)
    page.locator("button.act.up").last.click()
    page.wait_for_selector("text=Learned", timeout=10000)
    page.wait_for_function(f"Number(document.querySelector('#mem-badge').textContent) > {before}", timeout=10000)
    page.close()


def test_theme_toggle_and_memory_panel(browser, url):
    page = browser.new_page()
    page.goto(url)
    page.wait_for_selector("#input")
    start = page.evaluate("document.documentElement.dataset.theme || 'dark'")
    page.click("#theme-btn")
    assert page.evaluate("document.documentElement.dataset.theme || 'dark'") != start
    page.click("#panel-btn")
    page.wait_for_selector("#panel", state="visible")
    assert page.locator(".app.panel-open").count() == 1
    page.close()


def test_phone_width_layout_keeps_the_composer_usable(browser, url):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(url)
    page.wait_for_selector("#input")
    box = page.locator("#composer").bounding_box()
    assert box and box["width"] <= 390 and box["x"] >= 0
    width = page.evaluate("document.documentElement.scrollWidth")
    assert width <= 390  # no horizontal scrolling on a phone
    page.close()


def test_keyboard_only_user_can_reach_the_composer_and_send(browser, url):
    page = browser.new_page()
    page.goto(url)
    page.wait_for_selector("#input")
    page.evaluate("document.activeElement && document.activeElement.blur()")
    reached = False
    for _ in range(40):  # Tab through the page as a keyboard-only user would
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement && document.activeElement.id") == "input":
            reached = True
            break
    assert reached, "the message box is not reachable with Tab"
    page.keyboard.type("remember that the spare key is under the blue pot")
    page.keyboard.press("Enter")
    page.wait_for_selector("text=I'll remember that", timeout=15000)
    # every focusable control has an accessible name (text, aria-label or title)
    unnamed = page.evaluate("""() => [...document.querySelectorAll('button, [href], input, textarea, select')]
        .filter(e => e.offsetParent !== null)
        .filter(e => !(e.innerText || '').trim() && !e.getAttribute('aria-label') && !e.getAttribute('title')
                     && !(e.labels && e.labels.length) && !e.getAttribute('placeholder'))
        .map(e => e.outerHTML.slice(0, 80))""")
    assert unnamed == []
    page.close()
