"""Ten memory abilities (A1-A10): what a question needs from memory, and whether the read path delivered it.

Model-free. A question is scored from what the engine put into the context, not from a model's answer, so the
score is about memory alone. Every candidate note the read path ranked is handed in with the keys of the facts its
text came from (empty for filler), its tokens, its similarity and whether it was eligible and admitted; nothing
here touches the engine (camr.eval may not import camr.memory).

A question's ``needed`` facts are groups: a group is met when any one of its keys reaches the context (a fact
told in several turns of one session needs only one of them). The rule says what passing means:

* ``all``      every needed group reached the context (A1, A2, A5, A6);
* ``newest``   the newest value reached the context and, if a superseded value is there too, the two can be told
               apart: both carry dates and the newest is later, or the newest says it is an update (A3);
* ``temporal`` every needed group reached the context in a note that shows its date, and no note from outside the
               period asked about did: CAMR Personal's prompt does not tell the model today's date, so the model
               cannot drop those itself (A4);
* ``abstain``  memory abstained (A7);
* ``no_harm``  nothing was admitted: a question memory has nothing for gets an empty context (A10).
"""

from __future__ import annotations

import datetime as dt
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

ABILITIES = {
    "A1": "recall one taught fact among many",
    "A2": "join two facts",
    "A3": "knowledge update",
    "A4": "temporal",
    "A5": "counting",
    "A6": "implicit preference",
    "A7": "abstention",
    "A8": "forget and privacy",
    "A9": "scale",
    "A10": "do no harm (engine proxy)",
}
RULES = ("all", "newest", "temporal", "abstain", "no_harm")
ANSWERABLE = ("all", "newest", "temporal")  # rules of questions memory holds the answer to

# LongMemEval question types -> ability (abstention questions, ids ending "_abs", are A7 whatever their type)
LME_ABILITY = {"single-session-user": "A1", "single-session-assistant": "A1", "multi-session": "A2",
               "knowledge-update": "A3", "temporal-reasoning": "A4", "single-session-preference": "A6"}
LME_SUITE = {"single-session-user": "lme-ssu", "single-session-assistant": "lme-ssa", "multi-session": "lme-ms",
             "knowledge-update": "lme-ku", "temporal-reasoning": "lme-tr", "single-session-preference": "lme-ssp"}


@dataclass(frozen=True)
class Cand:
    """One note the read path ranked for a question."""

    keys: frozenset[str]  # facts this note's text came from; empty = filler
    tokens: int
    text: str = ""
    similarity: float = 0.0
    rank: int = 0
    eligible: bool = True
    admitted: bool = False
    via_bridge: bool = False


@dataclass
class Spec:
    qid: str
    ability: str
    suite: str
    question: str
    needed: list[frozenset[str]] = field(default_factory=list)
    stale: frozenset[str] = frozenset()          # A3: superseded values of the fact asked about
    out_of_window: frozenset[str] = frozenset()  # A4: same topic, outside the period asked about
    rule: str = "all"
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.rule not in RULES:
            raise ValueError(f"unknown rule {self.rule!r}")
        self.needed = [frozenset(g) for g in self.needed if g]
        self.stale, self.out_of_window = frozenset(self.stale), frozenset(self.out_of_window)


# ---------------------------------------------------------------------- dates and update cues
_ISO = re.compile(r"\b(\d{4})[-/](\d{2})[-/](\d{2})\b")
_MONTHS = ("january|february|march|april|may|june|july|august|september|october|november|december|"
           "jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec")
_NAMED = re.compile(rf"\b(?:\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})\b|(?:{_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?\b)",
                    re.I)
_UPDATE = re.compile(r"\b(?:update[sd]?|updating|moved|changed|switched|no longer|any ?more|instead|now|"
                     r"replaced|new address|new number)\b", re.I)


def iso_dates(text: str) -> list[dt.date]:
    out = []
    for y, m, d in _ISO.findall(text):
        try:
            out.append(dt.date(int(y), int(m), int(d)))
        except ValueError:
            pass
    return out


def has_date(text: str) -> bool:
    """The note shows when it happened (an ISO date, or a day and month in words)."""
    return bool(iso_dates(text)) or bool(_NAMED.search(text))


def update_cue(text: str) -> bool:
    return bool(_UPDATE.search(text))


def tell_apart(newest: Sequence[Cand], stale: Sequence[Cand]) -> bool:
    """Can a reader of the context tell the newest value from a superseded one next to it?"""
    new_d = [d for c in newest for d in iso_dates(c.text)]
    old_d = [d for c in stale for d in iso_dates(c.text)]
    if new_d and old_d and max(new_d) > max(old_d):
        return True
    return any(update_cue(c.text) for c in newest)


