"""Skill cards: corrections compiled into small per-skill adapters that memory attaches, against one merged adapter.

F27 (scripts/math_lora.py, results/math/lora_vs_memory.json) trained the same 40 corrections into one LoRA adapter.
It generalised to unseen problems far better than notes (88% against 50%), but the merged adapter cost the model an
unrelated skill (GSM8K 13% -> 0%). Facts belong in readable memory (F18, F21); this tests the skill tier of the
"frozen reader, learning memory" design (camr/memory/skills.py):

* skill card: one small LoRA adapter per formula family, trained only on that family's corrections with the merged
  adapter's recipe (rank 16 on the attention projections, lr 3e-4, same seed and target text); its number of epochs
  is chosen once for all cards on the pooled validation problems, as F27 chose the merged adapter's epoch;
* retrieval: the corrections stay in memory as notes (the store and engine of F27's memory condition). For each
  problem the engine recalls them; the family of the best admitted note names the card to attach. When memory
  abstains, or its best note is not a correction, no card is attached and the frozen model answers alone;
* the model's weights never change: a card is attached for one problem and removed after it.

Conditions, all in one runtime: base, memory (notes), merged (one adapter, F27's recipe and epoch), card (routed by
memory), card-oracle (the problem's own family: the ceiling of routing), notes+card. Splits as F27: the training
problems, held-out (new numbers), reworded, derived, and 30 GSM8K problems as the unrelated control.

    python scripts/skill_cards.py run       # results/skills/skill_cards.json (resumable: finished conditions are kept)
    python scripts/skill_cards.py report    # results/skills/skill_cards.md
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
OUT = ROOT / "results/skills"
BASE = "Qwen/Qwen2.5-0.5B-Instruct"
PREFIX = "Correction: "  # the source title scripts/math_lora.py gives each correction note; it names the card
TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj"]

_spec = importlib.util.spec_from_file_location("math_learning", ROOT / "scripts/math_learning.py")
ml = importlib.util.module_from_spec(_spec)
sys.modules["math_learning"] = ml
_spec.loader.exec_module(ml)


# ---------------------------------------------------------------------- model
def pick_device(name: str) -> str:
    if name == "auto":
        return "mps" if torch.backends.mps.is_available() else "cpu"
    return name


def release(dev: str) -> None:
    """Return cached GPU blocks to the system. On Apple GPUs (MPS) the allocator keeps every block it ever made;
    batches of different lengths make blocks of different sizes, so without this a run grew past 17 GB and swapped."""
    if dev == "mps":
        torch.mps.empty_cache()


def load(dev: str, dtype: str = "float32"):
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(BASE)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    # bfloat16 halves the model's memory (about 1 GB for 0.5B); the adapters PEFT adds still train in float32
    model = AutoModelForCausalLM.from_pretrained(BASE, dtype=getattr(torch, dtype)).to(dev)
    model.eval()
    return tok, model


def chat(tok, text: str) -> str:
    """The prompt as the model sees it in a chat (its own template, as Ollama applies it)."""
    return tok.apply_chat_template([{"role": "user", "content": text}], tokenize=False, add_generation_prompt=True)


@torch.no_grad()
def generate(tok, model, prompts: list[str], dev: str, max_new: int = 200, batch: int = 8) -> list[str]:
    out = []
    for i in range(0, len(prompts), batch):
        enc = tok([chat(tok, p) for p in prompts[i:i + batch]], return_tensors="pt", padding=True,
                  add_special_tokens=False).to(dev)
        gen = model.generate(**enc, max_new_tokens=max_new, do_sample=False, pad_token_id=tok.pad_token_id)
        out += [tok.decode(row, skip_special_tokens=True) for row in gen[:, enc["input_ids"].shape[1]:]]
        del enc, gen
        release(dev)
    return out


def generate_with_cards(tok, model, prompts: list[str], cards: list[str | None], dev: str) -> list[str]:
    """Each prompt answered with its own card attached (None: the frozen model alone). Prompts that share a card
    are batched together; the base weights are never touched."""
    out: list[str | None] = [None] * len(prompts)
    for card in sorted(set(cards), key=lambda c: (c is not None, c or "")):
        idx = [i for i, c in enumerate(cards) if c == card]
        if card is None:
            if hasattr(model, "disable_adapter"):
                with model.disable_adapter():
                    texts = generate(tok, model, [prompts[i] for i in idx], dev)
            else:
                texts = generate(tok, model, [prompts[i] for i in idx], dev)
        else:
            model.set_adapter(card)
            texts = generate(tok, model, [prompts[i] for i in idx], dev)
        for i, t in zip(idx, texts):
            out[i] = t
    return out  # type: ignore[return-value]


# ---------------------------------------------------------------------- training
def target(it: dict, fams) -> str:
    """What the model is taught to write for a correction: the rule, then the expression (as scripts/math_lora.py)."""
    rule = fams[it["family"]].rule.split(":", 1)[-1].strip().split(". ")[0]
    return f"Formula: {rule}\n#### {it['expr']}"


def train_adapter(tok, base, fit: list[dict], fams, dev: str, *, save_at: list[int], save_dir: Path, lr: float,
                  rank: int, seed: int) -> tuple[object, list[float]]:
    """Train one LoRA adapter on ``fit`` and save it after each epoch in ``save_at``; returns the base model with the
    adapter layers removed again, and the loss per epoch."""
    from peft import LoraConfig, get_peft_model

    torch.manual_seed(seed)
    model = get_peft_model(base, LoraConfig(r=rank, lora_alpha=2 * rank, lora_dropout=0.05, target_modules=TARGETS,
                                            task_type="CAUSAL_LM"))
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr)
    rng = random.Random(seed)
    examples = []
    for it in fit:
        p_ids = tok(chat(tok, ml.CALC_BARE.format(question=it["question"])), add_special_tokens=False)["input_ids"]
        t_ids = tok(target(it, fams) + "<|im_end|>", add_special_tokens=False)["input_ids"]
        examples.append((p_ids, t_ids))
    losses = []
    for epoch in range(1, max(save_at) + 1):
        model.train()
        order = list(range(len(examples)))
        rng.shuffle(order)
        total = 0.0
        for i in range(0, len(order), 4):
            # One optimiser step per four problems, as scripts/math_lora.py: the mean loss over the target tokens of
            # all four. Each problem is run on its own (gradients accumulate) and only its target positions get
            # vocabulary logits, so a step needs a fraction of the memory a padded batch with full logits does.
            chunk = [examples[j] for j in order[i:i + 4]]
            n_target = sum(len(t) for _, t in chunk)
            step = 0.0
            for p_ids, t_ids in chunk:
                ids = torch.tensor([p_ids + t_ids], device=dev)
                logits = model(input_ids=ids, logits_to_keep=len(t_ids) + 1).logits[0, :-1].float()
                loss = torch.nn.functional.cross_entropy(logits, torch.tensor(t_ids, device=dev), reduction="sum")
                (loss / n_target).backward()
                step += float(loss)
                del ids, logits, loss
            opt.step()
            opt.zero_grad()
            total += step / n_target * len(chunk)
            release(dev)
        losses.append(round(total / len(examples), 4))
        if epoch in save_at:
            model.save_pretrained(save_dir / f"e{epoch}")
    model.eval()
    del opt
    base = model.unload()  # the frozen base again, with no adapter layers left in it
    release(dev)
    return base, losses


# ---------------------------------------------------------------------- scoring
def score(items: list[dict], texts: list[str], cards: list[str | None] | None = None) -> list[dict]:
    rows = []
    for k, (it, t) in enumerate(zip(items, texts)):
        pred, grounded = ml.read_answer(t, "calc", it["question"])
        rows.append({"family": it["family"], "invented": it["invented"], "question": it["question"],
                     "gold": it["answer"], "pred": pred, "correct": ml.correct(pred, it["answer"]),
                     "grounded": grounded, "card": None if cards is None else cards[k], "answer": t.strip()[-200:]})
    return rows


def routing(rows: list[dict]) -> dict:
    """How often memory attached the problem's own card (for GSM8K, how often it attached none)."""
    right = sum((r["card"] is None) if r["family"] == "gsm8k" else (r["card"] == r["family"]) for r in rows)
    return {"right": round(right / max(1, len(rows)), 4), "none": sum(r["card"] is None for r in rows),
            "wrong_card": sum(r["card"] is not None and r["card"] != r["family"] for r in rows)}


