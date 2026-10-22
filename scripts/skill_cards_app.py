"""Skill cards inside CAMR Personal: F32 measured again through the app itself.

F32 measured the cards in PyTorch, on the full-precision model, with the experiment's own memory and prompts. The app
runs the quantised ``qwen2.5:0.5b`` in Ollama with its own memory (the user's embedder, the Phase 2 read path) and
attaches a card as a GGUF adapter (scripts/export_cards.py). This asks the same problems through
``camr.app.assistant.Assistant``, in a fresh memory per condition, with lookups, chat memory and the link off so
that only the cards differ:

* ``notes``: the card pack's corrections taught as notes, no cards: the model answers with the app's chat prompt;
* ``cards``: the card pack installed: memory attaches a card when it names one, and the calculator does the
  arithmetic; otherwise the model answers as in ``notes``.

Splits as F32: held-out (new numbers), reworded, derived, and GSM8K problems as the unrelated control.

    python scripts/skill_cards_app.py run --pack ~/.camr/cards/formulas    # results/skills/app_cards.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("math_learning", ROOT / "scripts/math_learning.py")
ml = importlib.util.module_from_spec(_spec)
sys.modules["math_learning"] = ml
_spec.loader.exec_module(ml)

OUT = ROOT / "results/skills/app_cards.json"


def splits(control: int) -> dict[str, list[dict]]:
    data = ml.problems()
    gsm = [json.loads(line) for line in open(ROOT / "data/gsm8k/test.jsonl")][:control]
    gsm_items = [{"family": "gsm8k", "question": x["question"],
                  "answer": float(x["answer"].rsplit("####", 1)[1].replace(",", "").strip())} for x in gsm]
    return {"test": data["test"], "rephrased": data["rephrased"], "derived": data["derived"], "gsm8k": gsm_items}


def assistant(home: Path, model: str):
    from camr.app.assistant import Assistant

    a = Assistant(home, model=model)
    a.save_settings(learn_online=False, remember_chat=False, trust_learning=False, sleep_when_idle=False,
                    verified_only=False, check_model="")
    return a


def ask(a, item: dict) -> dict:
    t0 = time.perf_counter()
    t = a.ask(item["question"])  # a new conversation for every problem: no history between them
    if t.skill:
        pred = t.skill.get("value")
    else:
        pred = ml.read_answer(t.answer, "reason", item["question"])[0]
    return {"family": item["family"], "question": item["question"], "gold": item["answer"], "pred": pred,
            "correct": ml.correct(pred, item["answer"]), "card": (t.skill or {}).get("skill"),
            "answer": t.answer[-300:], "seconds": round(time.perf_counter() - t0, 2)}


def run(a) -> None:
    from camr.app import tiers

    pack = tiers.read_pack(Path(a.pack).expanduser())
    out = json.loads(OUT.read_text()) if OUT.exists() and not a.fresh else {}
    out.update({"model": a.model, "pack": pack["name"], "card_epoch": pack.get("card_epoch"),
                "control": a.control, "conditions": out.get("conditions", {})})
    sp = splits(a.control)
    if a.limit:
        sp = {k: v[: a.limit] for k, v in sp.items()}
    for cond in a.conditions.split(","):
        if cond in out["conditions"] and not a.limit:
            print(cond, "already measured", flush=True)
            continue
        home = Path(tempfile.mkdtemp(prefix=f"camr-app-cards-{cond}-"))
        shutil.copytree(pack["folder"], home / "cards" / pack["name"])
        asst = assistant(home, a.model)
        try:
            if cond == "cards":
                asst.install_card_pack(pack["name"])
            else:  # the same corrections as plain notes, no card
                for i, n in enumerate(pack["notes"]):
                    asst.teach(n["text"], title=n["title"], kind="card", doc_id=f"card-{pack['name']}-{i}")
            res = {}
            for name, items in sp.items():
                rows = [ask(asst, it) for it in items]
                res[name] = {"n": len(rows), "accuracy": round(sum(r["correct"] for r in rows) / len(rows), 4),
                             "cards_attached": sum(r["card"] is not None for r in rows),
                             "right_card": sum(r["card"] == r["family"] for r in rows),
                             "seconds_mean": round(sum(r["seconds"] for r in rows) / len(rows), 2), "rows": rows}
                print(f"{cond:6s} {name:10s} {100 * res[name]['accuracy']:5.1f}%  cards {res[name]['cards_attached']}"
                      f"/{len(rows)}", flush=True)
            out["conditions"][cond] = res
        finally:
            if cond == "cards":
                try:
                    asst.remove_card_pack(pack["name"])  # the Ollama models it registered
                except Exception:  # noqa: BLE001
                    pass
            asst.close()
            shutil.rmtree(home, ignore_errors=True)
        if not a.limit:
            OUT.write_text(json.dumps(out, indent=1))
    if "notes" in out["conditions"] and "cards" in out["conditions"]:
        out["paired"] = paired(out["conditions"]["notes"], out["conditions"]["cards"])
        if not a.limit:
            OUT.write_text(json.dumps(out, indent=1))
    report()


def paired(notes: dict, cards: dict) -> dict:
    """Per split: problems the cards fixed and broke against notes alone, with the exact paired (McNemar) test."""
    from math import comb

    out = {}
    for name in notes:
        a, b = notes[name]["rows"], cards[name]["rows"]
        lost = sum(1 for x, y in zip(a, b) if x["correct"] and not y["correct"])
        gained = sum(1 for x, y in zip(a, b) if not x["correct"] and y["correct"])
        n = lost + gained
        p = min(1.0, 2 * sum(comb(n, k) for k in range(min(lost, gained) + 1)) / 2 ** n) if n else 1.0
        out[name] = {"lost": lost, "gained": gained, "p": round(p, 4)}
    return out


def ci(rows: list[dict], reps: int = 2000) -> tuple[float, float]:
    rng = random.Random(0)
    xs = [r["correct"] for r in rows]
    accs = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(reps))
    return accs[int(0.025 * reps)], accs[int(0.975 * reps)]


def report() -> None:
    if not OUT.exists():
        return
    d = json.loads(OUT.read_text())
    lines = [f"# Skill cards inside CAMR Personal ({d['model']}, pack {d['pack']})", "",
             "| Condition | Held-out | Reworded | Derived | GSM8K (control) |", "|---|---|---|---|---|"]
    for cond, res in d["conditions"].items():
        cells = []
        for name in ("test", "rephrased", "derived", "gsm8k"):
            r = res.get(name)
            if r:
                lo, hi = ci(r["rows"])
                cells.append(f"{100 * r['accuracy']:.1f}% ({100 * lo:.0f}-{100 * hi:.0f}), card {r['cards_attached']}/{r['n']}")
            else:
                cells.append("-")
        lines.append(f"| {cond} | " + " | ".join(cells) + " |")
    if d.get("paired"):
        lines += ["", "Cards against notes alone, same problems: " + "; ".join(
            f"{k}: {v['gained']} fixed, {v['lost']} broken (p = {v['p']})" for k, v in d["paired"].items())]
    (OUT.with_suffix(".md")).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["run", "report"])
    ap.add_argument("--pack", default=str(Path.home() / ".camr/cards/formulas"))
    ap.add_argument("--model", default="qwen2.5:0.5b")
    ap.add_argument("--conditions", default="notes,cards")
    ap.add_argument("--control", type=int, default=200)
    ap.add_argument("--limit", type=int, default=0, help="smoke test: a few problems per split, nothing saved")
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args()
    {"run": run, "report": lambda _: report()}[a.part](a)
