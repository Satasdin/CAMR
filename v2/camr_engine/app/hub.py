"""Models to run: those already on this Mac (the Hugging Face cache and Ollama), and the mlx-community models on
Hugging Face, searched through its public API with no token.

The page never calls Hugging Face itself: it asks the local server, which calls the public API and keeps each answer
for a while. Downloads use huggingface_hub in a child process (``camr_engine.app.fetch``), so a pause stops it at once;
progress is the bytes landing in the cache, read from the disk, never guessed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

API = "https://huggingface.co"
AUTHOR = "mlx-community"
OLLAMA = "http://127.0.0.1:11434"
PATTERNS = ("*.json", "*.safetensors", "*.txt", "*.model", "*.jinja", "*.tiktoken")  # what a download fetches
CHAT = {"text-generation", "image-text-to-text", None}
AUDIO = {"automatic-speech-recognition", "text-to-speech", "audio", "speech", "asr", "tts", "audio-to-audio"}
TTL_S = 600
_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_cache: dict[str, tuple[float, object]] = {}
_lock = threading.Lock()


def repo_ok(repo: str, *, author: str | None = AUTHOR) -> bool:
    """A plain ``owner/name`` repository id (from ``author`` when given), with nothing that could leave a folder."""
    return bool(isinstance(repo, str) and _REPO.match(repo) and ".." not in repo
                and (author is None or repo.split("/")[0] == author))


def cache_dir() -> Path:
    """The Hugging Face cache this Mac uses."""
    try:
        from huggingface_hub import constants

        return Path(constants.HF_HUB_CACHE)
    except ImportError:
        home = os.environ.get("HF_HOME") or str(Path.home() / ".cache" / "huggingface")
        return Path(os.environ.get("HF_HUB_CACHE") or Path(home) / "hub")


def _get(url: str, timeout: float = 10.0):
    """GET a public URL as JSON, with no credentials of any kind."""
    req = urllib.request.Request(url, headers={"User-Agent": "camr-app", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed https host)
        return json.loads(r.read())


def _kept(key: str, make: Callable[[], object], ttl: float = TTL_S):
    with _lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < ttl:
            return hit[1]
    value = make()
    with _lock:
        _cache[key] = (time.monotonic(), value)
    return value


# -- Hugging Face


def search(query: str = "", *, sort: str = "downloads", limit: int = 30, chat: bool = True,
           get: Callable = _get) -> list[dict]:
    """mlx-community models matching ``query`` (all of them when empty), most downloaded first (or ``trending``,
    ``likes``, ``modified``)."""
    sort = {"downloads": "downloads", "trending": "trendingScore", "likes": "likes",
            "modified": "lastModified"}.get(sort, "downloads")
    params = [("author", AUTHOR), ("sort", sort), ("direction", "-1"), ("limit", str(max(1, min(limit, 100))))]
    if query.strip():
        params.append(("search", query.strip()[:80]))
    for e in ("downloads", "likes", "lastModified", "safetensors", "config", "pipeline_tag", "library_name", "tags"):
        params.append(("expand[]", e))
    url = f"{API}/api/models?{urllib.parse.urlencode(params)}"
    rows = _kept(url, lambda: get(url))
    out = []
    for r in rows if isinstance(rows, list) else []:
        cfg = r.get("config") or {}
        if chat and not talks(r, cfg):
            continue
        q = cfg.get("quantization_config") or {}
        out.append({"repo": r.get("id"), "downloads": r.get("downloads"), "likes": r.get("likes"),
                    "modified": r.get("lastModified"), "pipeline": r.get("pipeline_tag"),
                    "library": r.get("library_name"), "family": cfg.get("model_type"),
                    "bits": q.get("bits"), "params": (r.get("safetensors") or {}).get("total")})
    return out


def talks(r: dict, cfg: dict) -> bool:
    """A model you can chat with: a text or image-and-text generator, not speech, audio or an encoder."""
    if r.get("pipeline_tag") not in CHAT or r.get("library_name") not in ("mlx", "transformers", None):
        return False
    if set(r.get("tags") or []) & AUDIO:
        return False
    arch = " ".join(cfg.get("architectures") or [])
    return bool(arch) and any(k in arch for k in ("CausalLM", "ConditionalGeneration", "LMHead", "ForCausal"))


def _wanted(path: str) -> bool:
    from fnmatch import fnmatch

    return "/" not in path and any(fnmatch(path, p) for p in PATTERNS)


def info(repo: str, *, get: Callable = _get) -> dict:
    """One repository: its config and the files a download would fetch, with their sizes."""
    if not repo_ok(repo, author=None):
        raise ValueError("not a repository id")

    def make() -> dict:
        tree = get(f"{API}/api/models/{repo}/tree/main?recursive=true")
        files = [{"path": f["path"], "size": int((f.get("lfs") or {}).get("size") or f.get("size") or 0)}
                 for f in tree if f.get("type", "file") == "file"]
        cfg = get(f"{API}/{repo}/resolve/main/config.json")
        wanted = [f for f in files if _wanted(f["path"])]
        return {"repo": repo, "config": cfg, "files": wanted,
                "weights_bytes": sum(f["size"] for f in wanted if f["path"].endswith(".safetensors")),
                "download_bytes": sum(f["size"] for f in wanted)}

    return _kept(f"info:{repo}", make)


def infos(repos: list[str], *, get: Callable = _get) -> dict[str, dict]:
    """Several repositories at once, eight requests in flight; a failure is reported for that repository only."""
    def one(repo: str) -> tuple[str, dict]:
        try:
            return repo, info(repo, get=get)
        except Exception as e:  # noqa: BLE001 (shown on its row)
            return repo, {"repo": repo, "error": f"{type(e).__name__}: {e}"[:200]}

    with ThreadPoolExecutor(8) as pool:
        return dict(pool.map(one, repos))


# -- on this Mac


def _folder(repo: str, root: Path) -> Path:
    return root / ("models--" + repo.replace("/", "--"))


def local(root: Path | None = None) -> list[dict]:
    """Models in the Hugging Face cache: their config, weights bytes, bytes on disk, and whether every weights file
    named in the index is there."""
    root = cache_dir() if root is None else Path(root)
    out = []
    if not root.is_dir():
        return out
    for d in sorted(root.glob("models--*--*")):
        repo = d.name[len("models--"):].replace("--", "/", 1)
        snaps = sorted((d / "snapshots").glob("*/"), key=lambda p: p.stat().st_mtime) if (d / "snapshots").is_dir() \
            else []
        snap = snaps[-1] if snaps else None
        cfg = None
        if snap is not None and (snap / "config.json").exists():
            try:
                cfg = json.loads((snap / "config.json").read_text())
            except (OSError, ValueError):
                cfg = None
        weights = [p for p in snap.glob("*.safetensors")] if snap else []
        want = set()
        if snap is not None and (snap / "model.safetensors.index.json").exists():
            try:
                want = set(json.loads((snap / "model.safetensors.index.json").read_text())["weight_map"].values())
            except (OSError, ValueError, KeyError):
                want = set()
        have = {p.name for p in weights if p.exists()}
        complete = bool(cfg) and bool(have) and want <= have
        out.append({"repo": repo, "snapshot": str(snap) if snap else None, "config": cfg,
                    "weights_bytes": sum(p.stat().st_size for p in weights if p.exists()),
                    "disk_bytes": landed(repo, root), "complete": complete})
    return out


def landed(repo: str, root: Path | None = None) -> int:
    """Bytes of ``repo`` on this disk now, finished files and the ones still arriving. A finished blob may be a link
    into the cache's shared store (huggingface_hub 2.x), so links are followed."""
    blobs = _folder(repo, cache_dir() if root is None else Path(root)) / "blobs"
    total = 0
    if blobs.is_dir():
        with os.scandir(blobs) as it:
            for e in it:
                try:
                    total += e.stat(follow_symlinks=True).st_size
                except OSError:  # a dangling link
                    pass
    return total


