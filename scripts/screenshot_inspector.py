"""Capture the four CAMR Inspector screens as PNGs (evidence for Chapter 5).

    python scripts/screenshot_inspector.py --run-dir results/pilot --out docs/figures/pilot
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

SCREENS = ["Run Dashboard", "Ablations", "Query Trace", "Memory Store"]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default=None, help="treatment label to select in the sidebar")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    port = free_port()
    app = Path(__file__).resolve().parent.parent / "camr" / "inspect" / "app.py"
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(app), "--server.headless", "true", "--server.port", str(port),
         "--server.address", "127.0.0.1", "--browser.gatherUsageStats", "false", "--", "--run-dir", args.run_dir],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
            for _ in range(60):
                try:
                    page.goto(f"http://127.0.0.1:{port}", timeout=5000)
                    break
                except Exception:  # server still starting
                    time.sleep(1)
            page.wait_for_selector("text=CAMR Inspector", timeout=60000)
            for i, screen in enumerate(SCREENS, start=1):
                page.get_by_text(screen, exact=True).first.click()
                page.wait_for_timeout(2500)
                page.wait_for_load_state("networkidle")
                errors = page.locator("[data-testid='stException']").count()
                path = out / f"{i}_{screen.lower().replace(' ', '_')}.png"
                page.screenshot(path=str(path), full_page=True)
                print(f"{path} exceptions={errors}")
            browser.close()
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
