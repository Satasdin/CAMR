"""python -m camr_engine.app [--memory DIR] [--port N] [--check] [--fixture DIR] [--model REPO] [--live]

The engine behind CAMR for Mac (mac/build.sh --open builds and opens the app, which starts this itself).

  --fixture  serve a recorded memory folder read-only, with no model loaded (its state says fixture)
  --model    the memory's reader (a Hugging Face repo already downloaded); a memory folder keeps one model's notes
  --live     print each layer's weights as they load (camr_engine.live), one CAMR-LIVE line each, for the Mac app
  --check   a health check instead of the engine: downloads the models if needed, teaches CAMR two facts in a
            throwaway memory, asks about one, and prints PASS or FAIL with the time to the first word
"""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import time
from pathlib import Path


def models_ready(reader: str | None = None) -> bool:
    """Download CAMR's two models the first time (about 1.3 GB), then run offline."""
    from huggingface_hub import snapshot_download

    from camr_engine.models import EMBEDDER, READER

    for repo in (reader or READER, EMBEDDER):
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

    from camr_engine.ruler.harness import RECORDS, environment

    now = dt.datetime.now()
    out = RECORDS / "health" / now.strftime("%Y-%m-%d") / f"{now.strftime('%H%M%S')}-check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"kind": "health", "passed": ok, "question": "Where does my sister live?",
                               "answer": reply.text, "ttft_s": round(reply.ttft_s, 4), "gen_tps": round(reply.gen_tps, 1),
                               "models_loaded_s": round(loaded_s, 2), "environment": environment()}, indent=1))


def check() -> int:
    import datetime as dt

    from camr_engine.memory import Memory
    from camr_engine.models import Embedder, Reader

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
    ap = argparse.ArgumentParser(prog="python -m camr_engine.app")
    ap.add_argument("--memory", type=Path, default=Path.home() / ".camr" / "default")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--check", action="store_true", help="run the health check and exit")
    ap.add_argument("--fixture", type=Path, help="serve this recorded memory folder read-only, loading no model")
    ap.add_argument("--model", help="the memory's reader, a Hugging Face repo (default: CAMR's own)")
    ap.add_argument("--live", action="store_true", help="print the weights loading, layer by layer, on stdout")
    a = ap.parse_args()
    if a.fixture is not None:
        from camr_engine.app.fixture import Fixture
        from camr_engine.app.server import serve

        return serve(Fixture(a.fixture), a.port)
    models_ready(a.model)
    if a.check:
        raise SystemExit(check())
    from camr_engine.app.server import App, serve
    from camr_engine.live import Live, reporting, stdout_line

    with reporting(Live("load", echo=stdout_line) if a.live else None):
        app = App(a.memory, a.model)
    serve(app, a.port)


if __name__ == "__main__":
    main()
