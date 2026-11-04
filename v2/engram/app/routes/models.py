"""The Models screen's routes: what this Mac is, which models fit it, and getting one onto it.

- ``GET /api/models?context=8192``: this Mac (chip, RAM, GPU, disk, the last SSD probe), RAM and disk in use, and
  every model on it (MLX in the Hugging Face cache, and Ollama's), each with its anatomy, its RAM at the context, its
  speed here (measured, or est. from the measured ones) and its verdict;
- ``GET /api/models/search?q=&sort=downloads``: mlx-community models on Hugging Face (the public API, no token);
- ``GET /api/models/info?repos=a,b``: the same rows as ``/api/models`` for models not on this Mac yet (config and
  file sizes fetched from Hugging Face);
- ``GET /api/models/jobs``: downloads and the loader, for polling while something moves;
- ``POST /api/models/download``, ``/pause``, ``/load``, ``/unload`` with ``{"repo": ...}``;
- ``POST /api/models/probe``: a quick burst read of this SSD.

Nothing loads, downloads or probes while a benchmark measures.
"""

from __future__ import annotations

import time
from pathlib import Path

from engram.app import fit, hub
from engram.app.web import Refused, Request, Routes, part

CONTEXT = 8192


def _records() -> Path:
    from engram.ruler.harness import RECORDS

    return RECORDS / "bench"


def _roles() -> dict[str, str]:
    from engram.models import EMBEDDER, READER, READER_27B, READER_BIG

    return {READER: "memory reader", READER_BIG: "reader", READER_27B: "reader", EMBEDDER: "embedder"}


def _kept(app, name: str, ttl: float, make):
    box = part(app, name, lambda: {"at": -1e9, "value": None})
    if time.monotonic() - box["at"] > ttl:
        box["value"], box["at"] = make(), time.monotonic()
    return box["value"]


def _local(app) -> list[dict]:
    return _kept(app, "_models_local", 5.0, lambda: [m for m in hub.local() if hub.repo_ok(m["repo"])])


def _speeds(app, local: list[dict]) -> fit.Speeds:
    def make() -> fit.Speeds:
        weights = {m["repo"]: (m["weights_bytes"], fit.anatomy(m["config"], m["repo"])) for m in local
                   if m["config"] and m["weights_bytes"]}
        return fit.Speeds.load(_records(), weights)

    return _kept(app, "_models_speeds", 60.0, make)


def _runtime(app):
    from engram.app.runtime import Runtime

    return part(app, "models", Runtime)


def _downloads(app) -> hub.Downloads:
    return part(app, "_downloads", hub.Downloads)


def _loaded(app, local: list[dict]) -> tuple[set[str], int]:
    """Repositories loaded in this server (the memory's reader and embedder, and the model picked here), and the
    weights of the picked one, which loading another would replace."""
    from engram.models import EMBEDDER

    s = _runtime(app).state()
    loaded = {slot["repo"] for slot in (s["memory"], s["picked"]) if slot and slot.get("repo")}
    if getattr(app, "embedder", None) is not None:
        loaded.add(EMBEDDER)
    picked = s["picked"]["repo"] if s["picked"] else None
    replace = next((m["weights_bytes"] for m in local if m["repo"] == picked), 0)
    return loaded, replace


def _mac(app, local: list[dict]) -> tuple[dict, dict, fit.Mac]:
    """This Mac's limits for a model about to load: everything in RAM now stays, except the picked model it would
    replace."""
    from engram import hardware

    hw = hardware.detect()
    now = hardware.memory_now()
    _, replace = _loaded(app, local)
    other = max(0, now["used_bytes"] - replace) if now["used_bytes"] is not None else None
    return hw, now, fit.Mac(hw["ram_bytes"], hw["gpu_limit_bytes"], other)


def _measured_line(m: fit.Measured | None) -> dict | None:
    if m is None or not m.decode_tps():
        return None
    return {"record": m.record, "first_word_s": m.first_word_s(fit.DESK_TOKENS), "decode_tps": m.decode_tps(),
            "desk_tokens": fit.DESK_TOKENS, "failed_at": m.failed_at}


