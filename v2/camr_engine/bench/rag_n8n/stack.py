"""The n8n + Qdrant stack in Docker, and what it costs: bring it up, give n8n its local owner and its two workflows,
make the Qdrant collection, and measure RAM (the containers and Ollama) and disk (the volumes).

Everything the stack keeps is under work/n8n/ (gitignored): ``.env`` (the encryption key and the local-only owner
login, made once with random values), ``n8n.nosync/`` (n8n's SQLite database) and ``qdrant.nosync/`` (the vectors).
The folders end in ``.nosync`` so iCloud leaves them alone, as the engine's memories do.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from camr_engine.bench.rag_n8n import build

HERE = Path(__file__).resolve().parent
COMPOSE = HERE / "docker-compose.yml"
REPO = Path(__file__).resolve().parents[4]
WORK = REPO / "work" / "n8n"
ENV = WORK / ".env"
N8N_PORT = 5678
QDRANT_PORT = 6333
N8N = f"http://127.0.0.1:{N8N_PORT}"
QDRANT = f"http://127.0.0.1:{QDRANT_PORT}"
OLLAMA = "http://127.0.0.1:11434"
SERVICES = ("n8n", "qdrant")


class StackError(RuntimeError):
    pass


# -- HTTP ---------------------------------------------------------------------------------------------------------


def request(method: str, url: str, body: Any = None, *, timeout: float = 900.0,
            headers: dict | None = None) -> tuple[int, Any]:
    """(status, parsed JSON or text). Never raises on an HTTP error status; raises StackError when nothing answers."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={**({"Content-Type": "application/json"} if data else {}), **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw, status = resp.read(), resp.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    except (urllib.error.URLError, OSError) as e:
        raise StackError(f"{method} {url}: nothing answered ({type(e).__name__}: {e})") from e
    try:
        return status, json.loads(raw) if raw.strip() else None
    except ValueError:
        return status, raw.decode(errors="replace")


# -- the local settings -------------------------------------------------------------------------------------------


def read_env(path: Path = ENV) -> dict:
    out = {}
    if path.exists():
        for ln in path.read_text().splitlines():
            if "=" in ln and not ln.lstrip().startswith("#"):
                k, _, v = ln.partition("=")
                out[k.strip()] = v.strip()
    return out


def ensure_env(work: Path = WORK) -> dict:
    """work/n8n/.env, made once: the paths compose mounts, the ports, n8n's encryption key and a local-only owner
    login (random; it never leaves this file). Later calls keep the secrets and refresh the paths."""
    work.mkdir(parents=True, exist_ok=True)
    (work / "n8n.nosync").mkdir(exist_ok=True)
    (work / "qdrant.nosync").mkdir(exist_ok=True)
    env = read_env(work / ".env")
    env.setdefault("N8N_ENCRYPTION_KEY", secrets.token_hex(24))
    env.setdefault("CAMR_N8N_OWNER_EMAIL", "camr-bench@localhost.test")
    env.setdefault("CAMR_N8N_OWNER_PASSWORD", "Camr" + secrets.token_urlsafe(18) + "9")
    env.update(CAMR_N8N_WORK=str(work), CAMR_RAG_WORKFLOWS=str(build.WORKFLOWS), CAMR_N8N_PORT=str(N8N_PORT),
               CAMR_QDRANT_PORT=str(QDRANT_PORT))
    text = ("# local-only settings for the n8n RAG stack (camr_engine.bench.rag_n8n); never commit\n"
            + "".join(f"{k}={v}\n" for k, v in env.items()))
    path = work / ".env"
    path.write_text(text)
    os.chmod(path, 0o600)
    return env


