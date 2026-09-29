"""Answer scoring (FR-12) with one normalisation shared by every condition.

* ``em`` / ``f1``: SQuAD-style normalisation, max over gold aliases.
* ``contains``: a gold alias appears in the normalised answer; the accuracy
  measure PopQA was introduced with (Mallen et al., 2023), which is robust to
  small models' habit of answering in a sentence.
* ``accuracy`` (GSM8K): the final number in the output equals the gold number.

The raw generation is logged; scoring reads only ``extract_answer`` of it, and
applies the same extraction to every condition so no condition is favoured.
"""

from __future__ import annotations

import re
import string
from collections import Counter
from fractions import Fraction

_ARTICLES = re.compile(r"\b(a|an|the)\b", re.UNICODE)
_PUNCT = set(string.punctuation)
_LEAD = re.compile(r"^\s*(final answer|answer|a)\s*[:\-]\s*", re.IGNORECASE)


def normalize_answer(s: str) -> str:
    s = s.lower()
    s = "".join(ch for ch in s if ch not in _PUNCT)
    s = _ARTICLES.sub(" ", s)
    return " ".join(s.split())


def extract_answer(generation: str) -> str:
    """First non-empty line, minus an 'Answer:' lead-in."""
    for line in generation.strip().splitlines():
        line = _LEAD.sub("", line).strip()
        if line:
            return line
    return ""


def exact_match(pred: str, golds: list[str]) -> float:
    p = normalize_answer(pred)
    return float(any(p == normalize_answer(g) for g in golds))


def f1(pred: str, golds: list[str]) -> float:
    best = 0.0
    p_toks = normalize_answer(pred).split()
    for g in golds:
        g_toks = normalize_answer(g).split()
        if not p_toks or not g_toks:
            best = max(best, float(p_toks == g_toks))
            continue
        common = Counter(p_toks) & Counter(g_toks)
        same = sum(common.values())
        if same == 0:
            continue
        prec, rec = same / len(p_toks), same / len(g_toks)
        best = max(best, 2 * prec * rec / (prec + rec))
    return best


def contains(pred: str, golds: list[str]) -> float:
    p = f" {normalize_answer(pred)} "
    return float(any(normalize_answer(g) and f" {normalize_answer(g)} " in p for g in golds))


_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?(?:/\d+)?")


def parse_number(s: str) -> Fraction | None:
    s = s.replace(",", "").replace("$", "").strip()
    try:
        return Fraction(s)
    except (ValueError, ZeroDivisionError):
        return None


def final_number(text: str) -> Fraction | None:
    if "####" in text:
        text = text.rsplit("####", 1)[1]
    nums = _NUM.findall(text)
    return parse_number(nums[-1]) if nums else None


def math_accuracy(generation: str, gold: str) -> float:
    g = final_number(gold)
    p = final_number(generation)
    return float(g is not None and p is not None and g == p)


def score(task_type: str, generation: str, golds: list[str]) -> dict[str, float]:
    if task_type == "reasoning":
        return {"accuracy": math_accuracy(generation, golds[0])}
    pred = extract_answer(generation)
    return {"em": exact_match(pred, golds), "f1": f1(pred, golds), "contains": contains(generation, golds)}