# ---------------------------------------------------------------------- run
def run(a) -> None:
    from peft import PeftModel

    from camr.memory.note import Document
    from camr.memory.skills import SkillRouter

    dev = pick_device(a.device)
    OUT.mkdir(parents=True, exist_ok=True)
    res_path = OUT / "skill_cards.json"
    out = json.loads(res_path.read_text()) if res_path.exists() and not a.fresh else {}
    out.update({"base_model": BASE, "problem_seed": ml.SEED, "train_seed": a.seed, "lr": a.lr, "rank": a.rank,
                "device": dev, "merged_epochs": a.merged_epochs, "card_epochs_tried": a.card_epochs})
    out.setdefault("conditions", {})
    save = lambda: ml.save(res_path, out)  # noqa: E731

    data = ml.problems()
    fams = {f.key: f for f in ml.FAMILIES}
    fit, val, per = [], [], {}
    for it in data["train"]:
        per.setdefault(it["family"], []).append(it)
    for items in per.values():  # four to train on, two to choose the epoch with (as F27)
        fit += items[:4]
        val += items[4:]
    gsm = [json.loads(line) for line in open(ROOT / "data/gsm8k/test.jsonl")][: a.control]
    gsm_items = [{"family": "gsm8k", "invented": False, "question": x["question"],
                  "answer": float(x["answer"].rsplit("####", 1)[1].replace(",", "").strip())} for x in gsm]
    splits = {"train": fit, "test": data["test"], "rephrased": data["rephrased"], "derived": data["derived"],
              "gsm8k": gsm_items}
    if a.limit:  # smoke test only: a few problems per split
        splits = {s: v[: a.limit] for s, v in splits.items()}
        val = val[: a.limit]
    out["sizes"] = {s: len(v) for s, v in splits.items()} | {"val": len(val)}

    # memory: the corrections of the training problems as notes, exactly as F27's memory condition
    store_path = OUT / "stores" / "corrections.sqlite"
    store_path.parent.mkdir(parents=True, exist_ok=True)
    for f in store_path.parent.glob(store_path.name + "*"):
        f.unlink()
    engine, store = ml.engine_at(store_path)
    engine.ingest([Document("correction", f"{it['family']}-{k}", ml.correction_note(fams[it["family"]], it),
                            f"{PREFIX}{it['family']}") for k, it in enumerate(fit)])
    router = SkillRouter(engine, PREFIX)
    routes = {s: [router.route(it["question"]) for it in items] for s, items in splits.items()}
    bare = lambda it: ml.CALC_BARE.format(question=it["question"])  # noqa: E731

    def noted(it, route):
        return ml.CALC_MEM.format(context=route.context.strip(), question=it["question"]) if route.context else bare(it)

    tok, base = load(dev, a.dtype)
    out["dtype"] = a.dtype
    t_all = time.perf_counter()

    # ---- train: one merged adapter (F27's recipe), one card per family
    merged_dir = OUT / "stores" / "merged"
    if not (merged_dir / f"e{a.merged_epochs}").exists():
        t0 = time.perf_counter()
        base, losses = train_adapter(tok, base, fit, fams, dev, save_at=[a.merged_epochs], save_dir=merged_dir,
                                     lr=a.lr, rank=a.rank, seed=a.seed)
        out["merged_training"] = {"losses": losses, "seconds": round(time.perf_counter() - t0, 1)}
        save()
    card_root = OUT / "stores" / "cards"
    for fam in fams:
        if not all((card_root / fam / f"e{e}").exists() for e in a.card_epochs):
            t0 = time.perf_counter()
            base, losses = train_adapter(tok, base, per[fam][:4], fams, dev, save_at=a.card_epochs,
                                         save_dir=card_root / fam, lr=a.lr, rank=a.rank, seed=a.seed)
            out.setdefault("card_training", {})[fam] = {"losses": losses, "seconds": round(time.perf_counter() - t0, 1)}
            save()
            print("card", fam, losses[-1], flush=True)

    # ---- one model holding every adapter; none of them is active unless set
    model = PeftModel.from_pretrained(base, merged_dir / f"e{a.merged_epochs}", adapter_name="merged")
    for e in a.card_epochs:
        for fam in fams:
            model.load_adapter(card_root / fam / f"e{e}", adapter_name=f"{fam}@{e}")
    model.eval()

    # ---- choose the cards' epoch on the pooled validation problems (each with its own card), as F27 did
    if "card_epoch" not in out:
        sweep = {}
        for e in a.card_epochs:
            rows = score(val, generate_with_cards(tok, model, [bare(it) for it in val],
                                                  [f"{it['family']}@{e}" for it in val], dev))
            sweep[e] = ml.summary(rows)["all"]
            print("card epochs", e, "validation", sweep[e], flush=True)
        out["card_epoch_sweep"] = {str(e): v for e, v in sweep.items()}
        out["card_epoch"] = max(a.card_epochs, key=lambda e: (sweep[e], -e))
        save()
    ce = out["card_epoch"]

    # ---- the conditions
    def condition(name: str, prompt_for, card_for):
        if name in out["conditions"]:
            return
        t0 = time.perf_counter()
        res, rows_out = {}, {}
        for s, items in splits.items():
            prompts = [prompt_for(it, r) for it, r in zip(items, routes[s])]
            cards = [card_for(it, r) for it, r in zip(items, routes[s])]
            rows = score(items, generate_with_cards(tok, model, prompts, cards, dev),
                         [c.split("@")[0] if c and c != "merged" else (None if c is None else c) for c in cards])
            res[s] = ml.summary(rows)
            if any(c not in (None, "merged") for c in cards) or name.startswith("card"):
                res[s]["routing"] = routing(rows)
            rows_out[s] = [(r["question"][:120], r["card"], r["pred"], r["correct"]) for r in rows]
        res["seconds"] = round(time.perf_counter() - t0, 1)
        out["conditions"][name] = res
        out.setdefault("rows", {})[name] = rows_out
        save()
        print(name, {s: res[s]["all"] for s in splits}, f"{res['seconds']}s", flush=True)

    condition("base", lambda it, r: bare(it), lambda it, r: None)
    condition("memory", noted, lambda it, r: None)
    condition("merged", lambda it, r: bare(it), lambda it, r: "merged")
    condition("card", lambda it, r: bare(it), lambda it, r: f"{r.skill}@{ce}" if r.skill else None)
    condition("card-oracle", lambda it, r: bare(it),
              lambda it, r: f"{it['family']}@{ce}" if it["family"] in fams else None)
    condition("notes+card", noted, lambda it, r: f"{r.skill}@{ce}" if r.skill else None)
    out["seconds"] = round(time.perf_counter() - t_all, 1)
    save()
    store.close()
    report(a)


