"""python -m engram.app [--memory DIR] [--port N]"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m engram.app")
    ap.add_argument("--memory", type=Path, default=Path.home() / ".engram" / "default")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from engram.app.server import App, serve

    serve(App(a.memory), a.port)


if __name__ == "__main__":
    main()