def ollama(get: Callable = _get) -> dict:
    """Ollama's models on this Mac (its local server), each with the shapes ``/api/show`` gives; ``running`` is
    False when Ollama is not answering."""
    try:
        tags = get(f"{OLLAMA}/api/tags", timeout=1.0)
    except Exception:  # noqa: BLE001
        return {"running": False, "models": []}
    models = []
    for m in tags.get("models", []):
        shape = _kept(f"ollama:{m.get('digest')}", lambda m=m: _show(m["name"]), ttl=3600)
        models.append({"name": m.get("name"), "size": m.get("size"), "details": m.get("details") or {},
                       "shape": shape})
    return {"running": True, "models": models}


def _show(name: str) -> dict:
    data = json.dumps({"model": name}).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/show", data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=2.0) as r:  # noqa: S310 (local Ollama)
            info_ = json.loads(r.read()).get("model_info") or {}
    except Exception:  # noqa: BLE001
        return {}
    arch = info_.get("general.architecture", "")
    pick = {k.split(".", 1)[1]: v for k, v in info_.items() if k.startswith(arch + ".") and not isinstance(v, list)}
    return {"architecture": arch, "params": info_.get("general.parameter_count"), **pick}


def ollama_config(m: dict) -> dict:
    """An Ollama model's shapes as a config.json would give them, so one anatomy reader serves both."""
    s = m.get("shape") or {}
    n = int(s.get("block_count") or 0)
    heads = int(s.get("attention.head_count") or 1)
    cfg = {"num_hidden_layers": n, "hidden_size": s.get("embedding_length"), "num_attention_heads": heads,
           "num_key_value_heads": s.get("attention.head_count_kv") or heads,
           "head_dim": s.get("attention.key_length"), "intermediate_size": s.get("feed_forward_length"),
           "max_position_embeddings": s.get("context_length"), "model_type": s.get("architecture"),
           "vocab_size": 151936 if s.get("architecture", "").startswith("qwen") else None,
           "quantization": {"bits": 4, "group_size": 32, "mode": "gguf"}}
    if s.get("full_attention_interval"):
        cfg["full_attention_interval"] = s["full_attention_interval"]
    return cfg


