"""Where each answer is lost: for every question at a cut, how high the moments that hold its answer rank among all
the moments a saved memory holds, by the engine's embeddings, by plain words (BM25) and by both (reciprocal rank
fusion), and whether they reach the room laid as notes or the closest moments re-read as words.

This splits "never found" from "found but misread" before any reading is changed. It needs the embedder only, not
the model, and never changes the memory.

    python -m camr_engine.bench.haul.recall --memory work/memories/dev-s2-4b/1M.nosync --haul work/haul/s2 --cut 1M
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Sequence

import numpy as np

WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
STOP = frozenset("a an and are as at be by do does did for from has have he her his how i in is it its me my of on "
                 "or our she that the their them they this to was we what when where which who whom will with you "
                 "your yours".split())
RRF_K = 60  # reciprocal rank fusion's constant
TOPS = (1, 4, 8, 16, 32, 64)
HOWS = ("dense", "bm25", "lines", "hop", "finder", "finder_nodense")
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def needed(probe: dict) -> list[int]:
    """The events an answer needs: the newest value for a changed fact, the asked one of two lookalikes, and every
    event for the rest (both hops, every rule of a sum or a function)."""
    if probe["family"] in ("changed", "lookalike") and probe.get("event") is not None:
        return [int(probe["event"])]
    return [int(e) for e in probe.get("events", [])]


def split_lines(texts: Sequence[str]) -> tuple[list[str], np.ndarray]:
    """Every moment cut into its lines and sentences, each with the moment it came from."""
    lines, owner = [], []
    for mid, t in enumerate(texts):
        for part in SENTENCE.split(t):
            if len(part.strip()) > 3:
                lines.append(part.strip())
                owner.append(mid)
    return lines, np.array(owner)


def by_moment(line_scores: np.ndarray, owner: np.ndarray, n: int) -> np.ndarray:
    """A moment's score is its best line's."""
    out = np.zeros(n, dtype=np.float32)
    np.maximum.at(out, owner, line_scores)
    return out


def words(text: str) -> list[str]:
    return [w for w in WORD.findall(text.lower()) if w not in STOP]


class BM25:
    """Okapi BM25 over the moments' words: rare words (names, plates, routes, prices) weigh most."""

    def __init__(self, texts: Sequence[str], k1: float = 1.2, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(words(t)) for t in texts]
        self.lens = np.array([sum(d.values()) for d in self.docs], dtype=np.float32)
        self.avg = float(self.lens.mean()) if len(self.lens) else 1.0
        self.post: dict[str, list[int]] = defaultdict(list)
        for i, d in enumerate(self.docs):
            for w in d:
                self.post[w].append(i)
        n = len(self.docs)
        self.idf = {w: math.log(1 + (n - len(p) + 0.5) / (len(p) + 0.5)) for w, p in self.post.items()}

    def scores(self, query: str) -> np.ndarray:
        out = np.zeros(len(self.docs), dtype=np.float32)
        for w in set(words(query)):
            for i in self.post.get(w, ()):
                tf = self.docs[i][w]
                out[i] += self.idf[w] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * self.lens[i] / self.avg))
        return out


def ranks(scores: np.ndarray) -> np.ndarray:
    """rank[i] = the place of moment i when sorted best first (0 = best)."""
    order = np.argsort(-scores, kind="stable")
    r = np.empty_like(order)
    r[order] = np.arange(len(order))
    return r


def fuse(*rank_lists: np.ndarray) -> np.ndarray:
    return sum(1.0 / (RRF_K + r + 1) for r in rank_lists)


def moment_of_event(events: list[dict]) -> dict[int, int]:
    """Event index -> moment id: the engine keeps one moment per event, in order, and none for a day line."""
    from camr_engine.bench.local import DAY_LINE
    from camr_engine.bench.longhaul import line

    out, mid = {}, 0
    for e in events:
        if DAY_LINE.match(line(e)):
            continue
        out[int(e["i"])] = mid
        mid += 1
    return out


