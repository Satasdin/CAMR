"""Capture CAMR Personal screens with real answers from a local model.

Start the app first:  camr app --home /tmp/demo --port 8510 --no-browser
    python scripts/screenshot_app.py --url http://127.0.0.1:8510 --out docs/figures/app --ask "When is my dentist appointment?"
"""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8510")
    ap.add_argument("--out", default="docs/figures/app")
    ap.add_argument("--ask", action="append", default=[], help="questions to send, in order")
    ap.add_argument("--theme", default="dark", choices=["dark", "light"])
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t = a.theme
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme=t, device_scale_factor=1)
        page.add_init_script(f"localStorage.setItem('camr-theme', '{t}')")
        page.goto(a.url)
        page.wait_for_selector("#input", state="visible", timeout=120000)
        page.wait_for_timeout(1200)
        page.screenshot(path=str(out / f"{t}_1_home.png"))
        for i, q in enumerate(a.ask, start=1):
            page.fill("#input", q)
            page.keyboard.press("Enter")
            page.wait_for_function(f"() => document.querySelectorAll('.msg.assistant .actions').length >= {i}"
                                   " && ![...document.querySelectorAll('.answer')].some(e => e.classList.contains('cursor'))",
                                   timeout=600000)
            page.wait_for_timeout(800)
        if a.ask:
            # open the first recall card so the memories are visible, then the memory panel
            page.locator("details.recall:not(.none)").first.evaluate("e => e.open = true")
            page.wait_for_timeout(300)
            page.screenshot(path=str(out / f"{t}_2_chat.png"))
            page.click("#panel-btn")
            page.wait_for_timeout(500)
            page.screenshot(path=str(out / f"{t}_3_panel_recall.png"))
            page.click(".tab[data-tab=growth]")
            page.wait_for_timeout(500)
            page.screenshot(path=str(out / f"{t}_4_panel_growth.png"))
            page.click(".tab[data-tab=memory]")
            page.wait_for_timeout(600)
            page.screenshot(path=str(out / f"{t}_5_panel_memory.png"))
        # mobile layout
        m = browser.new_page(viewport={"width": 390, "height": 844}, color_scheme=t, device_scale_factor=2)
        m.add_init_script(f"localStorage.setItem('camr-theme', '{t}')")
        m.goto(a.url)
        m.wait_for_selector("#input", state="visible")
        m.wait_for_timeout(1000)
        m.screenshot(path=str(out / f"{t}_6_mobile.png"))
        print("wrote", sorted(x.name for x in out.glob(f"{t}_*.png")))


if __name__ == "__main__":
    main()
