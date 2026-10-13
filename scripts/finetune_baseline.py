"""Fine-tuning baseline: teach the small model the same documents with LoRA, and compare with CAMR.

CAMR never changes the model's weights. This script measures the alternative the
problem statement (section 1.2) argues against, on the same facts:

* LoRA fine-tuning of Qwen2.5-0.5B-Instruct on the PopQA documents the engine stores
  (unsupervised knowledge injection, as in Ovadia et al., 2023), tuned on a validation
  split and tested once on held-out questions;
* the same base model with CAMR's notes (the exact prompts logged by the benchmark runs);
* both together; and the cost of each: training time, memory, artefact size, and
  forgetting (GSM8K accuracy before and after fine-tuning).

All four conditions run in one runtime (Hugging Face transformers, float32, CPU, greedy
decoding), so differences come from the weights and the prompt, not from the runtime.

    python scripts/finetune_baseline.py tune   # grid on the validation split, adapters saved
    python scripts/finetune_baseline.py test   # best adapter: held-out test + forgetting
"""

from __future__ import annotations

import argparse
import json
import math
import random
import resource
import sqlite3
import time
from pathlib import Path

import torch
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

from camr.eval.scoring import score
from camr.harness.benchmarks import load_questions

ROOT = Path(__file__).resolve().parents[1]
BASE = "Qwen/Qwen2.5-0.5B-Instruct"
OUT = ROOT / "results" / "finetune"
SEED = 13
torch.set_num_threads(4)


# ------------------------------------------------------------------ data
def logged_prompts(db: Path, label: str, bench: str, condition: str | None = None) -> dict[str, str]:
    """question_id -> the exact prompt the benchmark run sent to the small model."""
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    q = "SELECT MAX(run_id) FROM run WHERE label=? AND benchmark=? AND status='completed'"
    args = [label, bench]
    if condition:
        q += " AND condition=?"
        args.append(condition)
    rid = c.execute(q, args).fetchone()[0]
    return {qid: p for qid, p in c.execute("SELECT question_id, prompt FROM query_log WHERE run_id=?", (rid,))}


def golds(bench: str, sample_file: Path) -> dict[str, tuple[str, list[str]]]:
    s = json.loads(sample_file.read_text())
    ids = set(s["question_ids"])
    # a training-split sample is drawn from the same file as the evaluation sample beside it
    source = s.get("source") or json.loads((sample_file.parent / f"{bench}.json").read_text())["source"]
    return {q.qid: (q.task_type, q.answers) for q in load_questions(bench, source) if q.qid in ids}


def split_sets() -> dict[str, list[dict]]:
    """validation: learn-train PopQA (60). test: pilot PopQA (30) + learn-eval PopQA (30).
    forgetting: every logged GSM8K question of the pilot and learn splits (closed-book)."""
    pilot, learn = ROOT / "results/pilot", ROOT / "results/learn"
    sets: dict[str, list[dict]] = {"val": [], "test": [], "gsm8k": []}

    def add(name, db, sample, closed_label, mem_label, bench="popqa", closed_cond=None, mem_cond=None):
        g = golds(bench, sample)
        closed = logged_prompts(db, closed_label, bench, closed_cond)
        mem = logged_prompts(db, mem_label, bench, mem_cond) if mem_label else {}
        for qid, (task, answers) in g.items():
            if qid in closed:
                sets[name].append({"qid": f"{sample.parent.parent.name}/{qid}", "task": task, "answers": answers,
                                   "closed": closed[qid], "camr": mem.get(qid)})

    add("val", learn / "camr.sqlite", learn / "samples/popqa.train.json", "arm:local:train", "arm:mem512:train")
    add("test", pilot / "camr.sqlite", pilot / "samples/popqa.json", "main", "main", closed_cond="floor",
        mem_cond="treatment")
    add("test", learn / "camr.sqlite", learn / "samples/popqa.json", "arm:local", "arm:mem512")
    add("gsm8k", pilot / "camr.sqlite", pilot / "samples/gsm8k.json", "main", None, "gsm8k", closed_cond="floor")
    add("gsm8k", learn / "camr.sqlite", learn / "samples/gsm8k.json", "arm:local", None, "gsm8k")
    add("gsm8k", learn / "camr.sqlite", learn / "samples/gsm8k.train.json", "arm:local:train", None, "gsm8k")
    return sets


def documents() -> list[dict]:
    """Every PopQA document CAMR stores for these questions (the user's 'notes')."""
    seen, docs = set(), []
    for f in ("corpus_pilot.jsonl", "corpus_learn.jsonl"):
        for line in (ROOT / "data/popqa" / f).read_text().splitlines():
            d = json.loads(line)
            if d["doc_id"] not in seen:
                seen.add(d["doc_id"])
                docs.append(d)
    return docs


# ------------------------------------------------------------------ model
def load(adapter: Path | None = None):
    tok = AutoTokenizer.from_pretrained(BASE)
    model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.float32)
    if adapter:
        model = PeftModel.from_pretrained(model, str(adapter))
        model = model.merge_and_unload()
    model.eval()
    return tok, model


