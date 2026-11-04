"""The Models screen: a model's anatomy, what it needs on this Mac and how fast it runs here; Hugging Face reached
through the server only; downloads watched from the bytes landing; loading in the background; this Mac read from
the system. No model is loaded and nothing reaches the network: every outside call is a fake."""

from __future__ import annotations

import http.client
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

from camr_engine import hardware
from camr_engine.app import fit, hub
from camr_engine.app.runtime import Runtime

GIB = 1024**3

QWEN3_1_7B = {"architectures": ["Qwen3ForCausalLM"], "model_type": "qwen3", "hidden_size": 2048, "head_dim": 128,
              "intermediate_size": 6144, "max_position_embeddings": 40960, "num_attention_heads": 16,
              "num_hidden_layers": 28, "num_key_value_heads": 8, "tie_word_embeddings": True, "vocab_size": 151936,
              "quantization": {"group_size": 64, "bits": 4}}
QWEN_27B = {"architectures": ["Qwen3_5ForConditionalGeneration"], "model_type": "qwen3_5",
            "quantization": {"group_size": 64, "bits": 4, "mode": "affine"}, "tie_word_embeddings": False,
            "text_config": {"full_attention_interval": 4, "head_dim": 256, "hidden_size": 5120,
                            "intermediate_size": 17408, "linear_conv_kernel_dim": 4, "linear_key_head_dim": 128,
                            "linear_num_key_heads": 16, "linear_num_value_heads": 48, "linear_value_head_dim": 128,
                            "max_position_embeddings": 262144, "num_attention_heads": 24, "num_hidden_layers": 64,
                            "num_key_value_heads": 4, "vocab_size": 248320, "model_type": "qwen3_5_text"}}
QWEN3_30B_A3B = {"architectures": ["Qwen3MoeForCausalLM"], "model_type": "qwen3_moe", "hidden_size": 2048,
                 "head_dim": 128, "intermediate_size": 6144, "moe_intermediate_size": 768, "num_experts": 128,
                 "num_experts_per_tok": 8, "num_attention_heads": 32, "num_hidden_layers": 48,
                 "num_key_value_heads": 4, "vocab_size": 151936, "quantization": {"group_size": 64, "bits": 4}}
GEMMA_LIKE = {"architectures": ["Gemma3ForCausalLM"], "model_type": "gemma3_text", "hidden_size": 2560,
              "head_dim": 256, "intermediate_size": 10240, "num_attention_heads": 8, "num_hidden_layers": 12,
              "num_key_value_heads": 4, "sliding_window": 1024, "sliding_window_pattern": 6, "vocab_size": 262144}


# -- anatomy


def test_a_dense_model_keeps_kv_on_every_layer_and_reads_tensors():
    a = fit.anatomy(QWEN3_1_7B, "mlx-community/Qwen3-1.7B-4bit")
    assert a.layers == ["kv"] * 28 and a.memory_as == "tensors"
    assert a.kv_per_token == 114688  # the 112 KB a token the engine's notes take on the 1.7B
    assert a.state_bytes == 0 and a.quant["label"] == "4-bit g64"
    assert 1.6e9 < a.params < 2.2e9 and a.active == a.params


def test_the_27b_reads_words_because_48_of_its_64_layers_keep_no_kv():
    a = fit.anatomy(QWEN_27B, "mlx-community/Qwen3.8-27B-4bit")
    assert len(a.layers) == 64 and a.layers.count("kv") == 16 and a.layers.count("linear") == 48
    assert a.layers[:4] == ["linear", "linear", "linear", "kv"]
    assert a.memory_as == "words" and a.kv_per_token == 16 * 2 * 4 * 256 * 2
    assert a.state_bytes > 100e6  # a fixed state per linear layer, whatever the context
    assert a.vocab == 248320 and a.params == pytest.approx(27e9, rel=0.1)


def test_a_mixture_of_experts_reads_only_its_active_experts():
    a = fit.anatomy(QWEN3_30B_A3B, "mlx-community/Qwen3-30B-A3B-4bit")
    assert a.params == pytest.approx(30.5e9, rel=0.05) and 2.5e9 < a.active < 4e9
    named = fit.anatomy({**QWEN3_30B_A3B, "num_hidden_layers": 4}, "mlx-community/Qwen3-30B-A3B-4bit")
    assert named.params == 30e9 and named.active == 3e9  # shapes far from the name: the name wins