def row(repo: str, config: dict, weights: int, *, context: int, mac: fit.Mac, speeds: fit.Speeds, extra: dict,
        measured: fit.Measured | None = None, words: bool = False) -> dict:
    """One model's row: what it is, what it needs here, and how it runs here."""
    a = fit.anatomy(config, repo)
    out = {"id": repo, "repo": repo, "name": repo.split("/")[-1], "params": a.params, "active_params": a.active,
           "quant": a.quant, "anatomy": a.to_dict(), "memory_as": "words" if words else a.memory_as,
           "weights_bytes": weights, "measured": _measured_line(measured)}
    out["fit"] = fit.judge(a, weights, context, mac, speeds, measured=measured, engram=not words)
    out.update(extra)
    return out


def _board(app, context: int) -> dict:
    local = _local(app)
    speeds = _speeds(app, local)
    hw, now, mac = _mac(app, local)
    runtime = _runtime(app).state()
    loaded, _ = _loaded(app, local)
    loading = runtime["job"]["repo"] if runtime["job"] and runtime["job"]["state"] == "loading" else None
    roles = _roles()
    mlx = []
    for m in local:
        if not m["config"]:
            continue
        mlx.append(row(m["repo"], m["config"], m["weights_bytes"], context=context, mac=mac, speeds=speeds,
                       measured=speeds.mlx.get(m["repo"]),
                       extra={"source": "mlx", "local": True, "complete": m["complete"], "disk_bytes": m["disk_bytes"],
                              "download_bytes": None, "role": roles.get(m["repo"]), "loaded": m["repo"] in loaded,
                              "loading": m["repo"] == loading}))
    olla = hub.ollama()
    ollama_rows = []
    for m in olla["models"]:
        cfg = hub.ollama_config(m)
        level = (m.get("details") or {}).get("quantization_level")
        r = row(f"ollama:{m['name']}", cfg, int(m.get("size") or 0), context=context, mac=mac, speeds=speeds,
                measured=speeds.ollama.get(m["name"]), words=True,
                extra={"name": m["name"], "source": "ollama", "local": True, "complete": True,
                       "disk_bytes": m.get("size"), "role": None, "loaded": False, "loading": False,
                       "details": m.get("details")})
        if level:
            r["quant"] = {**r["quant"], "label": f"gguf {level}"}
        ollama_rows.append(r)
    memory = getattr(app, "memory", None)
    rooms = vault = None
    try:
        rooms = memory.rooms.disk_bytes() if memory is not None else None
        vault = memory.vault.disk_bytes() if memory is not None and memory.vault is not None else None
    except Exception:  # noqa: BLE001 (a stand-in app)
        pass
    tiers = getattr(memory, "tiers", None)
    weights = sum(m["weights_bytes"] for m in local if m["repo"] in loaded)
    return {"hardware": hw, "now": now, "context": context, "contexts": list(fit.CONTEXTS),
            "limits": {"slow_decode_tps": fit.SLOW_DECODE_TPS, "slow_first_word_s": fit.SLOW_FIRST_WORD_S,
                       "desk_tokens": fit.DESK_TOKENS, "tight_bytes": fit.TIGHT_BYTES},
            "engram_ram_budget": fit.ENGRAM_RAM,
            "ram": {"other_bytes": mac.other_bytes, "weights_bytes": weights if weights else None,
                    "engram_bytes": tiers.ram_bytes() if tiers is not None else None,
                    "process_bytes": now["process_bytes"]},
            "disk_use": {"models_bytes": sum(m["disk_bytes"] for m in hub.local()), "rooms_bytes": rooms,
                         "vault_bytes": vault},
            "speeds": {"records": speeds.records, "bandwidth_bps": speeds.bandwidth, "compute": speeds.compute},
            "mlx": mlx, "ollama": {"running": olla["running"], "models": ollama_rows},
            "runtime": runtime, "downloads": _downloads(app).state()}


def _context(req: Request) -> int:
    return req.int("context", CONTEXT, lo=256, hi=1 << 20)


def _repo(req: Request) -> str:
    repo = req.str("repo", limit=200)
    if not hub.repo_ok(repo):
        raise Refused(400, "repo must be an mlx-community/<name> repository")
    return repo