def diagnose(memory: Path, haul: Path, cut: str, *, per_family: int = 10, seed: int = 0, embedder=None) -> dict:
    from camr_engine.bench.longhaul import CUTS, checkpoints

    folder = Path(memory) / "project" / "longhaul"
    index = json.loads((folder / "index.json").read_text())
    moments = index["moments"]
    vectors = np.load(folder / "vectors.npy").astype(np.float32)
    events, cps = checkpoints(Path(haul), {cut: CUTS[cut]}, per_family=per_family, seed=seed)
    to_mid = moment_of_event(events)
    texts = [m["text"] for m in moments]
    # the mapping is checked, not trusted: every gold moment's text holds its event's words
    bad = [i for i, mid in to_mid.items() if mid < len(texts) and events[i]["text"][:40] not in texts[mid]]
    if bad:
        raise ValueError(f"{len(bad)} events do not match their moments (first: event {bad[0]})")
    bm = BM25(texts)
    lines, line_mid = split_lines(texts)
    bl = BM25(lines)
    from camr_engine.finder import LineIndex

    finder = LineIndex(texts)
    room_of = np.array([m["room"] for m in moments])
    if embedder is None:
        from camr_engine.bench.local import Loader

        embedder = Loader().embedder()
    rows = []
    for q in cps[0]["questions"]:
        p = q["probe"]
        gold = sorted({to_mid[e] for e in needed(p) if e in to_mid and to_mid[e] < len(texts)})
        qv = embedder.encode_one(q["question"], is_query=True)
        dense = ranks(vectors @ qv)
        lex = ranks(bm.scores(q["question"]))
        both = ranks(fuse(dense, lex))
        ls = by_moment(bl.scores(q["question"]), line_mid, len(texts))
        lline = ranks(ls)
        # a second lookup: the best lines found so far, their words added to the question (the bridge of a two-hop)
        top_lines = np.argsort(-bl.scores(q["question"]))[:2]
        q2 = q["question"] + " " + " ".join(lines[int(i)] for i in top_lines)
        hop = ranks(fuse(lline, ranks(by_moment(bl.scores(q2), line_mid, len(texts)))))
        mix = ranks(fuse(lline, lline, dense))
        from camr_engine.finder import ranks as frank
        fo = finder.order(q["question"], vectors @ qv)
        fnd = frank(-np.arange(len(fo), dtype=np.float32)[np.argsort(fo)])
        fo2 = finder.order(q["question"], None)
        fnd2 = frank(-np.arange(len(fo2), dtype=np.float32)[np.argsort(fo2)])
        top = int(np.argmax(vectors @ qv))
        row = {"id": q["id"], "family": q["family"], "question": q["question"], "gold": gold,
               "dense": [int(dense[g]) for g in gold], "bm25": [int(lex[g]) for g in gold],
               "fused": [int(both[g]) for g in gold], "lines": [int(lline[g]) for g in gold],
               "hop": [int(hop[g]) for g in gold], "mix": [int(mix[g]) for g in gold],
               "finder": [int(fnd[g]) for g in gold], "finder_nodense": [int(fnd2[g]) for g in gold],
               "in_room": [bool(room_of[g] == room_of[top]) for g in gold]}
        rows.append(row)
    return {"memory": str(memory), "haul": str(haul), "cut": cut, "moments": len(texts), "rows": rows,
            "summary": summarize(rows)}


def summarize(rows: list[dict]) -> dict:
    """Per family and in all: the share of questions whose gold moments ALL rank within the top N (a two-hop question
    needs both), by each ranking; and how many have no gold moment at all (never-told questions)."""
    out: dict[str, dict] = {}
    groups = defaultdict(list)
    for r in rows:
        groups[r["family"]].append(r)
        groups["all"].append(r)
    for fam, rs in groups.items():
        asked = [r for r in rs if r["gold"]]
        s = {"questions": len(rs), "with_gold": len(asked)}
        for how in HOWS:
            s[how] = {f"@{n}": sum(1 for r in asked if max(r[how]) < n) for n in TOPS}
        s["in_room"] = sum(1 for r in asked if all(r["in_room"]))
        out[fam] = s
    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m camr_engine.bench.haul.recall")
    ap.add_argument("--memory", type=Path, required=True)
    ap.add_argument("--haul", type=Path, required=True)
    ap.add_argument("--cut", required=True)
    ap.add_argument("--per-family", type=int, default=10)
    ap.add_argument("--sample-seed", type=int, default=0)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    d = diagnose(a.memory, a.haul, a.cut, per_family=a.per_family, seed=a.sample_seed)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(d, indent=1))
    print(f"{d['moments']} moments")
    for fam, s in d["summary"].items():
        print(f"{fam:10s} n={s['with_gold']:3d} " + "  ".join(
            f"{how}: " + " ".join(f"{k}={v}" for k, v in s[how].items() if k in ("@4", "@8", "@16")) for how in HOWS)
            + f"  in_room={s['in_room']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
