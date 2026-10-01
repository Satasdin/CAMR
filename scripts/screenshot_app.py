"""Capture CAMR Personal (camr app) screens with real answers from a local model.

Start the app first, e.g.  camr app --home /tmp/demo --port 8502
    python scripts/screenshot_app.py --url http://127.0.0.1:8502 --out docs/figures/app
"""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8502")
    ap.add_argument("--out", default="docs/figures/app")
    ap.add_argument("--ask", action="append", default=[], help="questions to ask on the Chat screen, in order")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        page = p.chromium.launch(executable_path=CHROME).new_page(viewport={"width": 1440, "height": 960})
        page.goto(a.url, timeout=60000)
        page.wait_for_selector("text=memory that grows", timeout=120000)
        page.wait_for_timeout(1500)
        msgs = "[data-testid='stChatMessage']"
        for i, q in enumerate(a.ask, start=1):
            box = page.locator("[data-testid='stChatInput'] textarea")
            box.fill(q)
            box.press("Enter")
            # finished = both messages of this exchange are rendered and the answer is no longer streaming
            page.wait_for_function(f"() => document.querySelectorAll(\"{msgs}\").length >= {2 * i}"
                                   " && !document.body.innerText.includes('▌')", timeout=600000)
            page.wait_for_timeout(3000)
        page.screenshot(path=str(out / "1_chat.png"), full_page=True)
        for i, screen in enumerate(["Teach", "Memory", "Growth", "Settings"], start=2):
            page.locator("section[data-testid='stSidebar']").get_by_text(screen, exact=True).first.click()
            page.wait_for_timeout(2500)
            page.screenshot(path=str(out / f"{i}_{screen.lower()}.png"), full_page=True)
            print("wrote", out / f"{i}_{screen.lower()}.png")


if __name__ == "__main__":
    main()
