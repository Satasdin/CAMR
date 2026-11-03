"""How fast each local model reads and writes on this Mac, by how much it is given to read.

For every model and context size, one prompt of that many tokens is read (prefill) and 128 tokens are written
(decode). MLX models report their own reading and writing speeds and peak memory; Ollama models report theirs in the
reply (prompt_eval and eval counts and durations). The prompt is the same plain text for every model, cut to size
with each model's own tokenizer. One measuring job at a time: nothing else should use the GPU while this runs.

    python -m engram.bench.throughput --out records/bench
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

from engram.ruler.harness import environment

MLX_MODELS = {
    "qwen3-1.7b": "mlx-community/Qwen3-1.7B-4bit",
    "qwen3-4b": "mlx-community/Qwen3-4B-Instruct-2507-4bit",
    "qwen3-8b": "mlx-community/Qwen3-8B-4bit",
    "qwen-27b": "mlx-community/Qwen3.8-27B-4bit",
}
OLLAMA_MODELS = {"qwen3-1.7b": "qwen3:1.7b", "qwen3-4b": "qwen3:4b", "qwen3-8b": "qwen3:8b"}
SIZES = (512, 2048, 8192, 32768)
WRITE = 128


def plain_text() -> str:
    """Long, varied plain text: every day of the three scripted lives, in order."""
    from engram.ruler.life import build

    parts = []
    for persona in ("student", "farmer", "developer"):
        for seed in (0, 1):
            life = build(persona, seed)
            parts += [t for d in life.days for t in d.dated()]
    return "\n".join(parts)


def mlx_point(model, tokenizer, ids: list[int]) -> dict:
    from mlx_lm import stream_generate

    last = None
    t = time.perf_counter()
    first = None
    for r in stream_generate(model, tokenizer, ids, max_tokens=WRITE):
        if first is None:
            first = time.perf_counter() - t
        last = r
    return {"tokens": len(ids), "first_word_s": round(first, 3), "read_tok_s": round(last.prompt_tps, 1),
            "write_tok_s": round(last.generation_tps, 1), "written": last.generation_tokens,
            "peak_gb": round(last.peak_memory, 2)}


def ollama_point(name: str, text: str, size: int) -> dict:
    body = json.dumps({"model": name, "prompt": text, "raw": True, "stream": False, "keep_alive": "5m",
                       "options": {"num_ctx": size + WRITE + 64, "num_predict": WRITE, "temperature": 0}}).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", body, {"Content-Type": "application/json"})
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=900) as r:
        reply = json.loads(r.read())
    wall = time.perf_counter() - t
    read_s = reply["prompt_eval_duration"] / 1e9
    return {"tokens": reply.get("prompt_eval_count"), "first_word_s": round(read_s + reply.get("load_duration", 0) / 1e9, 3),
            "read_tok_s": round(reply["prompt_eval_count"] / read_s, 1) if read_s else None,
            "write_tok_s": round(reply["eval_count"] / (reply["eval_duration"] / 1e9), 1),
            "written": reply["eval_count"], "wall_s": round(wall, 2)}


def run(out: Path, sizes=SIZES, progress=print) -> Path:
    import mlx.core as mx
    from mlx_lm import load

    text = plain_text()
    results = {"kind": "throughput", "write_tokens": WRITE, "environment": environment(), "mlx": {}, "ollama": {}}
    for key, repo in MLX_MODELS.items():
        model, tokenizer = load(repo)
        ids = tokenizer.encode(text)
        while len(ids) < max(sizes):
            ids = ids + ids
        stream_warm = mlx_point(model, tokenizer, ids[:256])  # warm the kernels
        points = []
        for size in sizes:
            mx.reset_peak_memory()
            try:
                p = mlx_point(model, tokenizer, ids[:size])
            except RuntimeError as e:  # a size that does not fit this Mac's GPU memory is a result, not a crash
                points.append({"tokens": size, "error": "out of GPU memory" if "Memory" in str(e) else str(e)[:200]})
                progress(f"mlx {key:11s} {size:6d} tokens: does not fit ({points[-1]['error']})")
                mx.clear_cache()
                break
            points.append(p)
            progress(f"mlx {key:11s} {size:6d} tokens: first word {p['first_word_s']} s, read {p['read_tok_s']} tok/s, "
                     f"write {p['write_tok_s']} tok/s, peak {p['peak_gb']} GB")
        results["mlx"][key] = {"repo": repo, "warm": stream_warm, "points": points}
        del model
        mx.clear_cache()
    for key, name in OLLAMA_MODELS.items():
        from mlx_lm import load as load_tok  # reuse the MLX tokenizer of the same model to cut the prompt to size

        _, tokenizer = load_tok(MLX_MODELS[key], lazy=True)
        ids = tokenizer.encode(text)
        while len(ids) < max(sizes):
            ids = ids + ids
        ollama_point(name, tokenizer.decode(ids[:256]), 256)  # load the model
        points = []
        for size in sizes:
            p = ollama_point(name, tokenizer.decode(ids[:size]), size)
            points.append(p)
            progress(f"ollama {key:8s} {size:6d} tokens: read {p['read_tok_s']} tok/s, write {p['write_tok_s']} tok/s")
        results["ollama"][key] = {"name": name, "points": points}
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"throughput-{time.strftime('%Y-%m-%d-%H%M')}.json"
    path.write_text(json.dumps(results, indent=1))
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("records/bench"))
    print(run(ap.parse_args().out))
