"""The models loaded in this server: the reader the memory was opened with (at launch) and at most one more, picked on
the Models screen. One model is loaded at a time, in the background, and what it took (seconds, and the RAM MLX
holds for it) is measured as it happens; there is no progress to report while MLX reads the files, so none is shown.

Unloading drops the model and gives its memory back to the system. The memory's own reader stays while the memory
is open: its rooms were written by it, and another model could not read them.
"""

from __future__ import annotations

import gc
import sys
import threading
import time
from typing import Callable


def _active_bytes() -> int | None:
    mx = sys.modules.get("mlx.core")
    if mx is None:
        return None
    try:
        return int(mx.get_active_memory())
    except Exception:  # noqa: BLE001
        return None


def _clear() -> None:
    mx = sys.modules.get("mlx.core")
    if mx is not None:
        try:
            mx.clear_cache()
        except Exception:  # noqa: BLE001
            pass


def mlx_reader(repo: str):
    """A Reader for a model already in the Hugging Face cache (never a download)."""
    from huggingface_hub import snapshot_download

    from engram.models import Reader

    path = snapshot_download(repo, local_files_only=True, token=False)
    reader = Reader(path)
    reader.repo = repo
    return reader


class Runtime:
    def __init__(self, loader: Callable[[str], object] = mlx_reader):
        self.loader = loader
        self.lock = threading.Lock()
        self.memory: dict | None = None  # {repo, model}: the reader the memory uses
        self.picked: dict | None = None  # {repo, model, bytes, load_s, at}
        self.job: dict | None = None  # {repo, state: loading|failed, started, error}

    def adopt(self, reader) -> None:
        """The memory's reader, loaded at launch."""
        with self.lock:
            self.memory = {"repo": getattr(reader, "repo", None), "model": reader}

    def busy(self) -> bool:
        return self.job is not None and self.job["state"] == "loading"

    def load(self, repo: str) -> dict:
        """Start loading ``repo`` in the background, in place of the model picked before."""
        with self.lock:
            if self.busy():
                raise RuntimeError(f"already loading {self.job['repo']}")
            if self.memory and self.memory["repo"] == repo:
                raise RuntimeError("that model is loaded already, as the memory's reader")
            self.job = {"repo": repo, "state": "loading", "started": time.time(), "error": None}
        threading.Thread(target=self._load, args=(repo,), daemon=True).start()
        return self.state()

    def _load(self, repo: str) -> None:
        self._drop()
        before = _active_bytes()
        t = time.perf_counter()
        try:
            model = self.loader(repo)
        except Exception as e:  # noqa: BLE001 (shown on the model's row)
            with self.lock:
                self.job = {**self.job, "state": "failed", "error": f"{type(e).__name__}: {e}"[:240]}
            return
        after = _active_bytes()
        with self.lock:
            self.picked = {"repo": repo, "model": model, "load_s": round(time.perf_counter() - t, 2),
                           "bytes": after - before if before is not None and after is not None else None,
                           "at": time.time()}
            self.job = None

    def unload(self, repo: str | None = None) -> dict:
        with self.lock:
            if self.memory and repo is not None and self.memory["repo"] == repo:
                raise RuntimeError("the memory's reader stays while the memory is open")
            if self.busy():
                raise RuntimeError("a model is loading")
            if repo is not None and (self.picked is None or self.picked["repo"] != repo):
                raise KeyError(repo)
        self._drop()
        return self.state()

    def _drop(self) -> None:
        with self.lock:
            self.picked = None
        gc.collect()
        _clear()

    def reader(self):
        """The model to talk to: the one picked on the Models screen, else the memory's reader, else None."""
        with self.lock:
            slot = self.picked or self.memory
            return slot["model"] if slot else None

    def state(self) -> dict:
        def show(slot):
            return None if slot is None else {k: v for k, v in slot.items() if k != "model"}

        with self.lock:
            return {"memory": show(self.memory), "picked": show(self.picked), "job": dict(self.job) if self.job
                    else None, "active_bytes": _active_bytes()}
