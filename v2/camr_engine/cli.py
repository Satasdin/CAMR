"""The ``camr`` command: one name for the engine's doors.

    camr serve [--backend ollama|lmstudio|mlx] [--port 11436]   an OpenAI-compatible endpoint with memory
    camr ollama [--port 11435]                                   memory for the ollama CLI (OLLAMA_HOST)
    camr app [--open] [--fixture DIR]                            the app, at http://127.0.0.1:8765
    camr doctor                                                  what is installed and what is listening
    camr bench                                                   where the benchmarks and their records are
    camr version

Each subcommand takes its own options (``camr serve --help``). Nothing here loads a model: ``serve`` and ``ollama``
load only the embedder, and ``doctor`` only looks.
"""

from __future__ import annotations

import http.client
import platform
import shutil
import sys
from pathlib import Path

from camr_engine import __version__

HELP = __doc__.split("\n\n")[1]
BENCH = """The benchmarks run from a clone of the repository (https://github.com/Satasdin/CAMR, folder v2), not from
an installed engine: they need the scripted history and write their records beside the code.

  build the Long Haul:   python -m camr_engine.bench.haul build --seed 1 --out work/haul/s1
  the engine on it:      python -m camr_engine.bench.local longhaul --contender engine:qwen3-4b --dir work/haul/s1
  Ollama + memory:       python -m camr_engine.bench.ollama_run longhaul --contender ollama:qwen3-1.7b --dir work/haul/s1
  Claude alone:          python -m camr_engine.bench.longhaul claude --model claude-sonnet-5-5 --dir work/haul/s1
  the Hugging Face suites: python -m camr_engine.bench.suites list

Records: v2/records/bench/<date>/*.json. How each is run: v2/docs/site/benchmarks.md.
The app's Bench screen (camr app) shows every record, live."""
LOCAL = (  # what doctor looks for on this Mac: name, port, path that answers when it is up
    ("Ollama", 11434, "/api/version"),
    ("LM Studio server", 1234, "/v1/models"),
    ("mlx_lm.server", 8080, "/v1/models"),
    ("CAMR endpoint (camr serve)", 11436, "/v1/models"),
    ("CAMR Ollama pairing (camr ollama)", 11435, "/api/version"),
    ("CAMR app (camr app)", 8765, "/"),
)


def _get(port: int, path: str, timeout: float = 1.5) -> tuple[int, bytes] | None:
    """GET ``path`` on 127.0.0.1:``port``: its status and body, or None when nothing answers."""
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
        c.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
        r = c.getresponse()
        out = r.status, r.read()
        c.close()
        return out
    except (OSError, http.client.HTTPException):
        return None


def _cached(repo: str) -> bool:
    """Whether a model is already downloaded (nothing is fetched)."""
    try:
        from huggingface_hub import snapshot_download

        snapshot_download(repo, local_files_only=True)
        return True
    except Exception:
        return False


def doctor(argv: list[str]) -> int:
    """What is installed and what is listening. Loads no model and reaches nothing past 127.0.0.1."""
    memory = Path(argv[argv.index("--memory") + 1]).expanduser() if "--memory" in argv[:-1] else \
        Path.home() / ".camr" / "default"
    bad = 0

    def say(ok: bool | None, what: str, note: str = "") -> None:
        mark = {True: "ok", False: "!!", None: "--"}[ok]
        print(f"  {mark}  {what}" + (f"  ({note})" if note else ""))

    print(f"CAMR {__version__}, from {Path(__file__).resolve().parent}")
    v = sys.version_info
    say(v >= (3, 11), f"Python {v.major}.{v.minor}.{v.micro}", "" if v >= (3, 11) else "3.11 or newer is needed")
    bad += v < (3, 11)
    mac = platform.system() == "Darwin" and platform.machine() == "arm64"
    say(mac, f"{platform.system()} {platform.machine()}", "" if mac else "the engine runs its models on Apple silicon")
    bad += not mac
    try:
        import mlx.core as mx

        say(True, f"MLX {getattr(mx, '__version__', '')}".strip())
    except Exception as e:
        say(False, "MLX", f"{type(e).__name__}: the embedder and the engine need it")
        bad += 1
    from camr_engine.models import EMBEDDER, READER

    for repo, use in ((EMBEDDER, "memory's embedder"), (READER, "the app's reader")):
        here = _cached(repo)
        say(True if here else None, f"{repo} ({use})", "" if here else "downloaded on first use")
    print("Listening on this Mac:")
    for name, port, path in LOCAL:
        got = _get(port, path)
        note = "not running" if got is None else ("" if got[0] < 500 else f"up, but answers {got[0]}")
        say(True if got and got[0] < 500 else None, f"{name}, 127.0.0.1:{port}", note)
    notes = memory / "ollama" / "notes.jsonl"
    count = sum(1 for _ in notes.open()) if notes.exists() else 0
    free = shutil.disk_usage(memory if memory.exists() else Path.home()).free / 1e9
    say(True if memory.exists() else None, f"memory {memory}",
        f"{count} notes, {free:.0f} GB free" if memory.exists() else "made on first use")
    on_path = shutil.which("camr")
    say(True if on_path else None, "camr on PATH", on_path or "add ~/.local/bin to PATH")
    print("Next: camr serve --backend ollama, then point an OpenAI client at http://127.0.0.1:11436/v1"
          if not bad else "Fix the lines marked !! first.")
    return 1 if bad else 0


def app(argv: list[str]) -> int:
    from camr_engine.app.__main__ import main as run

    sys.argv = ["camr app", *argv]  # the app reads its own options from sys.argv
    run()
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd, rest = (argv[0], argv[1:]) if argv else ("", [])
    if cmd == "serve":
        from camr_engine.pair.openai import main as serve

        serve(rest, prog="camr serve")
    elif cmd == "ollama":
        from camr_engine.pair.ollama import main as pair

        pair(rest, prog="camr ollama")
    elif cmd == "app":
        return app(rest)
    elif cmd == "doctor":
        return doctor(rest)
    elif cmd == "bench":
        print(BENCH)
    elif cmd in ("version", "--version", "-V"):
        print(f"camr {__version__}")
    elif cmd in ("", "help", "--help", "-h"):
        print(f"CAMR {__version__}: memory for on-device language models.\n\n{HELP}")
    else:
        print(f"camr: no command {cmd!r}\n\n{HELP}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