# ---------------------------------------------------------------------- one question
def miss_reason(group: frozenset[str], cands: Sequence[Cand], *, abstained: bool, top_similarity: float | None,
                min_similarity: float) -> str:
    """Why a needed fact did not reach the context: where its best note was lost on the read path."""
    mine = [c for c in cands if c.keys & group]
    if not mine:
        return "not retrieved"  # outside the top-k vector hits and the keyword hits
    best = min(mine, key=lambda c: c.rank or 10**9)
    if abstained:
        gated = top_similarity is None or top_similarity < min_similarity
        return "similarity gate" if gated else "entity gate"
    if not best.eligible:
        return "below margin"
    return "budget full"


def score(spec: Spec, cands: Sequence[Cand], *, abstained: bool, retrieval_ms: float,
          top_similarity: float | None = None, min_similarity: float = 0.0) -> dict:
    """Score one question from the ranked candidates (those with ``admitted`` set form the context)."""
    adm = [c for c in cands if c.admitted]
    relevant = frozenset().union(*spec.needed) if spec.needed else frozenset()
    reached = [any(c.keys & g for c in adm) for g in spec.needed]
    tokens = sum(c.tokens for c in adm)
    distract = sum(c.tokens for c in adm if not (c.keys & relevant))
    stale_in = any(c.keys & spec.stale for c in adm)
    first_new = next((i for i, c in enumerate(adm) if spec.needed and c.keys & spec.needed[0]), None)
    stale_first = stale_in and (first_new is None or any(c.keys & spec.stale for c in adm[:first_new]))
    oow_in = any(c.keys & spec.out_of_window for c in adm)
    if spec.rule == "all":
        passed = bool(reached) and all(reached)
    elif spec.rule == "newest":
        newest = [c for c in adm if c.keys & spec.needed[0]] if spec.needed else []
        stale = [c for c in adm if c.keys & spec.stale]
        passed = bool(newest) and (not stale or tell_apart(newest, stale))
    elif spec.rule == "temporal":
        dated = [any((c.keys & g) and has_date(c.text) for c in adm) for g in spec.needed]
        passed = bool(dated) and all(dated) and not oow_in
    elif spec.rule == "abstain":
        passed = abstained
    else:  # no_harm
        passed = tokens == 0
    misses = [miss_reason(g, cands, abstained=abstained, top_similarity=top_similarity,
                          min_similarity=min_similarity) for g, r in zip(spec.needed, reached) if not r]
    return {
        "qid": spec.qid, "ability": spec.ability, "suite": spec.suite, "rule": spec.rule,
        "question": spec.question, "passed": bool(passed),
        "needed": len(spec.needed), "reached": sum(reached),
        "all_needed": (all(reached) if spec.needed else None),
        "distractor_share": round(distract / tokens, 4) if tokens else 0.0,
        "context_tokens": tokens, "admitted": len(adm),
        "retrieval_ms": round(float(retrieval_ms), 2), "abstained": bool(abstained),
        "top_similarity": None if top_similarity is None else round(float(top_similarity), 4),
        "stale_in_context": stale_in, "stale_first": stale_first, "out_of_window_in_context": oow_in,
        "misses": misses, **({"meta": spec.meta} if spec.meta else {}),
    }


# ---------------------------------------------------------------------- LongMemEval
def lme_date(stamp: str) -> str:
    """LongMemEval's "2023/05/20 (Sat) 02:21" -> "2023-05-20"."""
    m = _ISO.search(stamp)
    if not m:
        raise ValueError(f"no date in {stamp!r}")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def turn_key(session_id: str, turn: int) -> str:
    return f"{session_id}#{turn}"


def lme_spec(item: dict) -> Spec:
    """Needed facts of a LongMemEval question: per evidence session (``answer_session_ids``), its turns flagged
    ``has_answer`` (all of its turns when none is flagged). Knowledge updates need the newest session's turns, and
    the older sessions' are superseded values."""
    qtype, qid = item["question_type"], item["question_id"]
    sessions = dict(zip(item["haystack_session_ids"], item["haystack_sessions"]))
    dates = dict(zip(item["haystack_session_ids"], item["haystack_dates"]))
    groups: dict[str, frozenset[str]] = {}
    unflagged = 0
    for sid in item["answer_session_ids"]:
        turns = sessions.get(sid)
        if turns is None:
            continue
        flagged = [i for i, t in enumerate(turns) if t.get("has_answer")]
        if not flagged:
            unflagged += 1
            flagged = list(range(len(turns)))
        groups[sid] = frozenset(turn_key(sid, i) for i in flagged)
    meta = {"type": qtype, "answer": str(item.get("answer", ""))[:200], "evidence_sessions": len(groups),
            "unflagged_sessions": unflagged}
    if qid.endswith("_abs"):
        return Spec(qid, "A7", "lme-abs", item["question"], rule="abstain", meta=meta)
    ability, suite = LME_ABILITY[qtype], LME_SUITE[qtype]
    if qtype == "knowledge-update" and groups:
        newest = max(groups, key=lambda s: (dates.get(s, ""), s))
        stale = frozenset().union(*(g for s, g in groups.items() if s != newest))
        return Spec(qid, ability, suite, item["question"], needed=[groups[newest]], stale=stale, rule="newest",
                    meta=meta)
    rule = "temporal" if qtype == "temporal-reasoning" else "all"
    return Spec(qid, ability, suite, item["question"], needed=list(groups.values()), rule=rule, meta=meta)