def test_sliding_window_layers_keep_kv_only_for_their_window():
    a = fit.anatomy(GEMMA_LIKE, "mlx-community/gemma-like-bf16")
    assert a.layers.count("sliding") == 10 and a.layers.count("kv") == 2 and a.layers[5] == "kv"
    assert a.memory_as == "words" and a.window == 1024 and a.quant["label"] == "bf16"
    j1 = fit.judge(a, 5 * 10**9, 2048, fit.Mac(24 * GIB, 18 * GIB), fit.Speeds())
    j2 = fit.judge(a, 5 * 10**9, 32768, fit.Mac(24 * GIB, 18 * GIB), fit.Speeds())
    assert j2["parts"]["kv"] - j1["parts"]["kv"] == a.kv_per_token * (32768 - 2048)  # sliding stays at its window


def test_hybrid_patterns_and_names():
    assert fit.layer_kinds({"num_hidden_layers": 4, "hybrid_override_pattern": "M-*M"}) == ["linear", "none", "kv",
                                                                                            "linear"]
    assert fit.layer_kinds({"num_hidden_layers": 4, "attn_layer_period": 2, "attn_layer_offset": 1}) == [
        "linear", "kv", "linear", "kv"]
    assert fit.layer_kinds({"num_hidden_layers": 2, "layer_types": ["sliding_attention", "full_attention"]}) == [
        "sliding", "kv"]
    assert fit._size_from_name("Qwen3-30B-A3B-Instruct-2507-4bit") == (30e9, 3e9)
    assert fit._size_from_name("Qwen3-0.6B-8bit") == (0.6e9, None)
    assert fit._size_from_name("SmolLM-135M-Instruct") == (135e6, None)
    assert fit.quant({"quantization": {"bits": 4, "group_size": 32, "mode": "mxfp4"}})["label"] == "4-bit mxfp4 g32"
    assert fit.quant({}, "Some-Model-8bit")["bits"] == 8


# -- what it needs here, and the verdict


def throughput(folder: Path, name: str = "throughput-2026-11-04-0123.json") -> Path:
    rec = {"kind": "throughput", "mlx": {"qwen3-1.7b": {"repo": "mlx-community/Qwen3-1.7B-4bit", "points": [
        {"tokens": 512, "first_word_s": 0.083, "read_tok_s": 6172.2, "write_tok_s": 219.6, "peak_gb": 1.71},
        {"tokens": 2048, "first_word_s": 0.298, "read_tok_s": 6878.5, "write_tok_s": 187.2, "peak_gb": 1.91},
        {"tokens": 8192, "first_word_s": 1.428, "read_tok_s": 5736.8, "write_tok_s": 126.6, "peak_gb": 2.77}]},
        "qwen-27b": {"repo": "mlx-community/Qwen3.8-27B-4bit", "points": [
            {"tokens": 512, "first_word_s": 1.424, "read_tok_s": 359.7, "write_tok_s": 17.6, "peak_gb": 16.4},
            {"tokens": 2048, "first_word_s": 5.374, "read_tok_s": 381.1, "write_tok_s": 17.6, "peak_gb": 18.13},
            {"tokens": 8192, "first_word_s": 21.997, "read_tok_s": 372.4, "write_tok_s": 16.7, "peak_gb": 18.53},
            {"tokens": 32768, "error": "out of GPU memory"}]}},
        "ollama": {"qwen3-1.7b": {"name": "qwen3:1.7b", "points": [
            {"tokens": 512, "first_word_s": 0.749, "read_tok_s": 1655.6, "write_tok_s": 137.5}]}}}
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(rec))
    return folder


def speeds(tmp_path) -> fit.Speeds:
    weights = {"mlx-community/Qwen3-1.7B-4bit": (968080210, fit.anatomy(QWEN3_1_7B, "Qwen3-1.7B")),
               "mlx-community/Qwen3.8-27B-4bit": (16054541349, fit.anatomy(QWEN_27B, "Qwen3.8-27B"))}
    return fit.Speeds.load(throughput(tmp_path / "records"), weights)