def compose(*args: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    cmd = ["docker", "compose", "-f", str(COMPOSE), "--env-file", str(ENV), *args]
    p = subprocess.run(cmd, capture_output=capture, text=True)
    if check and p.returncode != 0:
        raise StackError(f"{' '.join(cmd[2:])} failed: {(p.stderr or p.stdout or '').strip()[-800:]}")
    return p


# -- up and down --------------------------------------------------------------------------------------------------


def _wait(url: str, what: str, timeout_s: float = 180.0) -> None:
    end = time.time() + timeout_s
    last = None
    while time.time() < end:
        try:
            status, _ = request("GET", url, timeout=5)
            if status == 200:
                return
            last = f"status {status}"
        except StackError as e:
            last = str(e)
        time.sleep(1.0)
    raise StackError(f"{what} did not come up at {url} within {timeout_s:.0f} s ({last})")


def running() -> bool:
    try:
        return (request("GET", f"{N8N}/healthz", timeout=3)[0] == 200
                and request("GET", f"{QDRANT}/readyz", timeout=3)[0] == 200)
    except StackError:
        return False


def owner(env: dict) -> str:
    """Give n8n its owner (the local-only login in .env) the first time, so the editor can be opened and nothing
    asks for it interactively. Returns what happened."""
    status, settings = request("GET", f"{N8N}/rest/settings", timeout=10)
    data = (settings or {}).get("data", settings) if isinstance(settings, dict) else {}
    um = (data or {}).get("userManagement") or {}
    if status == 200 and um.get("showSetupOnFirstLoad") is False:
        return "owner already set up"
    status, out = request("POST", f"{N8N}/rest/owner/setup", {
        "email": env["CAMR_N8N_OWNER_EMAIL"], "firstName": "CAMR", "lastName": "Bench",
        "password": env["CAMR_N8N_OWNER_PASSWORD"]}, timeout=30)
    if status != 200:
        msg = json.dumps(out)[:300] if not isinstance(out, str) else out[:300]
        if "already" in msg.lower():
            return "owner already set up"
        raise StackError(f"n8n owner setup answered {status}: {msg}")
    return "owner set up"


def workflows_hash() -> str:
    h = hashlib.sha256()
    for name in ("ingest.json", "ask.json"):
        h.update((build.WORKFLOWS / name).read_bytes())
    return h.hexdigest()[:16]


def import_workflows(work: Path = WORK) -> bool:
    """Import (or re-import, when the JSON changed) and publish both workflows with n8n's own CLI inside the
    container, then restart n8n so its production webhooks are registered. Returns whether it imported."""
    mark = work / "imported.json"
    now = workflows_hash()
    if mark.exists() and json.loads(mark.read_text()).get("hash") == now:
        return False
    # n8n keeps its workflows in SQLite: the CLI writes them while the server is stopped, never beside it
    compose("stop", "n8n")
    try:
        for name, spec in (("ingest.json", build.INGEST), ("ask.json", build.ASK)):
            compose("run", "--rm", "--no-deps", "-T", "n8n", "import:workflow", f"--input=/workflows/{name}")
            compose("run", "--rm", "--no-deps", "-T", "n8n", "publish:workflow", f"--id={spec['id']}")
    finally:
        compose("start", "n8n")
    _wait(f"{N8N}/healthz/readiness", "n8n")
    _wait(f"{N8N}/rest/settings", "n8n REST")
    mark.write_text(json.dumps({"hash": now, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}))
    return True


def webhooks_ready(timeout_s: float = 90.0) -> None:
    """Both production webhooks answer (anything but 404: an empty ask fails inside the workflow, which is fine)."""
    end = time.time() + timeout_s
    while True:
        try:
            status, out = request("POST", f"{N8N}/webhook/{build.ASK['path']}", {"probe": True}, timeout=30)
        except StackError as e:
            status, out = 0, str(e)
        if status not in (0, 404):
            return
        if time.time() > end:
            raise StackError(f"the ask webhook is not registered ({status}: {str(out)[:200]})")
        time.sleep(2.0)


def up(progress=print) -> dict:
    """Bring the stack up (if it is not already), set the owner, import and publish the workflows. Idempotent."""
    if not COMPOSE.exists():
        raise StackError(f"no compose file at {COMPOSE}")
    if not (build.WORKFLOWS / "ingest.json").exists():
        build.write()
    env = ensure_env()
    if not running():
        progress("starting n8n and Qdrant (docker compose up -d)")
    compose("up", "-d")  # also recreates a container whose settings changed; a no-op otherwise
    _wait(f"{QDRANT}/readyz", "Qdrant")
    _wait(f"{N8N}/healthz/readiness", "n8n")
    _wait(f"{N8N}/rest/settings", "n8n REST")
    said = owner(env)
    imported = import_workflows()
    webhooks_ready()
    info = {"owner": said, "imported": imported, "n8n_version": n8n_version(), "qdrant_version": qdrant_version()}
    progress(f"stack up: n8n {info['n8n_version']}, Qdrant {info['qdrant_version']} ({said}"
             f"{', workflows imported' if imported else ''})")
    return info


def down() -> None:
    compose("down")


def n8n_version() -> str | None:
    p = compose("exec", "-T", "n8n", "n8n", "--version", check=False)
    got = (p.stdout or "").strip().splitlines()
    return got[-1] if p.returncode == 0 and got else None


def qdrant_version() -> str | None:
    try:
        status, out = request("GET", f"{QDRANT}/", timeout=5)
    except StackError:
        return None
    return out.get("version") if status == 200 and isinstance(out, dict) else None


# -- Qdrant and Ollama --------------------------------------------------------------------------------------------


def embed_dim(model: str = build.EMBED_MODEL) -> int:
    status, out = request("POST", f"{OLLAMA}/api/embed", {"model": model, "input": "size", "keep_alive": build.KEEP_ALIVE})
    if status != 200 or not out.get("embeddings"):
        raise StackError(f"Ollama could not embed with {model} ({status}: {str(out)[:200]})")
    return len(out["embeddings"][0])


def collection_info(name: str) -> dict | None:
    status, out = request("GET", f"{QDRANT}/collections/{name}", timeout=30)
    return out.get("result") if status == 200 else None


def ensure_collection(name: str, dim: int) -> bool:
    """The collection, made if it is not there (cosine over ``dim``-wide vectors). Returns whether it was made."""
    if collection_info(name) is not None:
        return False
    status, out = request("PUT", f"{QDRANT}/collections/{name}", {"vectors": {"size": dim, "distance": "Cosine"}})
    if status != 200:
        raise StackError(f"Qdrant could not make {name} ({status}: {str(out)[:200]})")
    return True


def drop_collection(name: str) -> None:
    request("DELETE", f"{QDRANT}/collections/{name}", timeout=60)


def count(name: str) -> int:
    status, out = request("POST", f"{QDRANT}/collections/{name}/points/count", {"exact": True}, timeout=60)
    return int(out["result"]["count"]) if status == 200 else 0


# -- RAM and disk -------------------------------------------------------------------------------------------------

_SIZE = re.compile(r"([\d.]+)\s*([KMGT]?i?B)")
_UNITS = {"B": 1, "KB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12, "KiB": 2**10, "MiB": 2**20, "GiB": 2**30, "TiB": 2**40}


def parse_size(text: str) -> int | None:
    """Bytes in docker's sizes: "123.4MiB" -> 129394278."""
    m = _SIZE.search(text or "")
    return int(float(m.group(1)) * _UNITS[m.group(2)]) if m else None


def container_ids() -> dict[str, str]:
    out = {}
    for svc in SERVICES:
        p = compose("ps", "-q", svc, check=False)
        cid = (p.stdout or "").strip()
        if cid:
            out[svc] = cid
    return out


def container_ram() -> dict[str, int]:
    """Each container's memory use in bytes, as docker stats reports it (its cgroup, page cache left out)."""
    ids = container_ids()
    if not ids:
        return {}
    p = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{json .}}", *ids.values()],
                       capture_output=True, text=True, timeout=60)
    by_id = {v[:12]: k for k, v in ids.items()}
    out = {}
    for ln in (p.stdout or "").splitlines():
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        svc = by_id.get(str(row.get("ID", ""))[:12])
        got = parse_size(str(row.get("MemUsage", "")).split("/")[0])
        if svc and got is not None:
            out[svc] = got
    return out


