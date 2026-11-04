"""python -m engram.app.fetch <mlx-community/repo>: download one model into the Hugging Face cache, with no token.

The Models screen runs this as a child process, so pausing stops it at once; the server reads the progress from the
bytes landing in the cache. Run again, it carries on from what is already there.
"""

from __future__ import annotations

import sys


def main() -> int:
    from engram.app.hub import PATTERNS, repo_ok

    if len(sys.argv) != 2 or not repo_ok(sys.argv[1]):
        print("usage: python -m engram.app.fetch mlx-community/<name>", file=sys.stderr)
        return 2
    from huggingface_hub import snapshot_download

    try:
        snapshot_download(sys.argv[1], token=False, allow_patterns=list(PATTERNS))
    except Exception as e:  # noqa: BLE001 (the reason is shown on the model's row)
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
