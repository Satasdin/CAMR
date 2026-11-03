"""python -m engram.app [--memory DIR] [--port N] [--open] [--check]

  --open    open the app in the browser once it is listening
  --check   a health check instead of the app: downloads the models if needed, teaches CAMR two facts in a
            throwaway memory, asks about one, and prints PASS or FAIL with the time to the first word
"""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import threading
import time
import webbrowser
from pathlib import Path


def models_ready() -> bool:
    """Download CAMR's two models the first time (about 1.3 GB), then run offline."""
    from huggingface_hub import snapshot_download

    from engram.models import EMBEDDER, READER

    for repo in (READER, EMBEDDER):
        try:
            snapshot_download(repo, local_files_only=True)
        except Exception:
            print(f"Downloading {repo} (first run only)…", flush=True)
            snapshot_download(repo)
    os.environ["HF_HUB_OFFLINE"] = "1"
    return True


def record(ok: bool, reply, loaded_s: float) -> None:
    """Keep each health check as a test record, so its timings can be cited."""
    import datetime as dt
    import json

    from engram.ruler.harness import RECORDS, environment

    now = dt.datetime.now()
    out = RECORDS / "health" / now.strftime("%Y-%m-%d") / f"{now.strftime('%H%M%S')}-check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"kind": "health", "passed": ok, "question": "Where does my sister live?",
                               "answer": reply.text, "ttft_s": round(reply.ttft_s, 4), "gen_tps": round(reply.gen_tps, 1),
                               "models_loaded_s": round(loaded_s, 2), "environment": environment()}, indent=1))


def check() -> int:
    import datetime as dt

    from engram.memory import Memory
    from engram.models import Embedder, Reader

    t0 = time.perf_counter()
    reader, embedder = Reader(), Embedder()
    loaded = time.perf_counter() - t0
    tmp = Path(tempfile.mkdtemp(prefix="camr-check-"))
    try:
        m = Memory(reader, embedder, tmp / "memory")
        m.remember("[2026-01-05] My sister Amina moved to Nakuru last week.", 0)
        m.remember("[2026-01-06] Paid the electricity bill.", 1)
        reply = m.answer("Where does my sister live?", dt.date(2026, 1, 7))
        ok = "nakuru" in reply.text.lower()
        print(f"Models loaded in {loaded:.1f} s. Asked: Where does my sister live?  CAMR said: {reply.text}")
        print(f"First word after {reply.ttft_s * 1000:.0f} ms, writing at {reply.gen_tps:.0f} tokens/s.")
        print("PASS: CAMR remembered and answered." if ok else "FAIL: the answer did not name Nakuru.")
        m.close()
        record(ok, reply, loaded)
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m engram.app")
    ap.add_argument("--memory", type=Path, default=Path.home() / ".engram" / "default")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--open", action="store_true", help="open the app in the browser")
    ap.add_argument("--check", action="store_true", help="run the health check and exit")
    a = ap.parse_args()
    models_ready()
    if a.check:
        raise SystemExit(check())
    from engram.app.server import App, serve

    app = App(a.memory)
    if a.open:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{a.port}")).start()
    serve(app, a.port)


if __name__ == "__main__":
    main()