_BLOBS: dict[tuple[str, ...], list[str]] = {}


def model_blobs(models: tuple[str, ...]) -> list[str]:
    """The sha256 of each model's blobs (from /api/show's modelfile), asked once per process."""
    if models not in _BLOBS:
        blobs = []
        for m in models:
            try:
                status, show = request("POST", f"{OLLAMA}/api/show", {"model": m}, timeout=10)
                blobs += re.findall(r"sha256[-:]([0-9a-f]{64})", json.dumps(show) if status == 200 else "")
            except StackError:
                pass
        if not blobs:
            return []
        _BLOBS[models] = blobs
    return _BLOBS[models]


def ollama_pids(models: tuple[str, ...] = (build.CHAT_MODEL, build.EMBED_MODEL)) -> dict[str, list[int]]:
    """Ollama's server and the runners holding our two models (found by their model blob in the runner's
    arguments); runners for other models are left out. When no blob can be matched, every runner counts."""
    p = subprocess.run(["ps", "-axo", "pid=,args="], capture_output=True, text=True)
    serve, runners = [], []
    for ln in p.stdout.splitlines():
        pid, _, args = ln.strip().partition(" ")
        exe = os.path.basename(args.split(" ")[0])
        if exe == "ollama" and " serve" in args:
            serve.append(int(pid))
        elif (exe == "ollama" and " runner" in args) or exe == "llama-server":  # Ollama 0.40 runs llama-server
            runners.append((int(pid), args))
    blobs = model_blobs(models)
    ours = [pid for pid, args in runners if any(b in args for b in blobs)]
    return {"serve": serve, "runners": ours if ours or not blobs else [], "all_runners": [p for p, _ in runners]}