def stratified_sample(items: Sequence[dict], key: Callable[[dict], str], per_group: int | None,
                      seed: int) -> list[dict]:
    """At most ``per_group`` items of each group, drawn with a fixed seed; order is the input order."""
    groups: dict[str, list[int]] = defaultdict(list)
    for i, it in enumerate(items):
        groups[key(it)].append(i)
    rng = random.Random(seed)
    keep: set[int] = set()
    for g in sorted(groups):
        idx = groups[g]
        keep |= set(idx if per_group is None or len(idx) <= per_group else rng.sample(idx, per_group))
    return [it for i, it in enumerate(items) if i in keep]


# ---------------------------------------------------------------------- summaries
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson interval of a pass rate (None when there is nothing to rate)."""
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return round(max(0.0, mid - half), 4), round(min(1.0, mid + half), 4)


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return round(s[min(len(s) - 1, max(0, math.ceil(q * len(s)) - 1))], 2)


def summarise(records: Iterable[dict]) -> dict:
    """Pass rate and read-path numbers of a set of question records."""
    rs = list(records)
    n = len(rs)
    k = sum(1 for r in rs if r.get("passed"))
    need = [r for r in rs if r.get("all_needed") is not None]
    ms = [r["retrieval_ms"] for r in rs if r.get("retrieval_ms") is not None]
    toks = [r["context_tokens"] for r in rs if r.get("context_tokens") is not None]
    dshare = [r["distractor_share"] for r in rs if r.get("distractor_share") is not None]
    asked = [r for r in rs if r.get("abstained") is not None]  # question records (not A8 checks or A9 sizes)
    out = {
        "n": n, "passed": k, "pass_rate": round(k / n, 4) if n else None, "ci95": wilson(k, n),
        "all_needed_recall": round(sum(r["all_needed"] for r in need) / len(need), 4) if need else None,
        "distractor_share": round(statistics.fmean(dshare), 4) if dshare else None,
        "context_tokens": round(statistics.fmean(toks), 1) if toks else None,
        "retrieval_ms_median": _pct(ms, 0.5), "retrieval_ms_p95": _pct(ms, 0.95),
        "abstain_rate": round(sum(1 for r in asked if r["abstained"]) / len(asked), 4) if asked else None,
    }
    misses = Counter(m for r in rs for m in r.get("misses", []))
    if misses:
        out["misses"] = dict(misses.most_common())
    return out


def gate_precision(records: Iterable[dict]) -> dict:
    """How well the gate opens only when memory holds something: over answerable questions (memory has the fact)
    and unanswerable ones (abstention and no-harm questions), precision = answerable among questions the gate let
    memory through for; specificity = share of unanswerable questions it kept closed."""
    rs = [r for r in records if r.get("rule") in RULES]
    pos = [r for r in rs if r["rule"] in ANSWERABLE]
    neg = [r for r in rs if r["rule"] not in ANSWERABLE]
    tp = sum(1 for r in pos if not r.get("abstained"))
    fp = sum(1 for r in neg if not r.get("abstained"))
    return {"answerable": len(pos), "unanswerable": len(neg), "opened_answerable": tp, "opened_unanswerable": fp,
            "precision": round(tp / (tp + fp), 4) if tp + fp else None,
            "specificity": round(1 - fp / len(neg), 4) if neg else None,
            "sensitivity": round(tp / len(pos), 4) if pos else None}


def scorecard(records: Iterable[dict]) -> dict:
    """Per ability: the summary over all its question records, and one per suite."""
    rs = [r for r in records if r.get("ability") in ABILITIES]
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rs:
        by[r["ability"]].append(r)
    out = {}
    for ab in ABILITIES:
        group = by.get(ab, [])
        if ab == "A10":  # do no harm: every question memory has nothing for, A7's included
            group = group + by.get("A7", [])
        suites: dict[str, list[dict]] = defaultdict(list)
        for r in group:
            suites[("A7 " if ab != r["ability"] else "") + r.get("suite", "?")].append(r)
        out[ab] = {"name": ABILITIES[ab], **summarise(group),
                   "suites": {s: summarise(v) for s, v in sorted(suites.items())}}
    out["A10"]["gate"] = gate_precision(rs)
    return out