def encode_doc(tok, d: dict, fmt: str, max_len: int = 192) -> tuple[list[int], list[int]]:
    """Token ids and labels (-100 = not trained on) for one document."""
    if fmt == "raw":
        ids = tok(f"{d['title']}: {d['text']}", add_special_tokens=False)["input_ids"][: max_len - 1] + [tok.eos_token_id]
        return ids, list(ids)
    # chat: the document is the assistant's answer to "what do you know about <title>?"
    user = [{"role": "user", "content": f"What do you know about {d['title']}?"}]
    prompt = tok.apply_chat_template(user, add_generation_prompt=True, tokenize=False)
    full = tok.apply_chat_template(user + [{"role": "assistant", "content": d["text"]}], tokenize=False)
    p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    ids = tok(full, add_special_tokens=False)["input_ids"][:max_len]
    labels = [-100] * min(len(p_ids), len(ids)) + ids[len(p_ids):]
    return ids, labels[: len(ids)]


def batches(examples, size, rng):
    order = list(range(len(examples)))
    rng.shuffle(order)
    for i in range(0, len(order), size):
        chunk = [examples[j] for j in order[i:i + size]]
        n = max(len(e[0]) for e in chunk)
        ids = torch.full((len(chunk), n), 0, dtype=torch.long)
        lab = torch.full((len(chunk), n), -100, dtype=torch.long)
        att = torch.zeros((len(chunk), n), dtype=torch.long)
        for k, (x, y) in enumerate(chunk):
            ids[k, :len(x)], lab[k, :len(y)], att[k, :len(x)] = torch.tensor(x), torch.tensor(y), 1
        yield ids, att, lab