def footprint(pid: int) -> int | None:
    from camr_engine.models import footprint_bytes

    return footprint_bytes(pid)


def rss(pids: list[int]) -> dict[int, int]:
    """Resident bytes of each process (ps rss), mapped model weights included."""
    if not pids:
        return {}
    p = subprocess.run(["ps", "-o", "pid=,rss=", "-p", ",".join(map(str, pids))], capture_output=True, text=True)
    out = {}
    for ln in p.stdout.splitlines():
        parts = ln.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            out[int(parts[0])] = int(parts[1]) * 1024
    return out


def ollama_ram() -> dict:
    """What Ollama holds for our two models: the resident memory (RSS: the mapped weights, the keys and values and
    Metal's buffers) of its server and of the runners holding them, which is the headline ``bytes``; their physical
    footprint (which leaves out clean mapped weight pages); and what Ollama says it holds (/api/ps)."""
    pids = ollama_pids()
    ours = pids["serve"] + pids["runners"]
    fp = {pid: footprint(pid) for pid in ours}
    res = rss(ours)
    held = {}
    try:
        status, ps = request("GET", f"{OLLAMA}/api/ps", timeout=10)
        for m in (ps or {}).get("models", []) if status == 200 else []:
            if m.get("name") in (build.CHAT_MODEL, build.EMBED_MODEL) or m.get("model") in (build.CHAT_MODEL,
                                                                                               build.EMBED_MODEL):
                held[m.get("name")] = {"size": m.get("size"), "size_vram": m.get("size_vram"),
                                       "context_length": m.get("context_length")}
    except StackError:
        pass
    return {"bytes": sum(res.values()), "rss_by_pid": res, "footprint_bytes": sum(v for v in fp.values() if v),
            "footprint_by_pid": fp, "runners": pids["runners"],
            "other_runners": [p for p in pids["all_runners"] if p not in pids["runners"]], "ollama_ps": held}


def du(path: Path) -> int:
    """Bytes on disk under ``path`` (du -sk: blocks actually used)."""
    if not Path(path).exists():
        return 0
    p = subprocess.run(["du", "-sk", str(path)], capture_output=True, text=True)
    try:
        return int(p.stdout.split()[0]) * 1024
    except (IndexError, ValueError):
        return 0


def disk(collection: str | None = None, work: Path = WORK) -> dict:
    """The volumes' size: Qdrant's whole storage, the one collection's folder, and n8n's data folder."""
    out = {"qdrant_bytes": du(work / "qdrant.nosync"), "n8n_bytes": du(work / "n8n.nosync")}
    if collection:
        out["collection_bytes"] = du(work / "qdrant.nosync" / "collections" / collection)
    out["total_bytes"] = out["qdrant_bytes"] + out["n8n_bytes"]
    return out


class RamWatch:
    """Samples the stack's RAM in a background thread (docker stats takes about two seconds a call, so it samples as
    fast as that allows): the containers plus Ollama's footprint. ``peak_since(t)`` is the most seen since ``t``."""

    def __init__(self, every_s: float = 1.0):
        self.every_s = every_s
        self.samples: list[tuple[float, int, dict]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str | None = None

    def sample(self) -> tuple[int, dict]:
        c = container_ram()
        o = ollama_ram()
        total = sum(c.values()) + o["bytes"]
        detail = {"containers": c, "ollama_rss_bytes": o["bytes"], "ollama_footprint_bytes": o["footprint_bytes"],
                  "ollama_ps": o["ollama_ps"],
                  "other_ollama_runners": o["other_runners"]}
        self.samples.append((time.perf_counter(), total, detail))
        return total, detail

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.sample()
            except Exception as e:  # noqa: BLE001: a missed sample is not worth stopping a run
                self.error = f"{type(e).__name__}: {e}"[:200]
            self._stop.wait(self.every_s)

    def start(self) -> "RamWatch":
        self._thread = threading.Thread(target=self._loop, name="ram-watch", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def latest(self) -> tuple[int, dict] | None:
        return (self.samples[-1][1], self.samples[-1][2]) if self.samples else None

    def peak_since(self, t: float) -> int | None:
        got = [b for at, b, _ in self.samples if at >= t]
        if got:
            return max(got)
        last = self.latest()
        return last[0] if last else None

    def peak(self) -> tuple[int, dict] | None:
        if not self.samples:
            return None
        _, b, d = max(self.samples, key=lambda s: s[1])
        return b, d