def test_measured_runs_give_peak_ram_and_speed_and_fit_the_estimates(tmp_path):
    s = speeds(tmp_path)
    assert s.records == ["records/throughput-2026-11-04-0123.json"]
    m = s.mlx["mlx-community/Qwen3-1.7B-4bit"]
    assert m.peak_bytes(512, 114688) == int(1.71e9) and m.peak_bytes(5120, 114688) == int(1.91e9 + 0.86e9 / 2)
    assert m.peak_bytes(16384, 114688) == int(2.77e9 + 8192 * 114688)  # past the last: plus the extra tokens' KV
    assert m.first_word_s(1024) == pytest.approx((0.083 * 0.298) ** 0.5, rel=1e-6)
    assert m.decode_tps() == 219.6
    big = s.mlx["mlx-community/Qwen3.8-27B-4bit"]
    assert big.failed_at == 32768 and big.peak_bytes(32768, 65536) is None
    assert 200e9 < s.bandwidth < 300e9 and s.compute > 1e12  # bytes of weights read per second, params x tok/s
    assert s.ollama["qwen3:1.7b"].decode_tps() == 137.5


def test_the_verdict_follows_the_gpu_limit_and_the_speed_measured_here(tmp_path):
    s = speeds(tmp_path)
    mac = fit.Mac(24 * GIB, 19069665280, 6 * GIB)
    small = fit.judge(fit.anatomy(QWEN3_1_7B, "Qwen3-1.7B"), 968080210, 8192, mac, s,
                      measured=s.mlx["mlx-community/Qwen3-1.7B-4bit"])
    assert small["verdict"] == "fits" and small["source"] == "measured" and small["speed_source"] == "measured"
    assert small["need_bytes"] == int(2.77e9) + fit.CAMR_RAM  # measured peak plus the camr's RAM budget
    assert small["spare_bytes"] > 10 * GIB and not small["tight"]
    a27 = fit.anatomy(QWEN_27B, "Qwen3.8-27B")
    big = fit.judge(a27, 16054541349, 8192, mac, s, measured=s.mlx["mlx-community/Qwen3.8-27B-4bit"])
    assert big["verdict"] == "fits" and big["tight"] and big["parts"]["camr"] == 0  # it reads words
    huge = fit.judge(a27, 16054541349, 32768, mac, s, measured=s.mlx["mlx-community/Qwen3.8-27B-4bit"])
    assert huge["verdict"] == "wont_run" and huge["source"] == "measured"  # it ran out of GPU memory here
    est = fit.judge(a27, 16054541349, 8192, mac, s)
    assert est["source"] == "est." and abs(est["need_bytes"] - 18.53e9) < 1.5e9  # the estimate is near the run
    slow = fit.judge(fit.anatomy(QWEN3_1_7B, "Qwen3-70B"), 40 * 10**9, 2048, fit.Mac(128 * GIB, 96 * GIB), s)
    assert slow["verdict"] == "slow" and slow["decode_tps"] < fit.SLOW_DECODE_TPS
    blind = fit.judge(fit.anatomy(QWEN3_1_7B), 10**9, 2048, fit.Mac(None, None), fit.Speeds())
    assert blind["verdict"] == "unknown" and blind["decode_tps"] is None  # nothing measured, nothing claimed


# -- Hugging Face, through the server only


def fake_get(responses: dict):
    calls = []

    def get(url, timeout=10.0):
        calls.append(url)
        for key, value in responses.items():
            if key in url:
                return value
        raise OSError(f"no fake for {url}")

    get.calls = calls
    return get


