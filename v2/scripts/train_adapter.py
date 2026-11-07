"""Train the reading adapter (camr_engine.adapter): Qwen3 4B learns to read laid notes (the latest value wins, both
halves of a bridge, the asked one of two lookalikes, "I don't know" only when the notes never say).

    # 1. examples from practice worlds only (never seed 1, the locked exam; never seed 3, the finder's check world,
    #    or the harder set built on it)
    .venv/bin/python scripts/train_adapter.py data --worlds ../work/haul/train-s5 ../work/haul/train-s6 \
        ../work/haul/train-s7 --out ../work/train/reading.jsonl

    # 2. train (the context is read with the adapter OFF, the question and answer with it ON, as when answering)
    .venv/bin/python scripts/train_adapter.py train --data ../work/train/reading.jsonl --name reading-v1

    # 3. a first look on a world it never trained on: the plain model and the adapter on the same examples
    .venv/bin/python scripts/train_adapter.py check --data ../work/train/reading.jsonl --name reading-v1

Each example mirrors the engine's desk: the header ("Notes:"), the moments as the engine keeps them
("[2025-09-23, day 2] User: ..."), "End of notes. Today is <date>." and the question. The moments are the word
finder's closest ones at that cut, with the moments the answer needs put in when the finder missed them, so the
adapter learns reading and not finding. The targets are the generator's own answers: no model wrote them, and no
answer from Claude is ever used.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import sys
import time
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V2))

FAMILIES = ("fact", "changed", "two_hop", "lookalike", "never")
PER_FAMILY = {"fact": 50, "changed": 40, "two_hop": 25, "lookalike": 25, "never": 25}  # per world and cut
CUT_NAMES = ("256K", "1M", "2M")
CONTEXT = 10  # moments on the desk in an example: a room's worth and the closest few
CONTEXT_CHARS = 9000  # about 2,300 tokens of moments at most
REFUSED_SEEDS = {1, 3, 4}  # the locked exam, the finder's check world, the harder set (built on seed 3's world)
VAL_WORLD_CUT = ("train-s7", "2M")  # held back from training: a world and cut the adapter never sees
DAY = re.compile(r"^Day (\d+) · [A-Z][a-z]+ (\d{1,2}) ([A-Z][a-z]+) (\d{4})$")
DECLINE = "I don't know."


def world_moments(events: list[dict]) -> tuple[list[str], dict[int, int], dict[int, dt.date]]:
    """(moment texts as the engine keeps them, event -> moment, day -> date)."""
    from camr_engine.bench.haul.recall import moment_of_event
    from camr_engine.bench.longhaul import line

    dates: dict[int, dt.date] = {}
    for e in events:
        m = DAY.match(e["text"]) if e["role"] == "system" else None
        if m:
            dates[int(m.group(1))] = dt.datetime.strptime(f"{m.group(2)} {m.group(3)} {m.group(4)}", "%d %B %Y").date()
    to_mid = moment_of_event(events)
    texts = [""] * len(to_mid)
    for i, mid in to_mid.items():
        e = events[i]
        texts[mid] = f"[{dates[e['day']].isoformat()}, day {e['day']}] {line(e)}"
    return texts, to_mid, dates


def target(q: dict) -> str:
    if q["family"] == "never":
        return DECLINE
    a = str(q["answer"]).strip()
    return a if a.endswith((".", "?", "!")) else a + "."


def examples_for(world: Path, rng: random.Random) -> list[dict]:
    from camr_engine.bench.haul.sample import askable
    from camr_engine.bench.haul.script import CUTS, load_events, load_probes
    from camr_engine.finder import LineIndex

    manifest = json.loads((world / "manifest.json").read_text())
    if int(manifest["seed"]) in REFUSED_SEEDS:
        raise SystemExit(f"{world} is seed {manifest['seed']}: never trained on")
    events, probes = load_events(world), load_probes(world)
    texts, to_mid, dates = world_moments(events)
    bad = [i for i, mid in to_mid.items() if events[i]["text"][:40] not in texts[mid]]
    assert not bad, f"{len(bad)} events do not match their moments"
    out = []
    for name in CUT_NAMES:
        cut = CUTS[name]
        told = sum(1 for e in events if e["cum_tokens"] <= cut)
        n = sum(1 for i in range(told) if i in to_mid)
        index = LineIndex(texts[:n])
        today = dates[events[told - 1]["day"]]
        pool = [q for q in askable(probes, cut) if q["family"] in FAMILIES]
        rng.shuffle(pool)
        taken = {f: 0 for f in FAMILIES}
        for q in pool:
            if taken[q["family"]] >= PER_FAMILY[q["family"]]:
                continue
            need = sorted({to_mid[int(e)] for e in q.get("events", []) if int(e) in to_mid and to_mid[int(e)] < n})
            if q["family"] != "never" and not need:
                continue
            found = [int(m) for m in index.order(q["ask"])[: CONTEXT * 2]]
            chosen = list(need) + [m for m in found if m not in need]
            chosen = chosen[:max(CONTEXT, len(need))]
            while sum(len(texts[m]) for m in chosen) > CONTEXT_CHARS and len(chosen) > len(need):
                chosen.pop()  # the finder's farthest go first; the needed ones stay
            taken[q["family"]] += 1
            out.append({"world": world.name, "seed": manifest["seed"], "cut": name, "id": q["id"],
                        "family": q["family"], "question": q["ask"], "target": target(q),
                        "moments": [texts[m] for m in sorted(chosen)], "today": today.isoformat(),
                        "intro": "longhaul" if rng.random() < 0.7 else "app",
                        "found": bool(set(need) <= set(found[:CONTEXT])), "probe": q})
    return out


def build_data(worlds: list[Path], out: Path, seed: int = 0) -> None:
    rng = random.Random(f"train-data:{seed}")
    rows = []
    for w in worlds:
        got = examples_for(w, rng)
        print(f"{w.name}: {len(got)} examples")
        rows += got
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    val = sum(1 for r in rows if (r["world"], r["cut"]) == VAL_WORLD_CUT)
    print(f"{len(rows)} examples -> {out} ({val} held back to check on)")


# -- turning an example into the engine's own token ids

def ids_of(tok, ex: dict) -> tuple[list[int], list[int], list[int]]:
    """(context read with the adapter off, the question part read with it on, the answer's tokens)."""
    from camr_engine.bench.local import LONGHAUL_INTRO
    from camr_engine.memory import _SLOT, INTRO, today_text

    intro = LONGHAUL_INTRO if ex["intro"] == "longhaul" else INTRO
    today = dt.date.fromisoformat(ex["today"])
    system = f"{intro}\n\nNotes:\n{_SLOT}End of notes.\nToday is {today_text(today)}."
    text = tok.apply_chat_template([{"role": "system", "content": system}, {"role": "user", "content": ex["question"]}],
                                   add_generation_prompt=True, enable_thinking=False, tokenize=False)
    head, rest = text.split(_SLOT)
    context = tok.encode(head) + [i for m in ex["moments"] for i in tok.encode(m + "\n")]
    answer = tok.encode(ex["target"]) + [tok.eos_token_id]
    return context, tok.encode(rest), answer


def read_context(model, ids: list[int]):
    import mlx.core as mx
    from mlx_lm.models.cache import make_prompt_cache

    from camr_engine import adapter

    cache = make_prompt_cache(model)
    with adapter.off(model):
        for i in range(0, len(ids), 1024):
            model(mx.array(ids[i:i + 1024])[None], cache=cache)
            mx.eval([c.state for c in cache])
    return cache


def load_rows(path: Path) -> tuple[list[dict], list[dict]]:
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    for r in rows:
        if int(r["seed"]) in REFUSED_SEEDS:
            raise SystemExit(f"example from seed {r['seed']}: refused")
    val = [r for r in rows if (r["world"], r["cut"]) == VAL_WORLD_CUT]
    train = [r for r in rows if (r["world"], r["cut"]) != VAL_WORLD_CUT]
    return train, val


def train(data: Path, name: str, *, lr: float = 2e-5, epochs: int = 1, seed: int = 0, repo: str | None = None) -> Path:
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx_lm import load

    from camr_engine import adapter
    from camr_engine.models import READER_BIG

    repo = repo or READER_BIG
    rows, val = load_rows(data)
    rng = random.Random(f"train:{seed}")
    model, tok = load(repo)
    adapter.attach(model)
    adapter.switch(model, True)
    opt = optim.Adam(learning_rate=lr)

    def loss_fn(model, cache, inp, answer):
        logits = model(inp[None], cache=cache)[0, -answer.shape[0]:].astype(mx.float32)
        return nn.losses.cross_entropy(logits, answer).mean()

    loss_and_grad = nn.value_and_grad(model, loss_fn)
    t0, seen, running, log = time.time(), 0, None, []
    steps = len(rows) * epochs
    for ep in range(epochs):
        order = list(rows)
        rng.shuffle(order)
        for ex in order:
            context, qa, answer = ids_of(tok, ex)
            cache = read_context(model, context)
            adapter.switch(model, True)
            inp = mx.array(qa + answer[:-1])
            loss, grads = loss_and_grad(model, cache, inp, mx.array(answer))
            opt.update(model, grads)
            mx.eval(model.trainable_parameters(), opt.state, loss)
            seen += 1
            running = float(loss) if running is None else 0.95 * running + 0.05 * float(loss)
            if seen % 25 == 0 or seen == steps:
                el = time.time() - t0
                print(f"step {seen}/{steps}  loss {running:.3f}  {el / 60:.1f} min  ({el / seen:.2f} s/step)", flush=True)
                log.append({"step": seen, "loss": round(running, 4), "s": round(el, 1)})
    meta = {"name": name, "base": repo, "layers": adapter.LAYERS, "config": adapter.CONFIG, "lr": lr, "epochs": epochs,
            "examples": len(rows), "families": sorted({r["family"] for r in rows}),
            "worlds": sorted({r["world"] for r in rows}), "seeds": sorted({int(r["seed"]) for r in rows}),
            "held_back": list(VAL_WORLD_CUT), "on": "question and answer only; memory is read with it off",
            "made": time.strftime("%Y-%m-%d %H:%M"), "minutes": round((time.time() - t0) / 60, 1), "log": log,
            "data": str(Path(data).resolve())}
    folder = adapter.save(model, adapter.ADAPTERS / name, meta)
    print(f"saved {folder}")
    return folder


def check(data: Path, name: str, n: int = 120, repo: str | None = None) -> dict:
    """The plain model and the adapter on the same held-back examples (a world and cut never trained on)."""
    from mlx_lm import load, stream_generate

    from camr_engine import adapter
    from camr_engine.bench.haul.grade import grade
    from camr_engine.models import READER_BIG

    _, val = load_rows(data)
    val = val[:n]
    model, tok = load(repo or READER_BIG)
    meta = adapter.load(model, name)
    tally = {"plain": {}, "adapter": {}}
    rows = []
    for ex in val:
        context, qa, _ = ids_of(tok, ex)
        row = {"id": ex["id"], "family": ex["family"], "target": ex["target"]}
        for who, on in (("plain", False), ("adapter", True)):
            cache = read_context(model, context)
            adapter.switch(model, on)
            text = "".join(r.text for r in stream_generate(model, tok, qa, max_tokens=40, prompt_cache=cache)).strip()
            v = grade(ex["probe"], text).verdict
            row[who] = text
            row[who + "_verdict"] = v
            fam = tally[who].setdefault(ex["family"], [0, 0])
            fam[0] += v == "right"
            fam[1] += 1
        rows.append(row)
    for who in tally:
        total = sum(v[0] for v in tally[who].values()), sum(v[1] for v in tally[who].values())
        fams = ", ".join(f"{f} {r}/{t}" for f, (r, t) in sorted(tally[who].items()))
        print(f"{who:8s} {total[0]}/{total[1]}   {fams}")
    out = Path(meta["path"]) / "check.json"
    out.write_text(json.dumps({"tally": tally, "rows": rows}, indent=1))
    print(f"-> {out}")
    return tally


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("data")
    d.add_argument("--worlds", type=Path, nargs="+", required=True)
    d.add_argument("--out", type=Path, required=True)
    t = sub.add_parser("train")
    t.add_argument("--data", type=Path, required=True)
    t.add_argument("--name", required=True)
    t.add_argument("--lr", type=float, default=2e-5)
    t.add_argument("--epochs", type=int, default=1)
    c = sub.add_parser("check")
    c.add_argument("--data", type=Path, required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--n", type=int, default=120)
    a = ap.parse_args(argv)
    if a.cmd == "data":
        build_data(a.worlds, a.out)
    elif a.cmd == "train":
        train(a.data, a.name, lr=a.lr, epochs=a.epochs)
    else:
        check(a.data, a.name, a.n)


if __name__ == "__main__":
    main()
