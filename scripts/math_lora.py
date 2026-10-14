"""Fine-tuning against memory on the same corrections: which one learns the formula, which one memorises?

Same base model (Qwen2.5-0.5B-Instruct), same runtime (Hugging Face transformers, CPU, float32, greedy
decoding), same problems as scripts/math_learning.py:

* base: the model alone;
* memory: the model reading the stored corrections (rule + one worked problem per training problem),
  recalled by the engine for each new problem; weights unchanged;
* LoRA: the model fine-tuned on the same training problems (question -> formula and expression),
  evaluated after every epoch on the problems it was trained on, on a validation split (to choose the
  epoch, as one would) and on held-out problems.

Overfitting shows as a gap: high accuracy on the training problems, low on new ones, growing with
epochs. Learning shows as held-out accuracy close to training accuracy, holding up on rephrased and
derived problems, and no loss on unrelated problems (GSM8K).

    python scripts/math_lora.py run
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/math"
BASE = "Qwen/Qwen2.5-0.5B-Instruct"

_spec = importlib.util.spec_from_file_location("math_learning", ROOT / "scripts/math_learning.py")
ml = importlib.util.module_from_spec(_spec)
sys.modules["math_learning"] = ml
_spec.loader.exec_module(ml)


def load():
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(BASE)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.float32)
    model.eval()
    return tok, model


def chat(tok, text: str) -> str:
    """The prompt as the model sees it in a chat (its own template, as Ollama applies it)."""
    return tok.apply_chat_template([{"role": "user", "content": text}], tokenize=False, add_generation_prompt=True)


@torch.no_grad()
def generate(tok, model, prompts: list[str], max_new: int = 200, batch: int = 8) -> list[str]:
    out = []
    for i in range(0, len(prompts), batch):
        enc = tok([chat(tok, p) for p in prompts[i:i + batch]], return_tensors="pt", padding=True,
                  add_special_tokens=False)
        gen = model.generate(**enc, max_new_tokens=max_new, do_sample=False, pad_token_id=tok.pad_token_id)
        for row in gen[:, enc["input_ids"].shape[1]:]:
            out.append(tok.decode(row, skip_special_tokens=True))
    return out


def evaluate(tok, model, items: list[dict], prompt_for, max_new: int = 200) -> list[dict]:
    texts = generate(tok, model, [prompt_for(it) for it in items], max_new=max_new)
    rows = []
    for it, t in zip(items, texts):
        pred, ok = ml.read_answer(t, "calc", it["question"])
        rows.append({"family": it["family"], "invented": it["invented"], "question": it["question"],
                     "gold": it["answer"], "pred": pred, "correct": ml.correct(pred, it["answer"]), "grounded": ok,
                     "answer": t.strip()[-300:]})
    return rows


def memorisation(rows: list[dict], fit: list[dict]) -> dict:
    """Wrong answers to new problems that repeat a training answer of the same family: the sign of copying."""
    stored = {}
    for it in fit:
        stored.setdefault(it["family"], set()).add(round(it["answer"], 2))
    wrong = [r for r in rows if not r["correct"] and r["pred"] is not None and r["family"] in stored]
    return {"wrong_answers": len(wrong),
            "equal_to_a_training_answer": sum(round(r["pred"], 2) in stored[r["family"]] for r in wrong)}


def target(it: dict, fams) -> str:
    rule = fams[it["family"]].rule.split(":", 1)[-1].strip().split(". ")[0]
    return f"Formula: {rule}\n#### {it['expr']}"


def train_lora(tok, base, fit: list[dict], fams, *, epochs: int, lr: float, rank: int, seed: int, on_epoch):
    from peft import LoraConfig, get_peft_model

    torch.manual_seed(seed)
    model = get_peft_model(base, LoraConfig(r=rank, lora_alpha=2 * rank, lora_dropout=0.05,
                                            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
                                            task_type="CAUSAL_LM"))
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr)
    rng = random.Random(seed)
    examples = []
    for it in fit:
        p_ids = tok(chat(tok, ml.CALC_BARE.format(question=it["question"])), add_special_tokens=False)["input_ids"]
        t_ids = tok(target(it, fams) + "<|im_end|>", add_special_tokens=False)["input_ids"]
        examples.append((p_ids + t_ids, [-100] * len(p_ids) + t_ids))
    for epoch in range(1, epochs + 1):
        model.train()
        order = list(range(len(examples)))
        rng.shuffle(order)
        total = 0.0
        for i in range(0, len(order), 4):
            chunk = [examples[j] for j in order[i:i + 4]]
            width = max(len(x) for x, _ in chunk)
            ids = torch.tensor([[tok.pad_token_id] * (width - len(x)) + x for x, _ in chunk])
            lab = torch.tensor([[-100] * (width - len(y)) + y for _, y in chunk])
            att = (torch.arange(width)[None, :] >= torch.tensor([width - len(x) for x, _ in chunk])[:, None]).long()
            loss = model(input_ids=ids, attention_mask=att, labels=lab).loss
            loss.backward()
            opt.step()
            opt.zero_grad()
            total += float(loss) * len(chunk)
        model.eval()
        on_epoch(epoch, model, total / len(examples))
    return model


def summary(rows):
    return ml.summary(rows)


def run(a) -> None:
    data = ml.problems()
    fams = {f.key: f for f in ml.FAMILIES}
    fit, val = [], []
    per = {}
    for it in data["train"]:
        per.setdefault(it["family"], []).append(it)
    for items in per.values():  # four to train on, two to choose the epoch with
        fit += items[:4]
        val += items[4:]
    gsm = [json.loads(line) for line in open(ROOT / "data/gsm8k/test.jsonl")][: a.control]
    gsm_items = [{"family": "gsm8k", "invented": False, "question": x["question"],
                  "answer": float(x["answer"].rsplit("####", 1)[1].replace(",", "").strip())} for x in gsm]
    tok, model = load()
    out = {"base_model": BASE, "seed": ml.SEED, "fit": len(fit), "val": len(val), "test": len(data["test"]), "lr": a.lr,
           "rank": a.rank, "conditions": {}}
    t0 = time.perf_counter()
    bare = lambda it: ml.CALC_BARE.format(question=it["question"])  # noqa: E731

    def full(name, prompt_for, m):
        rows = {s: evaluate(tok, m, items, prompt_for) for s, items in
                (("train", fit), ("test", data["test"]), ("rephrased", data["rephrased"]),
                 ("derived", data["derived"]), ("gsm8k", gsm_items))}
        res = {s: summary(r) for s, r in rows.items()}
        res["gap"] = round(res["train"]["all"] - res["test"]["all"], 4)
        res["memorisation"] = memorisation(rows["test"] + rows["rephrased"], fit)
        out.setdefault("rows", {})[name] = {s: [(r["question"], r["pred"], r["correct"], r["answer"][-160:])
                                                for r in rs] for s, rs in rows.items() if s != "gsm8k"}
        out["conditions"][name] = res
        ml.save(OUT / "lora_vs_memory.json", out)
        print(name, json.dumps({k: v.get("all", v) if isinstance(v, dict) else v for k, v in res.items()}), flush=True)

    full("base", bare, model)
    # memory: the corrections of the training problems, recalled by the engine for each problem
    from camr.memory.note import Document

    store_path = OUT / "stores" / "hf_memory.sqlite"
    store_path.parent.mkdir(parents=True, exist_ok=True)
    for f in store_path.parent.glob(store_path.name + "*"):
        f.unlink()
    engine, store = ml.engine_at(store_path)
    engine.ingest([Document("correction", f"{it['family']}-{k}", ml.correction_note(fams[it["family"]], it),
                            f"Correction: {it['family']}") for k, it in enumerate(fit)])

    def with_memory(it):
        r = engine.recall(it["question"], touch=False)
        if r.abstained or not r.context:
            return bare(it)
        return ml.CALC_MEM.format(context=r.context.strip(), question=it["question"])

    full("memory", with_memory, model)
    # LoRA: the same training problems, epoch by epoch
    curve = []

    def on_epoch(epoch, m, loss):
        if epoch in a.eval_at:
            rec = {"epoch": epoch, "loss": round(loss, 4)}
            for s, items in (("train", fit), ("val", val), ("test", data["test"])):
                rec[s] = summary(evaluate(tok, m, items, bare))["all"]
            curve.append(rec)
            out["lora_curve"] = curve
            ml.save(OUT / "lora_vs_memory.json", out)
            print("lora", rec, flush=True)
            m.save_pretrained(OUT / "stores" / f"lora-ep{epoch}")

    lora = train_lora(tok, model, fit, fams, epochs=max(a.eval_at), lr=a.lr, rank=a.rank, seed=a.seed,
                      on_epoch=on_epoch)
    best = max(curve, key=lambda r: (r["val"], -r["epoch"]))  # chosen on validation, as one would
    out["lora_chosen_epoch"] = best["epoch"]
    from peft import PeftModel

    base_again = load()[1]
    chosen = PeftModel.from_pretrained(base_again, OUT / "stores" / f"lora-ep{best['epoch']}")
    chosen.eval()
    full(f"lora (epoch {best['epoch']}, chosen on validation)", bare, chosen)
    last = max(a.eval_at)
    if last != best["epoch"]:
        full(f"lora (epoch {last})", bare, lora)
    out["seconds"] = round(time.perf_counter() - t0, 1)
    ml.save(OUT / "lora_vs_memory.json", out)
    store.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["run"])
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--eval-at", type=lambda s: [int(x) for x in s.split(",")], default=[1, 3, 6])
    ap.add_argument("--control", type=int, default=30)
    a = ap.parse_args()
    {"run": run}[a.part](a)