def test_search_asks_mlx_community_and_keeps_only_chat_models(monkeypatch):
    hub._cache.clear()
    rows = [{"id": "mlx-community/Qwen3-8B-4bit", "pipeline_tag": "text-generation", "library_name": "mlx",
             "downloads": 10, "config": {"architectures": ["Qwen3ForCausalLM"], "model_type": "qwen3",
                                         "quantization_config": {"bits": 4}}, "safetensors": {"total": 8e9}},
            {"id": "mlx-community/Qwen3-ASR-0.6B-8bit", "pipeline_tag": "automatic-speech-recognition",
             "library_name": "mlx-audio", "config": {"architectures": ["Qwen3ASRForConditionalGeneration"]}},
            {"id": "mlx-community/mel-roformer", "pipeline_tag": None, "library_name": "mlx", "config": {}},
            {"id": "mlx-community/whisper", "pipeline_tag": None, "library_name": "mlx", "tags": ["audio"],
             "config": {"architectures": ["WhisperForConditionalGeneration"]}}]
    get = fake_get({"/api/models?": rows})
    found = hub.search("qwen3 8b", get=get)
    assert [r["repo"] for r in found] == ["mlx-community/Qwen3-8B-4bit"] and found[0]["bits"] == 4
    url = get.calls[0]
    assert url.startswith("https://huggingface.co/api/models?") and "author=mlx-community" in url
    assert "search=qwen3+8b" in url and "token" not in url.lower()
    hub.search("qwen3 8b", get=get)
    assert len(get.calls) == 1  # kept for a while


def test_info_counts_only_the_files_a_download_fetches():
    hub._cache.clear()
    tree = [{"type": "file", "path": "config.json", "size": 900},
            {"type": "file", "path": "model.safetensors", "size": 5, "lfs": {"size": 4_000_000_000}},
            {"type": "file", "path": "README.md", "size": 1000}, {"type": "file", "path": "assets/pic.png", "size": 9},
            {"type": "file", "path": "tokenizer.json", "size": 11_000_000}, {"type": "directory", "path": "assets"}]
    get = fake_get({"/tree/main": tree, "/resolve/main/config.json": QWEN3_1_7B})
    got = hub.info("mlx-community/Qwen3-8B-4bit", get=get)
    assert got["weights_bytes"] == 4_000_000_000 and got["download_bytes"] == 4_011_000_900
    assert {f["path"] for f in got["files"]} == {"config.json", "model.safetensors", "tokenizer.json"}
    assert hub.infos(["mlx-community/broken"], get=fake_get({}))["mlx-community/broken"]["error"].startswith("OSError")
    with pytest.raises(ValueError):
        hub.info("../../etc", get=get)


def test_only_plain_mlx_community_repository_ids_pass():
    assert hub.repo_ok("mlx-community/Qwen3-8B-4bit")
    for bad in ["someone/Qwen3-8B", "mlx-community/../x", "mlx-community/a/b", "/etc/passwd", "mlx-community/",
                "mlx-community/.hidden", "mlx-community/a b", 7, "mlx-community/" + "a" * 120]:
        assert not hub.repo_ok(bad), bad


def fake_cache(root: Path, repo: str, shards: list[str], missing: tuple[str, ...] = (), size: int = 1000) -> Path:
    folder = root / ("models--" + repo.replace("/", "--"))
    blobs, snap = folder / "blobs", folder / "snapshots" / "abc123"
    blobs.mkdir(parents=True)
    snap.mkdir(parents=True)
    (snap / "config.json").write_text(json.dumps(QWEN3_1_7B))
    if len(shards) > 1:
        (snap / "model.safetensors.index.json").write_text(json.dumps({"weight_map": {f"w{i}": s for i, s in
                                                                                      enumerate(shards)}}))
    for name in shards:
        if name in missing:
            continue
        blob = blobs / f"blob-{name}"
        blob.write_bytes(b"\0" * size)
        os.symlink(blob, snap / name)
    return folder


def test_the_cache_says_which_models_are_whole_and_counts_bytes_still_landing(tmp_path):
    fake_cache(tmp_path, "mlx-community/Whole-4bit", ["model.safetensors"])
    fake_cache(tmp_path, "mlx-community/Half-4bit", ["model-1.safetensors", "model-2.safetensors"],
               missing=("model-2.safetensors",))
    shared = tmp_path / "blobs" / "ab"
    shared.mkdir(parents=True)
    (shared / "deadbeef").write_bytes(b"\0" * 5000)  # huggingface_hub 2.x links finished blobs to a shared store
    half = tmp_path / "models--mlx-community--Half-4bit" / "blobs"
    os.symlink(shared / "deadbeef", half / "linked")
    (half / "etag.1234.incomplete").write_bytes(b"\0" * 300)
    got = {m["repo"]: m for m in hub.local(tmp_path)}
    assert got["mlx-community/Whole-4bit"]["complete"] and got["mlx-community/Whole-4bit"]["weights_bytes"] == 1000
    assert not got["mlx-community/Half-4bit"]["complete"]
    assert hub.landed("mlx-community/Half-4bit", tmp_path) == 1000 + 5000 + 300
    assert hub.landed("mlx-community/Nothing", tmp_path) == 0


