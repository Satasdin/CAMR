"""Prompt processing (PP) and token generation (TG) speeds, the way llama-bench reports them, on this Mac.

    .venv/bin/python scripts/pp_tg.py --out ../work/speed/pp_tg.json

Three parts, each a table of medians over ``--reps`` runs that start at different places in a Long Haul's words (so no
run reads what an earlier one read):

- mlx: each MLX reader (camr_engine.bench.local.MODELS) reads ``depth`` tokens (PP: tokens a second) and then writes
  ``--tg`` tokens after them (TG, at that depth). The end of a turn is barred while writing, so every run writes all
  ``--tg`` tokens.
- ollama: the same models through Ollama (llama.cpp), raw text, its own prompt_eval and eval counters. Ollama may stop
  at the end of a turn, so its written count is kept beside the speed.
- notes: the 4B answers a short question after ``depth`` tokens of history, read either as words (the text is read
  with the question) or as saved notes (the same text's notes read off the SSD past the file cache, unpacked and laid
  as the model's cache, then the question read): the time to the first word each way, and the bytes read.

The load average is kept with each part: a busy Mac reads slower, and the record says so.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import statistics as st
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from camr_engine.bench.local import MODELS  # noqa: E402

OLLAMA = {"qwen3-1.7b": "qwen3:1.7b", "qwen3-4b": "qwen3:4b-instruct-2507-q4_K_M", "qwen3-8b": "qwen3:8b"}
F_NOCACHE = 48
QUESTION = "\n\nQuestion: In one short sentence, what was the last thing the user asked for above?"


def load() -> float:
    return float(subprocess.run(["sysctl", "-n", "vm.loadavg"], capture_output=True, text=True).stdout.split()[1])


def history_text(haul: Path, chars: int) -> str:
    out, n = [], 0
    with open(haul / "script.jsonl") as f:
        for line in f:
            e = json.loads(line)
            t = e["text"] if e["role"] == "system" else f"{e['role'].capitalize()}: {e['text']}"
            out.append(t)
            n += len(t) + 1
            if n >= chars:
                break
    return "\n".join(out)


def window(ids: list[int], depth: int, rep: int) -> list[int]:
    start = rep * 7919 % max(1, len(ids) - depth)
    return ids[start:start + depth]


def med(xs):
    return round(st.median(xs), 1) if xs else None


def mlx_part(models, depths, tg, reps, text) -> list[dict]:
    import mlx.core as mx
    from mlx_lm import load as mlx_load, stream_generate

    rows = []
    for name in models:
        model, tok = mlx_load(MODELS[name])
        ids = tok.encode(text)
        eos = set(tok.eos_token_ids) if getattr(tok, "eos_token_ids", None) else {tok.eos_token_id}

        def no_end(_tokens, logits):
            for e in eos:
                logits[:, e] = -float("inf")
            return logits

        list(stream_generate(model, tok, ids[:64], max_tokens=4))  # warm
        for depth in depths:
            pp, tgs, n_out, ld = [], [], [], load()
            for r in range(reps):
                w = window(ids, depth, r)
                last = None
                for last in stream_generate(model, tok, w, max_tokens=tg, logits_processors=[no_end]):
                    pass
                pp.append(last.prompt_tps)
                tgs.append(last.generation_tps)
                n_out.append(last.generation_tokens)
                mx.clear_cache()
            row = {"engine": "mlx", "model": name, "depth": depth, "pp_tps": med(pp), "tg_tps": med(tgs),
                   "tg_tokens": min(n_out), "load": ld, "peak_gb": round(mx.get_peak_memory() / 1e9, 2)}
            mx.reset_peak_memory()
            print(json.dumps(row), flush=True)
            rows.append(row)
        del model
        mx.clear_cache()
    return rows


def ollama_call(body: dict) -> dict:
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read())


def ollama_part(models, depths, tg, reps, text) -> list[dict]:
    from transformers import AutoTokenizer

    rows = []
    for name in models:
        tag = OLLAMA[name]
        tok = AutoTokenizer.from_pretrained(MODELS[name])  # the same Qwen3 words Ollama's GGUF reads
        ids = tok.encode(text)
        for depth in depths:
            opts = {"num_ctx": depth + tg + 512, "num_predict": tg, "temperature": 0, "seed": 0}
            ollama_call({"model": tag, "prompt": "Hello", "raw": True, "stream": False, "options": opts})  # load
            pp, tgs, n_out, ld = [], [], [], load()
            for r in range(reps):
                out = ollama_call({"model": tag, "prompt": tok.decode(window(ids, depth, r)), "raw": True,
                                   "stream": False, "options": opts})
                pp.append(out["prompt_eval_count"] / (out["prompt_eval_duration"] / 1e9))
                tgs.append(out["eval_count"] / (out["eval_duration"] / 1e9))
                n_out.append(out["eval_count"])
            row = {"engine": "ollama", "model": name, "tag": tag, "depth": depth, "prompt_tokens": out["prompt_eval_count"],
                   "pp_tps": med(pp), "tg_tps": med(tgs), "tg_tokens": min(n_out), "load": ld}
            print(json.dumps(row), flush=True)
            rows.append(row)
        ollama_call({"model": tag, "prompt": "", "keep_alive": 0, "stream": False})
    return rows


def read_uncached(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY)
    try:
        fcntl.fcntl(fd, F_NOCACHE, 1)
        size = os.fstat(fd).st_size
        buf = bytearray(size)
        view, o = memoryview(buf), 0
        while o < size:
            o += os.readv(fd, [view[o:o + (1 << 20)]])
        return bytes(buf)
    finally:
        os.close(fd)


def notes_part(name, depths, reps, text, scratch: Path) -> list[dict]:
    import mlx.core as mx
    from mlx_lm import load as mlx_load, stream_generate
    from mlx_lm.models.cache import KVCache, make_prompt_cache

    from camr_engine.notes import Shape, pack, unpack

    model, tok = mlx_load(MODELS[name])
    a = model.args
    shape = Shape(len(model.layers), a.num_key_value_heads, a.head_dim, float(a.rope_theta))
    ids = tok.encode(text)
    q = tok.encode(QUESTION)
    list(stream_generate(model, tok, ids[:64], max_tokens=2))  # warm
    scratch.mkdir(parents=True, exist_ok=True)
    rows = []
    for depth in depths:
        words, kept = {16: [], 8: []}, {16: [], 8: []}
        as_text = []
        sizes = {}
        for r in range(reps):
            w = window(ids, depth, r)
            t0 = time.perf_counter()
            first = next(iter(stream_generate(model, tok, w + q, max_tokens=1)))
            as_text.append(time.perf_counter() - t0)
            # the same history's notes, written once (untimed), as the memory keeps them
            cache = make_prompt_cache(model)
            for i in range(0, len(w), 2048):
                model(mx.array(w[i:i + 2048])[None], cache=cache)
                mx.eval([c.state for c in cache])
            notes = mx.stack([mx.stack([c.keys[0, :, :depth, :], c.values[0, :, :depth, :]]) for c in cache])
            notes = notes.transpose(3, 0, 1, 2, 4)
            dtype = notes.dtype
            for bits in (16, 8):
                f = scratch / f"notes-{depth}-{bits}.bin"
                f.write_bytes(pack(notes, bits))
                sizes[bits] = f.stat().st_size
            del cache, notes
            mx.clear_cache()
            for bits in (16, 8):
                t0 = time.perf_counter()
                buf = read_uncached(scratch / f"notes-{depth}-{bits}.bin")
                t_read = time.perf_counter() - t0
                x = unpack(buf, shape, dtype, bits).transpose(1, 2, 3, 0, 4)
                laid = []
                for layer in range(shape.layers):
                    c = KVCache()
                    c.state = (x[layer, 0][None], x[layer, 1][None], depth)
                    laid.append(c)
                mx.eval([c.keys for c in laid] + [c.values for c in laid])
                next(iter(stream_generate(model, tok, q, max_tokens=1, prompt_cache=laid)))
                kept[bits].append(time.perf_counter() - t0)
                words[bits].append(t_read)
                del laid, x, buf
                mx.clear_cache()
            for bits in (16, 8):
                (scratch / f"notes-{depth}-{bits}.bin").unlink()
        row = {"engine": "mlx", "model": name, "depth": depth, "load": load(),
               "first_word_text_s": round(st.median(as_text), 3),
               "first_word_notes16_s": round(st.median(kept[16]), 3),
               "first_word_notes8_s": round(st.median(kept[8]), 3),
               "ssd_read16_s": round(st.median(words[16]), 3), "ssd_read8_s": round(st.median(words[8]), 3),
               "notes16_mb": round(sizes[16] / 1e6, 1), "notes8_mb": round(sizes[8] / 1e6, 1),
               "text_kb": round(len(tok.decode(window(ids, depth, 0)).encode()) / 1e3, 1)}
        row["speedup16"] = round(row["first_word_text_s"] / row["first_word_notes16_s"], 2)
        row["speedup8"] = round(row["first_word_text_s"] / row["first_word_notes8_s"], 2)
        print(json.dumps(row), flush=True)
        rows.append(row)
    del model
    mx.clear_cache()
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--haul", type=Path, default=Path("../work/haul/s2"))
    ap.add_argument("--models", nargs="+", default=["qwen3-1.7b", "qwen3-4b", "qwen3-8b"])
    ap.add_argument("--depths", nargs="+", type=int, default=[512, 1024, 2048, 4096, 8192, 16384, 32768])
    ap.add_argument("--notes-depths", nargs="+", type=int, default=[512, 1024, 2048, 4096, 8192, 16384])
    ap.add_argument("--tg", type=int, default=128)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--parts", nargs="+", default=["mlx", "notes", "ollama"])
    ap.add_argument("--scratch", type=Path, default=Path("../work/speed/scratch.nosync"))
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    text = history_text(a.haul, chars=4 * (max(a.depths) + 4 * 7919) * 2)
    from camr_engine.bench.contender import environment

    out = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "environment": environment(), "tg": a.tg, "reps": a.reps,
           "haul": str(a.haul)}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    for part in a.parts:
        if part == "mlx":
            out["mlx"] = mlx_part(a.models, a.depths, a.tg, a.reps, text)
        elif part == "notes":
            out["notes"] = notes_part("qwen3-4b", a.notes_depths, a.reps, text, a.scratch)
        elif part == "ollama":
            out["ollama"] = ollama_part(a.models, a.depths, a.tg, a.reps, text)
        a.out.write_text(json.dumps(out, indent=1))
    out["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    a.out.write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