# -- downloads


@dataclass
class Job:
    repo: str
    total: int | None
    state: str = "downloading"  # downloading, paused, done or failed
    bytes: int = 0
    rate: float | None = None  # bytes per second, over the last few seconds
    error: str | None = None
    started: float = field(default_factory=time.time)
    proc: object = None
    samples: list = field(default_factory=list)

    def to_dict(self) -> dict:
        left = (self.total - self.bytes) / self.rate if self.rate and self.total and self.bytes < self.total else None
        return {"repo": self.repo, "state": self.state, "bytes": self.bytes, "total": self.total,
                "rate_bps": round(self.rate) if self.rate else None, "eta_s": round(left) if left else None,
                "error": self.error}


def _spawn(repo: str):
    """The download's child process. Its errors go to a temporary file (a pipe nobody reads could fill and stall
    it), and its progress bars are off."""
    err = tempfile.TemporaryFile(mode="w+")
    env = {**os.environ, "HF_HUB_DISABLE_PROGRESS_BARS": "1"}
    env.pop("HF_HUB_OFFLINE", None)
    proc = subprocess.Popen([sys.executable, "-m", "camr_engine.app.fetch", repo], stdout=subprocess.DEVNULL, stderr=err,
                            env=env)
    proc.errfile = err
    return proc


class Downloads:
    """Downloads in flight, one child process each, watched from the bytes landing in the cache."""

    def __init__(self, spawn: Callable = _spawn, root: Path | None = None, every_s: float = 0.5):
        self.spawn, self.root, self.every = spawn, root, every_s
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()

    def start(self, repo: str, total: int | None) -> dict:
        if not repo_ok(repo):
            raise ValueError("only mlx-community repositories are downloaded")
        with self.lock:
            job = self.jobs.get(repo)
            if job is not None and job.state == "downloading":
                return job.to_dict()
            job = Job(repo, total, bytes=landed(repo, self.root))
            job.proc = self.spawn(repo)
            self.jobs[repo] = job
        threading.Thread(target=self._watch, args=(job,), daemon=True).start()
        return job.to_dict()

    def pause(self, repo: str) -> dict:
        with self.lock:
            job = self.jobs.get(repo)
            if job is None:
                raise KeyError(repo)
            if job.state == "downloading":
                job.state = "paused"
                job.proc.terminate()
            return job.to_dict()

    def state(self) -> list[dict]:
        with self.lock:
            return [j.to_dict() for j in self.jobs.values()]

    def _watch(self, job: Job) -> None:
        while job.proc.poll() is None:
            self._sample(job)
            time.sleep(self.every)
        self._sample(job)
        err = ""
        f = getattr(job.proc, "errfile", None)
        try:
            if f is not None:
                f.seek(0)
                err = f.read()
                f.close()
        except (OSError, ValueError):
            pass
        with self.lock:
            if job.state == "paused":
                job.rate = None
            elif job.proc.returncode == 0:
                job.state, job.rate = "done", None
                if job.total:
                    job.bytes = max(job.bytes, job.total)
            else:
                job.state, job.rate = "failed", None
                lines = [ln for ln in err.strip().splitlines() if ln.strip()]
                job.error = (lines[-1] if lines else f"exited with {job.proc.returncode}")[:240]

    def _sample(self, job: Job) -> None:
        now, got = time.monotonic(), landed(job.repo, self.root)
        job.samples = [s for s in job.samples if now - s[0] <= 3.0] + [(now, got)]
        t0, b0 = job.samples[0]
        job.bytes = got
        job.rate = (got - b0) / (now - t0) if now - t0 > 0.2 else job.rate
