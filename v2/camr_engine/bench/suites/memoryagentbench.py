"""MemoryAgentBench (Hu et al., 2025): one long context fed in chunks, then many questions on it.

Two of its four splits are here:
  Conflict_Resolution  FactConsolidation: numbered facts, some later ones overriding earlier ones (the larger number
                       wins); single-hop and multi-hop, at 6k, 32k, 64k and 262k tokens. 8 contexts x 100 questions.
  Accurate_Retrieval   RULER QA (SQuAD and HotpotQA documents, 197K and 421K) and EventQA (what happens next in a
                       novel, at 65K, 131K and the full book). 17 contexts x 100 questions. Its 5 LongMemEval rows
                       are left out by default: suite "longmemeval" asks those questions with a judge.

Contexts are cut into chunks of about 4,096 tokens at sentence ends, as the benchmark feeds them. A reply is right
when it equals an accepted answer after the benchmark's normalising (lowercase, no punctuation or articles), whole
or after "Answer:". ``scores`` also gives the benchmark's substring match, which its paper reports for some tasks.
"""

from __future__ import annotations

import re
import string
from collections import defaultdict
from typing import Any

from camr_engine.bench.suites.common import Item, chunk, clean, estimate_tokens, hub_file, rng, verdict

NAME = "memoryagentbench"
REPO = "ai-hyz/MemoryAgentBench"
REVISION = "7ea066982b140a19337e17e60d45d4076e042faf"
SPLITS = ("Conflict_Resolution", "Accurate_Retrieval")
SHORT = {"Conflict_Resolution": "cr", "Accurate_Retrieval": "ar"}
SKIP = ("longmemeval",)
CHUNK_TOKENS = 4096

INSTRUCTIONS = {
    "factconsolidation": ("The memory holds numbered facts; a larger number is newer, and a newer fact overrides an "
                          "older one. Answer from those facts only, not from what you know of the world, in as few "
                          "words as you can."),
    "ruler_qa": "Answer the question from the documents in memory. Give only the answer, no other words.",
    "eventqa": ("The memory holds a book excerpt. Choose which of the listed events happens next. Give only that "
                "event, word for word."),
}


def _kind(source: str) -> str:
    for k in INSTRUCTIONS:
        if source.startswith(k):
            return k
    return "ruler_qa"


def _file(split: str) -> str:
    return f"data/{split}-00000-of-00001.parquet"


def load(splits: tuple[str, ...] = SPLITS, *, skip: tuple[str, ...] = SKIP, chunk_tokens: int = CHUNK_TOKENS,
         paths: dict[str, Any] | None = None) -> list[Item]:
    """One item per question. The questions on one context share one list of chunks."""
    import pyarrow.parquet as pq

    out = []
    for split in splits:
        p = (paths or {}).get(split) or hub_file(REPO, _file(split), REVISION, "memoryagentbench")
        table = pq.read_table(p, columns=["context", "questions", "answers", "metadata"])
        for row_no, row in enumerate(table.to_pylist()):
            md = row["metadata"] or {}
            source = md.get("source") or ""
            if any(source.startswith(s) for s in skip):
                continue
            pieces = chunk(row["context"], chunk_tokens)
            size = estimate_tokens(row["context"])
            kind = _kind(source)
            pair_ids = md.get("qa_pair_ids") or []
            for q_no, (q, answers) in enumerate(zip(row["questions"], row["answers"])):
                accepted = list(dict.fromkeys(a for a in answers if a and a.strip()))
                out.append(Item(id=f"mab/{SHORT[split]}/{row_no:02d}/{q_no:03d}", suite=NAME, context=pieces,
                                question=q, answer=accepted, length_tokens=size,
                                meta={"split": split, "source": source, "kind": kind, "row": row_no,
                                      "qa_pair_id": pair_ids[q_no] if q_no < len(pair_ids) else None,
                                      "instruction": INSTRUCTIONS[kind]}))
    return out


def sample(n: int, seed: int = 0, splits: tuple[str, ...] = SPLITS, **kw: Any) -> list[Item]:
    """``n`` questions per context, chosen by the seed."""
    by_row: dict[tuple[str, int], list[Item]] = defaultdict(list)
    for it in load(splits, **kw):
        by_row[(it.meta["split"], it.meta["row"])].append(it)
    out = []
    for key, items in by_row.items():
        picks = sorted(rng(seed, NAME, *key).sample(range(len(items)), min(n, len(items))))
        out += [items[k] for k in picks]
    return out


def prompt(item: Item) -> str:
    return f"{item.meta['instruction']}\n\nQuestion: {item.question}\nAnswer:"


def normalize(text: str) -> str:
    """The benchmark's normalising: lowercase, no punctuation, no articles, single spaces."""
    t = "".join(c for c in text.lower() if c not in string.punctuation)
    t = re.sub(r"\b(a|an|the)\b", " ", t)
    return " ".join(t.split())


def parsed(reply: str) -> str:
    """What follows "Answer:", else the first line (as the benchmark parses a reply)."""
    m = re.search(r"answer:(.*)(?:\n|$)", reply, re.I)
    line = m.group(1) if m else reply.strip().split("\n")[0]
    return re.sub(r"^answer:", "", line.strip(), flags=re.I).strip()


def scores(item: Item, reply: str) -> dict[str, bool]:
    """Exact match and substring match, each the best over the accepted answers and over the whole and parsed reply."""
    text = clean(reply)
    forms = {normalize(text), normalize(parsed(text))}
    golds = [normalize(a) for a in item.answers]
    em = any(g == f for g in golds for f in forms)
    sub = any(g and g in f for g in golds for f in forms)
    return {"exact_match": em, "substring_match": sub}


def grade(item: Item, reply: str, **_: Any) -> str:
    return verdict(scores(item, reply)["exact_match"], clean(reply))
