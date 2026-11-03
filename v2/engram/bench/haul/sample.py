"""Probes at a cut: which can be asked after the first N tokens, with the answer right at that point, and a
stratified sample of them.

A changed fact asked "now" at the 256K cut has the value of day 14, not of day 110; the page asked at the 1M cut
still has the old main colour, because the change on day 61 is not inside it yet.
"""

from __future__ import annotations

import copy
import random

from engram.bench.haul.grade import resolve_timeline


def at_cut(p: dict, cut: int) -> dict | None:
    """``p`` as asked after the first ``cut`` tokens, or None if something it needs is not inside them."""
    g = p["grader"]
    if g["type"] == "never":
        return dict(copy.deepcopy(p), cut=cut)
    if g["type"] == "timeline":
        exact = resolve_timeline(g, cut)
        if exact is None:
            return None
        q = copy.deepcopy(p)
        seen = [v for v in g["values"] if v["tokens"] <= cut]
        if g["on_day"] is None:
            right = seen[-1]
        else:
            right = [v for v in seen if v["day"] <= g["on_day"]][-1]
        q.update(grader=exact, answer=right["value"], event=right["event"], planted_at=right["tokens"],
                 planted_day=right["day"], events=[v["event"] for v in seen], cut=cut,
                 ready_at=max([right["tokens"]] + ([g["day_over_at"]] if g["on_day"] is not None else
                                                    [seen[-1]["tokens"]])))
        return q
    if g["type"] == "page":
        seen = [v for v in g["timeline"] if v["tokens"] <= cut]
        if not seen:
            return None
        q = copy.deepcopy(p)
        q["grader"] = dict(q["grader"], colour=seen[-1]["value"], old=[v["value"] for v in seen[:-1]])
        q.update(answer=f"an HTML page in the design system, main colour {seen[-1]['value']}", event=seen[-1]["event"],
                 planted_at=seen[-1]["tokens"], planted_day=seen[-1]["day"], cut=cut)
        return q
    if p["ready_at"] is None or p["ready_at"] > cut:
        return None
    return dict(copy.deepcopy(p), cut=cut)


def askable(probes: list[dict], cut: int) -> list[dict]:
    return [q for q in (at_cut(p, cut) for p in probes) if q is not None]


def sample(probes: list[dict], cut: int, n: int, per_family: bool = False, seed: int = 0,
           samples_first: bool = True) -> list[dict]:
    """A stratified sample of the probes askable at ``cut``: ``n`` from each family (``per_family``), or ``n`` in
    all spread across the families as evenly as they allow. The doc's sample probes come first when askable."""
    rng = random.Random(f"sample:{seed}:{cut}:{n}:{per_family}")
    pool = askable(probes, cut)
    fams: dict[str, list[dict]] = {}
    for q in pool:
        fams.setdefault(q["family"], []).append(q)
    for fam, qs in fams.items():
        rng.shuffle(qs)
        if samples_first:
            qs.sort(key=lambda q: not q.get("sample"))
    if per_family:
        return [q for qs in fams.values() for q in qs[:n]]
    out: list[dict] = []
    while len(out) < n and any(fams.values()):
        for qs in fams.values():
            if qs and len(out) < n:
                out.append(qs.pop(0))
    return out
