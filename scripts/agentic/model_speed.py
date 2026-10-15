"""Speed and memory of each local model as the engine's reader, measured on a quiet machine.

The same 30 prompts for every model (the verified pipeline's reading prompt, built from held-out questions and the
notes memory gave them): time to first token is not separated (Ollama returns whole answers), so seconds per answer,
prompt-reading and generation rates come from Ollama's own timings; resident memory is the model process's RSS after
the run (other models unloaded first).

    python scripts/agentic/model_speed.py --models qwen2.5:0.5b,qwen2.5:1.5b,llama3.2:3b,phi4-mini,qwen2.5:7b
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
HOST = "http://127.0.0.1:11434"


def model_rss_mb() -> float:
    import subprocess

    out = subprocess.run(["ps", "-eo", "rss,cmd"], capture_output=True, text=True).stdout
    return sum(int(line.split()[0]) for line in out.splitlines()[1:] if "llama-server" in line or "ollama runner"
               in line) / 1024


def prompts(n: int) -> list[str]:
    d = json.loads((ROOT / "results/verified/answers_heldout_sa.json").read_text())
    rows = next(iter(d["variants"].values()))["per_question"]
    qs = {it["i"]: it["question"] for it in json.loads((ROOT / "results/verified/heldout.json").read_text())}
    out = []
    for r in rows:
        ev = r.get("evidence") or ""
        out.append("Use the notes below to answer. Answer the question with a short phrase copied from the notes. "
                   f"Do not explain.\n\nNotes:\n- {ev}\n\nQuestion: {qs.get(r['i'], '')}\nAnswer:")
        if len(out) >= n:
            break
    return out


def main(a) -> None:
    ps = prompts(a.n)
    out = {"n": len(ps), "models": {}}
    for model in a.models.split(","):
        for m in requests.get(f"{HOST}/api/ps", timeout=10).json().get("models", []):
            requests.post(f"{HOST}/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=60)
        time.sleep(3)
        t0 = time.perf_counter()
        requests.post(f"{HOST}/api/generate", json={"model": model, "prompt": "Hi", "stream": False,
                                                    "options": {"num_predict": 1}}, timeout=900)
        load_s = time.perf_counter() - t0
        secs, pe, ev = [], [], []
        for p in ps:
            t = time.perf_counter()
            b = requests.post(f"{HOST}/api/generate", json={"model": model, "prompt": p, "stream": False,
                                                            "options": {"temperature": 0, "num_predict": 32,
                                                                        "num_ctx": 4096}}, timeout=900).json()
            secs.append(time.perf_counter() - t)
            if b.get("prompt_eval_duration"):
                pe.append(b["prompt_eval_count"] / (b["prompt_eval_duration"] / 1e9))
            if b.get("eval_duration") and b.get("eval_count"):
                ev.append(b["eval_count"] / (b["eval_duration"] / 1e9))
        out["models"][model] = {"load_s": round(load_s, 2), "s_per_answer_median": round(statistics.median(secs), 3),
                                "s_per_answer_mean": round(statistics.mean(secs), 3),
                                "prompt_tokens_per_s": round(statistics.median(pe), 1) if pe else None,
                                "gen_tokens_per_s": round(statistics.median(ev), 1) if ev else None,
                                "rss_mb": round(model_rss_mb(), 1)}
        print(model, out["models"][model], flush=True)
    path = ROOT / "results/models/speed.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="qwen2.5:0.5b,qwen2.5:1.5b,llama3.2:3b,phi4-mini,qwen2.5:7b")
    ap.add_argument("--n", type=int, default=30)
    main(ap.parse_args())
