"""External weights beside a frozen model: a token-level memory (kNN-LM) for Qwen2.5-0.5B.

The closest working form of "the frozen 0.5B model uses external weights as memory and its
own parameters as compute" is the k-nearest-neighbour language model (Khandelwal et al., 2020).
The model reads every stored document once; for each position it stores a key, the model's own
final hidden state h(x_≤t), and a value, the token that came next. At answer time each step's
hidden state looks up its k nearest keys, and their next tokens form a second distribution
that is mixed with the model's:

    p(y | x) = λ · p_kNN(y | x) + (1 − λ) · p_LM(y | x),
    p_kNN(y | x) ∝ Σ_{(k_i, v_i) ∈ N_k(h(x))} 1[v_i = y] · exp(cos(h(x), k_i) / τ)

The model's weights never change; the datastore grows with what it reads. This script builds
the datastore from the same 237 PopQA documents the LoRA study trained on and CAMR stores,
chooses the document format, λ and τ on the same 60 validation questions, and tests once on
the same 60 held-out questions, in the same runtime (transformers, float32, CPU, greedy), so
it sits directly beside LoRA (weights inside) and CAMR (memory in the prompt).

    python scripts/token_memory.py tune
    python scripts/token_memory.py test
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import finetune_baseline as fb  # noqa: E402  (same data, model and scoring as the LoRA study)

from camr.eval.scoring import score  # noqa: E402

OUT = fb.ROOT / "results" / "token_memory"
K = 64
GRID = {"fmt": ("raw", "chat"), "lam": (0.25, 0.5, 0.75), "tau": (0.02, 0.05)}


@torch.no_grad()
def build_datastore(tok, model, fmt: str) -> dict:
    """Keys: unit-length final hidden states at every trained position; values: the next token."""
    keys, vals = [], []
    t0 = time.perf_counter()
    for d in fb.documents():
        ids, labels = fb.encode_doc(tok, d, fmt, max_len=256)
        x = torch.tensor([ids])
        h = model(x, output_hidden_states=True).hidden_states[-1][0]  # T x H (after the final norm)
        for t in range(len(ids) - 1):
            if labels[t + 1] != -100:  # position t predicts token t+1
                keys.append(h[t])
                vals.append(ids[t + 1])
    k = torch.nn.functional.normalize(torch.stack(keys), dim=-1)
    return {"keys": k.half(), "vals": torch.tensor(vals), "build_s": time.perf_counter() - t0,
            "entries": len(vals), "mb": k.numel() * 2 / 1e6 + len(vals) * 8 / 1e6}


@torch.no_grad()
def knn_generate(tok, model, store: dict | None, prompt: str, lam: float, tau: float, max_new: int = 32) -> str:
    """Greedy decoding from λ·p_kNN + (1−λ)·p_LM (store None: the model alone)."""
    text = tok.apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True, tokenize=False)
    ids = tok(text, return_tensors="pt", add_special_tokens=False)["input_ids"]
    keys = store["keys"].float() if store else None
    out, past, step_in = [], None, ids
    for _ in range(max_new):
        o = model(step_in, past_key_values=past, use_cache=True, output_hidden_states=True)
        past = o.past_key_values
        p = torch.softmax(o.logits[0, -1].float(), dim=-1)
        if store is not None and lam > 0:
            h = torch.nn.functional.normalize(o.hidden_states[-1][0, -1], dim=-1)
            sims = keys @ h
            top = torch.topk(sims, min(K, len(sims)))
            w = torch.softmax(top.values / tau, dim=-1)
            p_knn = torch.zeros_like(p).scatter_add_(0, store["vals"][top.indices], w)
            p = lam * p_knn + (1 - lam) * p
        nxt = int(torch.argmax(p))
        if nxt == tok.eos_token_id or nxt in (tok.convert_tokens_to_ids("<|im_end|>"),):
            break
        out.append(nxt)
        step_in = torch.tensor([[nxt]])
    return tok.decode(out, skip_special_tokens=True)


def accuracy(tok, model, store, rows, key, lam, tau) -> dict:
    rows = [r for r in rows if r.get(key)]
    t0 = time.perf_counter()
    answers = [knn_generate(tok, model, store, r[key], lam, tau) for r in rows]
    per = [score(r["task"], a, r["answers"])["contains"] for r, a in zip(rows, answers)]
    return {"n": len(rows), "accuracy": sum(per) / len(per), "seconds": round(time.perf_counter() - t0, 1),
            "per_question": [{"qid": r["qid"], "correct": c, "answer": a.strip()[:200]} for r, c, a in
                             zip(rows, per, answers)]}


def tune(a) -> None:
    tok, model = fb.load()
    sets = fb.split_sets()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "tune.json"
    res = json.loads(path.read_text()) if path.exists() else {"grid": [], "datastores": {}}
    done = {(g["fmt"], g["lam"], g["tau"]) for g in res["grid"]}
    for fmt in GRID["fmt"]:
        store = build_datastore(tok, model, fmt)
        res["datastores"][fmt] = {k: store[k] for k in ("entries", "mb", "build_s")}
        torch.save(store, OUT / f"datastore_{fmt}.pt")
        for lam in GRID["lam"]:
            for tau in GRID["tau"]:
                if (fmt, lam, tau) in done:
                    continue
                r = accuracy(tok, model, store, sets["val"], "closed", lam, tau)
                res["grid"].append({"fmt": fmt, "lam": lam, "tau": tau, "val_accuracy": r["accuracy"],
                                    "seconds": r["seconds"]})
                path.write_text(json.dumps(res, indent=1))
                print(fmt, lam, tau, round(r["accuracy"], 3), r["seconds"], "s", flush=True)
    res["peak_rss_mb"] = round(fb.peak_rss_mb())
    path.write_text(json.dumps(res, indent=1))


def test(a) -> None:
    tune_res = json.loads((OUT / "tune.json").read_text())
    best = max(tune_res["grid"], key=lambda g: (g["val_accuracy"], -g["lam"]))
    tok, model = fb.load()
    sets = fb.split_sets()
    store = torch.load(OUT / f"datastore_{best['fmt']}.pt")
    out = {"selected": best, "datastore": tune_res["datastores"][best["fmt"]], "conditions": {}}
    out["conditions"]["base"] = accuracy(tok, model, None, sets["test"], "closed", 0.0, 1.0)
    out["conditions"]["knn_lm"] = accuracy(tok, model, store, sets["test"], "closed", best["lam"], best["tau"])
    out["conditions"]["camr"] = accuracy(tok, model, None, sets["test"], "camr", 0.0, 1.0)
    out["conditions"]["knn_lm+camr"] = accuracy(tok, model, store, sets["test"], "camr", best["lam"], best["tau"])
    out["peak_rss_mb"] = round(fb.peak_rss_mb())
    (OUT / "test.json").write_text(json.dumps(out, indent=1))
    for k, v in out["conditions"].items():
        print(k, round(v["accuracy"], 3), v["seconds"], "s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["tune", "test"])
    a = ap.parse_args()
    {"tune": tune, "test": test}[a.part](a)