@torch.no_grad()
def generate(tok, model, prompts: list[str], max_new: int, bs: int = 4) -> list[str]:
    tok.padding_side = "left"
    outs = []
    for i in range(0, len(prompts), bs):
        texts = [tok.apply_chat_template([{"role": "user", "content": p}], add_generation_prompt=True, tokenize=False)
                 for p in prompts[i:i + bs]]
        enc = tok(texts, return_tensors="pt", padding=True, add_special_tokens=False)
        gen = model.generate(**enc, max_new_tokens=max_new, do_sample=False, pad_token_id=tok.eos_token_id)
        outs += tok.batch_decode(gen[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)
    return outs


def accuracy(tok, model, rows: list[dict], key: str, max_new: int) -> dict:
    rows = [r for r in rows if r.get(key)]
    t0 = time.perf_counter()
    answers = generate(tok, model, [r[key] for r in rows], max_new)
    metric = "accuracy" if rows and rows[0]["task"] == "reasoning" else "contains"
    per = [score(r["task"], a, r["answers"])[metric] for r, a in zip(rows, answers)]
    return {"n": len(rows), "metric": metric, "accuracy": sum(per) / len(per), "seconds": time.perf_counter() - t0,
            "per_question": [{"qid": r["qid"], "correct": c, "answer": a.strip()[:300]}
                             for r, c, a in zip(rows, per, answers)]}


def peak_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


# ------------------------------------------------------------------ stages
def tune(a) -> None:
    sets, docs = split_sets(), documents()
    out = OUT / "tune"
    out.mkdir(parents=True, exist_ok=True)
    log = json.loads((out / "grid.json").read_text()) if (out / "grid.json").exists() else []
    done = {(r["fmt"], r["lr"]) for r in log}
    for fmt in a.formats.split(","):
        for lr in map(float, a.lrs.split(",")):
            if (fmt, lr) in done:
                continue
            torch.manual_seed(SEED)
            rng = random.Random(SEED)
            tok, base = load()
            tok.padding_side = "right"
            model = get_peft_model(base, LoraConfig(r=a.rank, lora_alpha=2 * a.rank, lora_dropout=0.05,
                                                    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                                                    "gate_proj", "up_proj", "down_proj"],
                                                    task_type="CAUSAL_LM"))
            model.gradient_checkpointing_enable()
            model.enable_input_require_grads()
            trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
            examples = [encode_doc(tok, d, fmt) for d in docs]
            opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=0.0)
            steps_per_epoch = math.ceil(len(examples) / (a.batch * a.accum))
            warm = max(1, steps_per_epoch // 2)
            run = {"fmt": fmt, "lr": lr, "rank": a.rank, "batch": a.batch * a.accum, "docs": len(docs),
                   "train_tokens": sum(sum(1 for y in e[1] if y != -100) for e in examples),
                   "trainable_params": trainable, "epochs": []}
            step, t_train = 0, 0.0
            for epoch in range(1, a.epochs + 1):
                model.train()
                t0, losses = time.perf_counter(), []
                micro = list(batches(examples, a.batch, rng))
                for i in range(0, len(micro), a.accum):  # gradient accumulation: effective batch = batch x accum
                    for g in opt.param_groups:
                        g["lr"] = lr * min(1.0, (step + 1) / warm)  # warm-up, then constant
                    group = micro[i:i + a.accum]
                    total = 0.0
                    for ids, att, lab in group:
                        loss = model(input_ids=ids, attention_mask=att, labels=lab).loss / len(group)
                        loss.backward()
                        total += loss.item()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    opt.step()
                    opt.zero_grad()
                    losses.append(total)
                    step += 1
                    if step % 10 == 0:
                        print(f"  step {step} loss {losses[-1]:.3f} {time.perf_counter() - t0:.0f}s", flush=True)
                t_train += time.perf_counter() - t0
                rec = {"epoch": epoch, "train_loss": sum(losses) / len(losses), "train_seconds": round(t_train, 1)}
                if epoch in a.eval_at:
                    model.eval()
                    ev = accuracy(tok, model, sets["val"], "closed", 40)
                    rec.update({"val_closed": ev["accuracy"], "eval_seconds": round(ev["seconds"], 1)})
                    path = out / f"adapter-{fmt}-lr{lr:g}-ep{epoch}"
                    model.save_pretrained(str(path))
                    rec["adapter_mb"] = round(sum(f.stat().st_size for f in path.iterdir()) / 1e6, 1)
                run["epochs"].append(rec)
                print(fmt, lr, rec, flush=True)
            run["peak_rss_mb"] = round(peak_rss_mb())
            log.append(run)
            (out / "grid.json").write_text(json.dumps(log, indent=2))
            del model, base, opt


def best_adapter() -> tuple[dict, dict, Path]:
    log = json.loads((OUT / "tune" / "grid.json").read_text())
    cands = [(r, e) for r in log for e in r["epochs"] if "val_closed" in e]
    # highest validation accuracy; ties go to the cheaper run (fewer epochs)
    r, e = max(cands, key=lambda re: (re[1]["val_closed"], -re[1]["epoch"]))
    return r, e, OUT / "tune" / f"adapter-{r['fmt']}-lr{r['lr']:g}-ep{e['epoch']}"


def test(a) -> None:
    sets = split_sets()
    r, e, path = best_adapter()
    res = {"selected": {"fmt": r["fmt"], "lr": r["lr"], "epoch": e["epoch"], "val_closed": e["val_closed"]},
           "n_test": len(sets["test"]), "n_gsm8k": len(sets["gsm8k"]), "conditions": {}}
    for name, adapter in (("base", None), ("lora", path)):
        tok, model = load(adapter)
        res["conditions"][name] = {
            "test_closed": accuracy(tok, model, sets["test"], "closed", 40),
            "test_camr": accuracy(tok, model, sets["test"], "camr", 40),
            "gsm8k": accuracy(tok, model, sets["gsm8k"], "closed", 384),
        }
        c = res["conditions"][name]
        print(name, {k: round(v["accuracy"], 3) for k, v in c.items()}, flush=True)
        del model
    res["peak_rss_mb"] = round(peak_rss_mb())
    (OUT / "test.json").write_text(json.dumps(res, indent=2))
    print("wrote", OUT / "test.json")


def camr_cost() -> None:
    """Time and storage for CAMR to take in the same documents (BGE embedder, verbatim notes)."""
    import tempfile

    from camr.config import Config
    from camr.memory.embedder import build_embedder
    from camr.memory.engine import MemoryEngine
    from camr.memory.note import Document
    from camr.memory.store import SQLiteVectorStore
    from camr.models.tokenizer import build_tokenizer

    cfg = Config.load(ROOT / "results/learn/config.yaml")
    docs = documents()
    with tempfile.TemporaryDirectory() as tmp:
        t0 = time.perf_counter()
        emb = build_embedder(cfg.embedder)
        store = SQLiteVectorStore(Path(tmp) / "store.sqlite", dim=emb.dim, embedder_name=emb.name)
        engine = MemoryEngine.from_config(cfg, store=store, embedder=emb,
                                          tokenizer=build_tokenizer(cfg.tokenizer.backend, cfg.tokenizer.name))
        t1 = time.perf_counter()
        s = engine.ingest([Document(dataset="popqa", doc_id=d["doc_id"], text=d["text"], title=d["title"]) for d in docs])
        t2 = time.perf_counter()
        mb = (Path(tmp) / "store.sqlite").stat().st_size / 1e6
    out = {"docs": len(docs), "notes": s.accepted, "load_seconds": round(t1 - t0, 1),
           "ingest_seconds": round(t2 - t1, 1), "store_mb": round(mb, 2)}
    (OUT / "camr_cost.json").write_text(json.dumps(out, indent=2))
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["tune", "test", "camr-cost", "sets"])
    ap.add_argument("--formats", default="chat,raw")
    ap.add_argument("--lrs", default="1e-4,3e-4")
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--eval-at", dest="eval_at", default="1,2,4,8")
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--accum", type=int, default=4)
    a = ap.parse_args()
    a.eval_at = {int(x) for x in a.eval_at.split(",")}
    OUT.mkdir(parents=True, exist_ok=True)
    if a.stage == "sets":
        s = split_sets()
        print({k: (len(v), sum(1 for r in v if r.get("camr"))) for k, v in s.items()}, len(documents()), "docs")
    elif a.stage == "tune":
        tune(a)
    elif a.stage == "test":
        test(a)
    else:
        camr_cost()