def control(a) -> None:
    """The unrelated control at a size that can show harm: base, merged and routed cards on ``--control`` GSM8K
    problems (the run's 30 can only show a direction). Uses the adapters ``run`` trained; nothing is retrained.
    Reports, per condition, accuracy with a 95% bootstrap interval and the problems lost and gained against base."""
    from peft import PeftModel

    from camr.memory.note import Document
    from camr.memory.skills import SkillRouter

    dev = pick_device(a.device)
    res_path = OUT / "skill_cards.json"
    out = json.loads(res_path.read_text())
    ce = out["card_epoch"]
    fams = {f.key: f for f in ml.FAMILIES}
    fit = []
    per = {}
    for it in ml.problems()["train"]:
        per.setdefault(it["family"], []).append(it)
    for items in per.values():
        fit += items[:4]
    gsm = [json.loads(line) for line in open(ROOT / "data/gsm8k/test.jsonl")][: a.control]
    items = [{"family": "gsm8k", "invented": False, "question": x["question"],
              "answer": float(x["answer"].rsplit("####", 1)[1].replace(",", "").strip())} for x in gsm]
    store_path = OUT / "stores" / "control.sqlite"
    for f in store_path.parent.glob(store_path.name + "*"):
        f.unlink()
    engine, store = ml.engine_at(store_path)
    from camr.memory.embedder import CachedEmbedder

    # the new GSM8K questions' vectors go to this experiment's own cache, not the committed results/math one
    engine.embedder = CachedEmbedder(engine.embedder.inner, OUT / "vectors.sqlite")
    engine.ingest([Document("correction", f"{it['family']}-{k}", ml.correction_note(fams[it["family"]], it),
                            f"{PREFIX}{it['family']}") for k, it in enumerate(fit)])
    routes = [SkillRouter(engine, PREFIX).route(it["question"]) for it in items]
    tok, base = load(dev, out.get("dtype", a.dtype))
    model = PeftModel.from_pretrained(base, OUT / "stores" / "merged" / f"e{out['merged_epochs']}", adapter_name="merged")
    for fam in fams:
        model.load_adapter(OUT / "stores" / "cards" / fam / f"e{ce}", adapter_name=f"{fam}@{ce}")
    model.eval()
    prompts = [ml.CALC_BARE.format(question=it["question"]) for it in items]
    plans = {"base": [None] * len(items), "merged": ["merged"] * len(items),
             "card": [f"{r.skill}@{ce}" if r.skill else None for r in routes]}
    right = {}
    for name, cards in plans.items():
        rows = score(items, generate_with_cards(tok, model, prompts, cards, dev))
        right[name] = [bool(r["correct"]) for r in rows]
        print("control", name, round(sum(right[name]) / len(items), 4), flush=True)
    rng = random.Random(0)
    n = len(items)

    def interval(xs):
        means = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) / n for _ in range(2000))
        return [round(means[49], 4), round(means[1949], 4)]

    out["control_large"] = {
        "n": n, "cards_attached": sum(c is not None for c in plans["card"]),
        "conditions": {k: {"accuracy": round(sum(v) / n, 4), "ci95": interval(v),
                           "lost_vs_base": sum(b and not x for b, x in zip(right["base"], v)),
                           "gained_vs_base": sum(x and not b for b, x in zip(right["base"], v))}
                       for k, v in right.items()}}
    ml.save(res_path, out)
    store.close()
    print(json.dumps(out["control_large"], indent=1))