def _not_measuring() -> None:
    from engram.app.measuring import active

    job = active()
    if job:
        raise Refused(409, f"a benchmark is measuring ({job['job']}); try again when it is done")


def register(routes: Routes) -> None:
    @routes.get("/api/models")
    def models(req: Request) -> dict:
        return _board(req.app, _context(req))

    @routes.get("/api/models/search")
    def search(req: Request) -> dict:
        try:
            found = hub.search(req.str("q", limit=80), sort=req.str("sort", "downloads", limit=20),
                               limit=req.int("limit", 30, lo=1, hi=60))
        except OSError as e:
            raise Refused(502, f"Hugging Face did not answer: {e}") from None
        here = {m["repo"] for m in _local(req.app)}
        return {"results": [{**r, "local": r["repo"] in here} for r in found]}

    @routes.get("/api/models/info")
    def info(req: Request) -> dict:
        repos = [r for r in req.str("repos", limit=4000).split(",") if r][:24]
        if not all(hub.repo_ok(r) for r in repos):
            raise Refused(400, "repos must be mlx-community/<name> repositories")
        context = _context(req)
        local = _local(req.app)
        speeds = _speeds(req.app, local)
        _, _, mac = _mac(req.app, local)
        roles = _roles()
        out = {}
        for repo, got in hub.infos(repos).items():
            if "error" in got:
                out[repo] = {"id": repo, "repo": repo, "error": got["error"]}
                continue
            out[repo] = row(repo, got["config"], got["weights_bytes"], context=context, mac=mac, speeds=speeds,
                            measured=speeds.mlx.get(repo),
                            extra={"source": "hub", "local": False, "complete": False, "disk_bytes": hub.landed(repo),
                                   "download_bytes": got["download_bytes"], "role": roles.get(repo),
                                   "loaded": False, "loading": False})
        return {"rows": out}

    @routes.get("/api/models/jobs")
    def jobs(req: Request) -> dict:
        return {"downloads": _downloads(req.app).state(), "runtime": _runtime(req.app).state()}

    @routes.post("/api/models/download")
    def download(req: Request) -> dict:
        repo = _repo(req)
        _not_measuring()
        try:
            total = hub.info(repo)["download_bytes"]
        except Exception:  # noqa: BLE001 (the bar then shows bytes without a total)
            total = None
        return _downloads(req.app).start(repo, total)

    @routes.post("/api/models/pause")
    def pause(req: Request) -> dict:
        try:
            return _downloads(req.app).pause(_repo(req))
        except KeyError:
            raise Refused(404, "no download of that model") from None

    @routes.post("/api/models/load")
    def load(req: Request) -> dict:
        repo = _repo(req)
        _not_measuring()
        here = next((m for m in hub.local() if m["repo"] == repo), None)
        if here is None or not here["complete"]:
            raise Refused(409, "download it first: its files are not all on this Mac")
        if not req.bool("force"):
            local = _local(req.app)
            _, _, mac = _mac(req.app, local)
            r = row(repo, here["config"], here["weights_bytes"], context=_context(req), mac=mac,
                    speeds=_speeds(req.app, local), measured=_speeds(req.app, local).mlx.get(repo), extra={})
            if r["fit"]["verdict"] == "wont_run":
                raise Refused(409, "it needs more RAM than the GPU may use on this Mac")
        try:
            return _runtime(req.app).load(repo)
        except RuntimeError as e:
            raise Refused(409, str(e)) from None

    @routes.post("/api/models/unload")
    def unload(req: Request) -> dict:
        try:
            return _runtime(req.app).unload(_repo(req))
        except RuntimeError as e:
            raise Refused(409, str(e)) from None
        except KeyError:
            raise Refused(404, "that model is not loaded") from None

    @routes.post("/api/models/probe")
    def probe(req: Request) -> dict:
        from engram import hardware

        _not_measuring()
        folder = None
        paths = req.app.paths() if hasattr(req.app, "paths") else {}
        if paths.get("memory") is not None:
            folder = Path(paths["memory"])
        return hardware.probe(folder if folder is not None and folder.is_dir() else None)
