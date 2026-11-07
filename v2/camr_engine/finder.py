"""Finding the moments a question is about, by their words as well as their meaning.

A moment is often a whole meeting note or a pasted group chat: ten topics in one message. One embedding for all of
it blurs the one line a question needs, so the engine's embeddings alone put the moment holding the answer in the
closest 8 for 21 of 63 told questions on a development memory (seed 2, 1M tokens); words, scored line by line
(BM25, rare words such as names, plates, routes and prices weighing most), put it there for 45
(camr_engine.bench.haul.recall; DECISIONS.md, E-63).

``LineIndex`` keeps every moment's lines and sentences, each tied to its moment, and grows as moments are kept; it is
built from the moments' own texts, so it needs no file of its own. ``order`` ranks every moment for a question:
its best line by words, a second look with the best lines' words added (the bridge of a two-hop question:
"Kevin handles payroll" -> "whoever handles payroll gets extension 214"), and the embeddings, fused by reciprocal
rank.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Iterable, Sequence

import numpy as np

WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
STOP = frozenset("a an and are as at be by do does did for from has have he her his how i in is it its me my of on "
                 "or our she that the their them they this to was we what when where which who whom will with you "
                 "your yours".split())
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
STAMP = re.compile(r"^\[[^\]]*\]\s*(?:User|Assistant):\s*")  # "[2025-09-22, day 1] User: " leads every moment
RRF_K = 60
HOP_LINES = 1  # the best lines whose new words a second look searches for
HOP_WEIGHT = 0.75  # the second look counts three quarters as much as the first
DENSE_WEIGHT = 0.5  # and so do the embeddings
K1, B = 1.2, 0.75
FINDERS = ("dense", "words")
# a request that names what it needs only by kind: the words its notes are written in, added to the first look.
# A page or screen to build is made in the site's design system, which no such request names.
HINTS = ((re.compile(r"\b(build|make|create|design|write)\b.*\b(page|site|screen|landing|homepage|layout)\b", re.I),
          "design system main colour colours font fonts style buttons nav"),)


def hinted(question: str) -> str:
    extra = [words for pattern, words in HINTS if pattern.search(question)]
    return question + (" " + " ".join(extra) if extra else "")


def words(text: str) -> list[str]:
    """A text's words for matching: lower case, a possessive's 's dropped (Njoroge's finds Njoroge), stop words out."""
    out = []
    for w in WORD.findall(text.lower().replace("’", "'")):
        w = w.removesuffix("'s")
        if w not in STOP:
            out.append(w)
    return out


def lines_of(text: str) -> list[str]:
    return [p.strip() for p in SENTENCE.split(STAMP.sub("", text)) if len(p.strip()) > 3]


def ranks(scores: np.ndarray) -> np.ndarray:
    """rank[i] = moment i's place, best first (0 = best)."""
    order = np.argsort(-scores, kind="stable")
    r = np.empty_like(order)
    r[order] = np.arange(len(order))
    return r


class LineIndex:
    """BM25 over every moment's lines, kept up to date as moments are added. A moment scores as its best line."""

    def __init__(self, texts: Iterable[str] = ()):
        self.lines: list[str] = []
        self.owner: list[int] = []  # line -> moment
        self.lens: list[int] = []
        self.post: dict[str, list[tuple[int, int]]] = defaultdict(list)  # word -> [(line, count)]
        self._arrays: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self._owner: np.ndarray | None = None
        self.moments = 0
        for t in texts:
            self.add(t)

    def add(self, text: str) -> None:
        mid = self.moments
        self.moments += 1
        for line in lines_of(text):
            lid = len(self.lines)
            ws = words(line)
            self.lines.append(line)
            self.owner.append(mid)
            self.lens.append(len(ws))
            counts: dict[str, int] = defaultdict(int)
            for w in ws:
                counts[w] += 1
            for w, c in counts.items():
                self.post[w].append((lid, c))
                self._arrays.pop(w, None)
        self._owner = None

    def _posting(self, w: str) -> tuple[np.ndarray, np.ndarray]:
        got = self._arrays.get(w)
        if got is None:
            p = self.post.get(w, [])
            got = (np.fromiter((x[0] for x in p), dtype=np.int64, count=len(p)),
                   np.fromiter((x[1] for x in p), dtype=np.float32, count=len(p)))
            self._arrays[w] = got
        return got

    def line_scores(self, query: str) -> np.ndarray:
        n = len(self.lines)
        out = np.zeros(n, dtype=np.float32)
        if not n:
            return out
        lens = np.asarray(self.lens, dtype=np.float32) if getattr(self, "_lens_n", -1) != n else self._lens
        self._lens, self._lens_n = lens, n
        avg = float(lens.mean()) or 1.0
        for w in set(words(query)):
            lid, tf = self._posting(w)
            if not len(lid):
                continue
            idf = math.log(1 + (n - len(lid) + 0.5) / (len(lid) + 0.5))
            out[lid] += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * lens[lid] / avg))
        return out

    def moment_scores(self, line_scores: np.ndarray) -> np.ndarray:
        if self._owner is None or len(self._owner) != len(self.owner):
            self._owner = np.asarray(self.owner, dtype=np.int64)
        out = np.zeros(self.moments, dtype=np.float32)
        if len(line_scores):
            np.maximum.at(out, self._owner, line_scores)
        return out

    def order(self, question: str, dense: np.ndarray | None = None, *, hop: bool = True) -> np.ndarray:
        """Every moment, best first, for ``question``: its words line by line, a second look with the best lines'
        words, and ``dense`` (the embeddings' closeness, one per moment) when given, fused by reciprocal rank."""
        ls = self.line_scores(hinted(question))
        parts = [(1.0, ranks(self.moment_scores(ls)))]
        if hop and len(ls):
            # the second look searches for what the best lines add (the bridge), not for the question again, and
            # counts half: it must not undo a first look that already found an exact name
            asked = set(words(question))
            best = np.argsort(-ls)[:HOP_LINES]
            bridge = {w for i in best if ls[int(i)] > 0 for w in words(self.lines[int(i)])} - asked
            if bridge:
                parts.append((HOP_WEIGHT, ranks(self.moment_scores(self.line_scores(" ".join(sorted(bridge)))))))
        if dense is not None and len(dense) == self.moments:
            parts.append((DENSE_WEIGHT, ranks(dense)))
        fused = sum(w / (RRF_K + r + 1) for w, r in parts)
        return np.argsort(-fused, kind="stable")


def best_lines(index: LineIndex, question: str, mids: Sequence[int], per: int = 3) -> dict[int, list[str]]:
    """For each moment in ``mids``, its ``per`` lines that best match the question, in their own order."""
    ls = index.line_scores(question)
    out: dict[int, list[str]] = {}
    owner = np.asarray(index.owner)
    for m in mids:
        ids = np.nonzero(owner == m)[0]
        top = sorted(ids[np.argsort(-ls[ids])[:per]].tolist())
        out[int(m)] = [index.lines[i] for i in top]
    return out