# ---------------------------------------------------------------------- report
def mcnemar(lost: int, gained: int) -> float:
    """Exact two-sided McNemar p: are the answers a condition broke and fixed (against base) a fair coin?"""
    from math import comb

    n = lost + gained
    return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(min(lost, gained) + 1)) / 2 ** n)


NAMES = {"base": "Base model", "memory": "Memory notes", "merged": "One merged LoRA",
         "card": "Skill card, routed by memory", "card-oracle": "Skill card, right family given",
         "notes+card": "Notes + skill card"}


def report(a=None) -> None:
    d = json.loads((OUT / "skill_cards.json").read_text())
    cols = ["train", "test", "rephrased", "derived", "gsm8k"]
    heads = ["seen", "held-out", "reworded", "derived", "GSM8K (unrelated)"]
    lines = [f"# Skill cards against one merged adapter ({d['base_model']}, {d['device']}, {d.get('dtype', 'float32')})",
             "",
             f"Problem draw seed {d['problem_seed']} (F27's fresh draw); training seed {d['train_seed']}; LoRA rank "
             f"{d['rank']}, lr {d['lr']}; merged adapter {d['merged_epochs']} epochs (F27's choice); cards "
             f"{d.get('card_epoch')} epochs, chosen on validation from {d['card_epochs_tried']} "
             f"(validation: {d.get('card_epoch_sweep')}).", "",
             "| Condition | " + " | ".join(heads) + " | memory picked the right card |",
             "|---|" + "---|" * (len(cols) + 1)]
    for key, name in NAMES.items():
        c = d["conditions"].get(key)
        if not c:
            continue
        cells = [f"{100 * c[s]['all']:.1f}%" for s in cols]
        rt = [c[s]["routing"]["right"] for s in cols if "routing" in c[s]]
        route = f"{100 * sum(rt) / len(rt):.1f}% (mean of splits)" if rt and key != "card-oracle" else "—"
        lines.append(f"| {name} | " + " | ".join(cells) + f" | {route} |")
    lines += ["", f"Sizes: {d['sizes']}. Run time {d.get('seconds')} s."]
    cl = d.get("control_large")
    if cl:
        lines += ["", f"## Unrelated control at size: {cl['n']} GSM8K problems (cards attached to {cl['cards_attached']})",
                  "", "| Condition | accuracy | 95% bootstrap interval | lost vs base | gained vs base | answers changed "
                  "| exact McNemar p |", "|---|---|---|---|---|---|---|"]
        for k, v in cl["conditions"].items():
            b, c = v["lost_vs_base"], v["gained_vs_base"]
            p = "—" if k == "base" else f"{mcnemar(b, c):.3f}"
            lines.append(f"| {NAMES.get(k, k)} | {100 * v['accuracy']:.1f}% | {100 * v['ci95'][0]:.1f}-"
                         f"{100 * v['ci95'][1]:.1f}% | {b} | {c} | {b + c} | {p} |")
    (OUT / "skill_cards.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["run", "control", "report"])
    ap.add_argument("--device", default="auto", help="auto (mps when available), mps or cpu")
    ap.add_argument("--dtype", default="float32", choices=["float32", "bfloat16"],
                    help="model weights; bfloat16 halves memory (every condition runs in the same one)")
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--merged-epochs", type=int, default=6)
    ap.add_argument("--card-epochs", type=lambda s: [int(x) for x in s.split(",")], default=[6, 15, 30, 60])
    ap.add_argument("--control", type=int, default=30)
    ap.add_argument("--fresh", action="store_true", help="drop finished conditions and run them again")
    ap.add_argument("--out", default="", help="results folder (default results/skills)")
    ap.add_argument("--limit", type=int, default=0, help="smoke test: this many problems per split")
    a = ap.parse_args()
    if a.out:
        OUT = Path(a.out)
    {"run": run, "control": control, "report": report}[a.part](a)