class FakeProc:
    """A download that lands ``chunks`` of bytes, one per poll, then exits with ``code``."""

    def __init__(self, blobs: Path, chunks: int, code: int = 0, error: str = ""):
        import tempfile

        self.blobs, self.left, self.code, self.returncode = blobs, chunks, code, None
        self.errfile = tempfile.TemporaryFile(mode="w+")
        self.errfile.write(error)
        self.terminated = False

    def poll(self):
        if self.terminated:
            self.returncode = -15
        elif self.left > 0:
            self.blobs.mkdir(parents=True, exist_ok=True)
            (self.blobs / f"part{self.left}.incomplete").write_bytes(b"\0" * 100)
            self.left -= 1
        else:
            self.returncode = self.code
        return self.returncode

    def terminate(self):
        self.terminated = True


def wait_for(fn, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if fn():
            return True
        time.sleep(0.01)
    return False


def test_a_download_reports_bytes_landing_and_ends_done_paused_or_failed(tmp_path):
    blobs = lambda repo: tmp_path / ("models--" + repo.replace("/", "--")) / "blobs"  # noqa: E731
    procs = {}

    def spawn(repo):
        if repo.endswith("Bad"):
            procs[repo] = FakeProc(blobs(repo), 1, code=1, error="noise\nHTTPError: 404 not found\n")
        else:
            procs[repo] = FakeProc(blobs(repo), 5 if repo.endswith("Slow") else 3)
        return procs[repo]

    d = hub.Downloads(spawn=spawn, root=tmp_path, every_s=0.01)
    first = d.start("mlx-community/Good", 300)
    assert first["state"] == "downloading" and first["total"] == 300
    assert d.start("mlx-community/Good", 300)["state"] == "downloading"  # asked twice: one download
    assert wait_for(lambda: d.state()[0]["state"] == "done")
    assert d.state()[0]["bytes"] == 300
    d.start("mlx-community/Bad", 999)
    assert wait_for(lambda: next(j for j in d.state() if j["repo"].endswith("Bad"))["state"] == "failed")
    assert next(j for j in d.state() if j["repo"].endswith("Bad"))["error"] == "HTTPError: 404 not found"
    procs.clear()
    d.every = 5.0  # slow the watcher so the pause lands while it runs
    d.start("mlx-community/Slow", 500)
    assert d.pause("mlx-community/Slow")["state"] == "paused" and procs["mlx-community/Slow"].terminated
    with pytest.raises(KeyError):
        d.pause("mlx-community/Never")
    with pytest.raises(ValueError):
        d.start("someone/else", 1)


# -- loading


def test_a_model_loads_in_the_background_and_unloads():
    gate = threading.Event()

    def loader(repo):
        gate.wait(5)
        if repo.endswith("broken"):
            raise RuntimeError("bad weights")
        return type("FakeReader", (), {"repo": repo})()

    rt = Runtime(loader=loader)
    rt.adopt(type("Mem", (), {"repo": "mlx-community/Qwen3-1.7B-4bit"})())
    assert rt.reader().repo == "mlx-community/Qwen3-1.7B-4bit"
    s = rt.load("mlx-community/Qwen3-8B-4bit")
    assert s["job"]["state"] == "loading" and s["picked"] is None
    with pytest.raises(RuntimeError, match="already loading"):
        rt.load("mlx-community/other")
    gate.set()
    assert wait_for(lambda: rt.state()["picked"] is not None)
    assert rt.reader().repo == "mlx-community/Qwen3-8B-4bit" and rt.state()["job"] is None
    assert rt.state()["picked"]["load_s"] >= 0 and "model" not in rt.state()["picked"]
    with pytest.raises(RuntimeError, match="memory"):
        rt.unload("mlx-community/Qwen3-1.7B-4bit")  # the memory's reader stays
    with pytest.raises(RuntimeError, match="already"):
        rt.load("mlx-community/Qwen3-1.7B-4bit")
    assert rt.unload("mlx-community/Qwen3-8B-4bit")["picked"] is None
    assert rt.reader().repo == "mlx-community/Qwen3-1.7B-4bit"
    with pytest.raises(KeyError):
        rt.unload("mlx-community/Qwen3-8B-4bit")
    rt.load("mlx-community/broken")
    assert wait_for(lambda: rt.state()["job"]["state"] == "failed")
    assert "bad weights" in rt.state()["job"]["error"] and rt.state()["picked"] is None


# -- this Mac


def test_this_mac_is_read_from_the_system(tmp_path):
    now = hardware.memory_now()
    assert set(now) >= {"total_bytes", "used_bytes", "free_bytes", "process_bytes", "pressure"}
    assert hardware.sysctl("no.such.value") is None
    if sys.platform == "darwin":
        d = hardware.detect()
        assert d["chip"] and d["ram_bytes"] > 0 and d["disk"]["free_bytes"] > 0
        assert now["process_bytes"] > 0 and now["pressure"] in ("normal", "tight", "critical")
    p = hardware.probe(tmp_path, size=3 * 2**20 + 5)
    assert p["bytes"] == 3 * 2**20 + 5 and p["seconds"] > 0 and p["gbps"] > 0
    assert list(tmp_path.iterdir()) == []  # the probe's file is gone
    assert hardware.detect()["probe"] == p


# -- the routes, end to end, with fakes


class StandIn:
    def state(self):
        return {"moments": 0}


@pytest.fixture
def models_server(tmp_path, monkeypatch):
    from camr_engine.app import measuring
    from camr_engine.app.routes import models as routes
    from camr_engine.app.server import make_server

    monkeypatch.setenv("CAMR_MEASURING", str(tmp_path / "measuring.json"))
    cache = tmp_path / "hf"
    fake_cache(cache, "mlx-community/Qwen3-1.7B-4bit", ["model.safetensors"], size=968080210 // 1000)
    fake_cache(cache, "mlx-community/Half-4bit", ["a.safetensors", "b.safetensors"], missing=("b.safetensors",))
    monkeypatch.setattr(hub, "cache_dir", lambda: cache)
    monkeypatch.setattr(hub, "_get", fake_get({}))  # the network is never reached
    monkeypatch.setattr(hub, "ollama", lambda get=None: {"running": False, "models": []})
    monkeypatch.setattr(hub, "search", lambda q="", **kw: [
        {"repo": "mlx-community/Qwen3-8B-4bit", "bits": 4, "params": 8e9, "downloads": 5},
        {"repo": "mlx-community/Qwen3-1.7B-4bit", "bits": 4, "params": 1.7e9, "downloads": 9}])
    monkeypatch.setattr(hub, "info", lambda repo, **kw: {"repo": repo, "config": QWEN3_1_7B, "files": [],
                                                          "weights_bytes": 4_600_000_000,
                                                          "download_bytes": 4_620_000_000})
    monkeypatch.setattr(hub, "infos", lambda repos, **kw: {r: hub.info(r) for r in repos})
    monkeypatch.setattr(routes, "_records", lambda: throughput(tmp_path / "records"))
    monkeypatch.setattr(hardware, "detect", lambda **kw: {"chip": "Apple M5 Pro", "ram_bytes": 24 * GIB,
                                                          "gpu_limit_bytes": 19069665280, "gpu_cores": 16,
                                                          "disk": {"total_bytes": 10**12, "free_bytes": 6 * 10**11},
                                                          "probe": None})
    monkeypatch.setattr(hardware, "memory_now", lambda: {"total_bytes": 24 * GIB, "used_bytes": 8 * GIB,
                                                         "free_bytes": 16 * GIB, "process_bytes": GIB,
                                                         "pressure": "normal", "pressure_level": 1})
    monkeypatch.setattr(hardware, "probe", lambda folder=None, size=0, **kw: {"bytes": 1, "seconds": 1.0,
                                                                               "gbps": 1e-9})
    app = StandIn()
    loaded = []
    app.models = Runtime(loader=lambda repo: loaded.append(repo) or type("R", (), {"repo": repo})())
    spawned = []
    app._downloads = hub.Downloads(spawn=lambda repo: spawned.append(repo) or FakeProc(cache / "x", 2),
                                   root=cache, every_s=0.01)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    httpd, token = make_server(app, port)
    threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.05), daemon=True).start()

    def call(path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        headers = {"Host": f"127.0.0.1:{port}", "X-CAMR-Token": token}
        if body is not None:
            headers["Content-Type"] = "application/json"
        c.request("POST" if body is not None else "GET", path, body=None if body is None else json.dumps(body),
                  headers=headers)
        r = c.getresponse()
        return r.status, json.loads(r.read())

    yield call, app, loaded, spawned, measuring
    httpd.shutdown()


def test_the_board_lists_this_macs_models_with_their_fit(models_server):
    call, app, *_ = models_server
    status, board = call("/api/models?context=8192")
    assert status == 200 and board["context"] == 8192 and board["hardware"]["chip"] == "Apple M5 Pro"
    rows = {r["repo"]: r for r in board["mlx"]}
    small = rows["mlx-community/Qwen3-1.7B-4bit"]
    assert small["complete"] and small["role"] == "memory reader" and small["memory_as"] == "tensors"
    assert small["fit"]["source"] == "measured" and small["fit"]["verdict"] == "fits"
    assert small["measured"]["decode_tps"] == 219.6 and small["anatomy"]["kv_layers"] == 28
    assert not rows["mlx-community/Half-4bit"]["complete"]
    assert board["ollama"] == {"running": False, "models": []}
    assert board["speeds"]["records"] == ["records/throughput-2026-11-04-0123.json"]
    assert call("/api/models?context=2048")[1]["mlx"][0]["fit"]["context"] == 2048


def test_search_and_info_go_through_the_server(models_server):
    call, *_ = models_server
    status, got = call("/api/models/search?q=qwen3")
    assert status == 200 and [r["local"] for r in got["results"]] == [False, True]
    status, got = call("/api/models/info?repos=mlx-community/Qwen3-8B-4bit&context=8192")
    row = got["rows"]["mlx-community/Qwen3-8B-4bit"]
    assert status == 200 and row["download_bytes"] == 4_620_000_000 and row["fit"]["source"] == "est."
    assert call("/api/models/info?repos=someone/else")[0] == 400


def test_downloads_and_loads_are_guarded(models_server):
    call, app, loaded, spawned, measuring = models_server
    assert call("/api/models/download", {"repo": "someone/else"})[0] == 400
    status, job = call("/api/models/download", {"repo": "mlx-community/Qwen3-8B-4bit"})
    assert status == 200 and job["total"] == 4_620_000_000 and spawned == ["mlx-community/Qwen3-8B-4bit"]
    assert call("/api/models/load", {"repo": "mlx-community/Half-4bit"})[0] == 409  # not all on this Mac
    assert call("/api/models/load", {"repo": "mlx-community/Qwen3-8B-4bit"})[0] == 409
    with measuring.measuring("longhaul"):
        assert call("/api/models/load", {"repo": "mlx-community/Qwen3-1.7B-4bit"})[0] == 409
        assert call("/api/models/download", {"repo": "mlx-community/Qwen3-8B-4bit"})[0] == 409
        assert call("/api/models/probe", {})[0] == 409
    status, s = call("/api/models/load", {"repo": "mlx-community/Qwen3-1.7B-4bit"})
    assert status == 200 and (s["job"] or s["picked"])["repo"] == "mlx-community/Qwen3-1.7B-4bit"
    assert wait_for(lambda: call("/api/models/jobs")[1]["runtime"]["picked"] is not None)
    assert loaded == ["mlx-community/Qwen3-1.7B-4bit"]
    assert call("/api/state")[1]["model"]["repo"] == "mlx-community/Qwen3-1.7B-4bit"
    status, s = call("/api/models/unload", {"repo": "mlx-community/Qwen3-1.7B-4bit"})
    assert status == 200 and s["picked"] is None
    assert call("/api/models/unload", {"repo": "mlx-community/Qwen3-1.7B-4bit"})[0] == 404
    assert call("/api/models/pause", {"repo": "mlx-community/Never"})[0] == 404
    assert call("/api/models/probe", {})[1]["bytes"] == 1
