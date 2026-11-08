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
    """rank[i] = moment i's place, best first (0 = best); equal scores keep their own order."""
    order = np.argsort(-scores, kind="stable")
    r = np.empty_like(order)
    r[order] = np.arange(len(order))
    return r


def sparse_ranks(scores: np.ndarray) -> np.ndarray:
    """``ranks`` for scores that are never below zero and mostly zero (words found in few lines): only the scored
    ones are sorted; every zero takes the next place in its own order, exactly as the full sort puts them."""
    hit = scores > 0
    pos = np.flatnonzero(hit)
    r = np.empty(len(scores), dtype=np.int64)
    r[pos[np.argsort(-scores[pos], kind="stable")]] = np.arange(len(pos))
    zero = ~hit
    before = np.cumsum(hit)  # scored ones up to and including each place
    r[zero] = len(pos) + np.flatnonzero(zero) - before[zero]
    return r


def top(scores: np.ndarray, n: int) -> np.ndarray:
    """The ``n`` best places, best first, equal scores in their own order: the head of a stable full sort, without
    sorting the rest."""
    if n >= len(scores):
        return np.argsort(-scores, kind="stable")
    cut = np.partition(scores, len(scores) - n)[len(scores) - n]  # the n-th best score
    above = np.flatnonzero(scores > cut)
    tied = np.flatnonzero(scores == cut)[:n - len(above)]
    head = np.concatenate([above, tied])
    return head[np.lexsort((head, -scores[head]))]


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
        """Each moment's best line's score. A moment's lines sit side by side, so each moment is one slice."""
        if self._owner is None or len(self._owner) != len(self.owner):
            self._owner = np.asarray(self.owner, dtype=np.int64)
        if getattr(self, "_starts_n", -1) != len(self.owner):
            o = self._owner
            first = np.flatnonzero(np.r_[True, o[1:] != o[:-1]]) if len(o) else np.zeros(0, dtype=np.int64)
            self._starts, self._with_lines, self._starts_n = first, o[first], len(self.owner)
        out = np.zeros(self.moments, dtype=np.float32)
        if len(line_scores):
            out[self._with_lines] = np.maximum.reduceat(line_scores, self._starts)
        return out

    def order(self, question: str, dense: np.ndarray | None = None, *, hop: bool = True,
              head: int | None = None) -> np.ndarray:
        """Every moment, best first, for ``question`` (only the ``head`` best when given): its words line by line, a
        second look with the best lines' words, and ``dense`` (the embeddings' closeness, one per moment) when given,
        fused by reciprocal rank."""
        ls = self.line_scores(hinted(question))
        parts = [(1.0, sparse_ranks(self.moment_scores(ls)))]
        if hop and len(ls):
            # the second look searches for what the best lines add (the bridge), not for the question again, and
            # counts half: it must not undo a first look that already found an exact name
            asked = set(words(question))
            best = top(ls, HOP_LINES)
            bridge = {w for i in best if ls[int(i)] > 0 for w in words(self.lines[int(i)])} - asked
            if bridge:
                parts.append((HOP_WEIGHT, sparse_ranks(self.moment_scores(self.line_scores(" ".join(sorted(bridge)))))))
        if dense is not None and len(dense) == self.moments:
            parts.append((DENSE_WEIGHT, ranks(dense)))
        fused = sum(w / (RRF_K + r + 1) for w, r in parts)
        return top(fused, head) if head is not None else np.argsort(-fused, kind="stable")


SPEAKER = re.compile(r"^\[[^\]]*\]\s*(User|Assistant):")


def speaker(text: str) -> str | None:
    """Who said a moment, from its stamp: "User", "Assistant", or None."""
    m = SPEAKER.match(text)
    return m.group(1) if m else None


def replies(text_of, order: Sequence[int], *, top: int = 3, moments: int | None = None) -> list[int]:
    """What the user said back after an answer, for each of the ``top`` best moments that is the user's question: the
    moment two on, when the one between is the assistant's answer and that one is the user's again. A method taught
    as a correction ("Not quite, here's how our fee works...") shares few words with the next question of its kind,
    but the question it corrected shares many; so the question is found and its correction read with it, never the
    wrong answer between them. ``text_of(m)`` is moment m's words; ``moments`` how many there are."""
    out: list[int] = []
    for m in list(order[:top]):
        m = int(m)
        if moments is not None and m + 2 >= moments:
            continue
        t = text_of(m)
        if speaker(t) == "User" and t.rstrip().endswith("?") and speaker(text_of(m + 1)) == "Assistant" \
                and speaker(text_of(m + 2)) == "User":
            out.append(m + 2)
    return out


VALUE = re.compile(r"\d|\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I)
SAME_WORDS = 3  # words two lines must have in common to name the same thing
OVERLAP = 0.6  # and this share of the shorter line's words
NEWEST_LOOK = 200  # lines looked at, best first, for a newer one naming the same thing


def _named(line: str) -> set[str]:
    """A line's words without the ones holding digits: what it names, not the value it gives."""
    return {w for w in words(line) if not any(c.isdigit() for c in w)}


def newest(index: LineIndex, question: str, order: Sequence[int], *, best: int = 2) -> list[int]:
    """For each of the ``best`` best moments: its best line for the question, when that line gives a value (a number
    or a day), and the newest later line naming the same thing (at least SAME_WORDS words in common, at least
    OVERLAP of the shorter line's words) and giving a value too; the moments holding those newer lines. A value
    told and changed later ("the production app port is 8010" ... "changed the production app port to 8200") then
    reaches the question by its latest version, even when the question's words found only an older one."""
    if not len(order):
        return []
    ls = index.line_scores(hinted(question))
    if index._owner is None or len(index._owner) != len(index.owner):
        index._owner = np.asarray(index.owner, dtype=np.int64)
    owner = index._owner
    out: list[int] = []
    for m in list(order[:best]):
        m = int(m)
        lo, hi = int(np.searchsorted(owner, m, "left")), int(np.searchsorted(owner, m, "right"))
        if hi <= lo:
            continue
        here = lo + int(np.argmax(ls[lo:hi]))
        line = index.lines[here]
        if ls[here] <= 0 or not VALUE.search(line):
            continue
        a = _named(line)
        if len(a) < SAME_WORDS:
            continue
        sc = index.line_scores(" ".join(sorted(a)))
        sc[:hi] = 0  # only lines told after this moment
        latest = None
        for i in top(sc, NEWEST_LOOK):
            if sc[i] <= 0:
                break
            b = _named(index.lines[i])
            both = len(a & b)
            if both >= SAME_WORDS and both >= OVERLAP * min(len(a), len(b)) and VALUE.search(index.lines[i]):
                if latest is None or i > latest:
                    latest = int(i)
        if latest is not None and int(owner[latest]) not in out:
            out.append(int(owner[latest]))
    return out


CODE = re.compile(r"```|^\s*(def|class|import|from \S+ import|return)\b|^ {4}\S", re.M)
CUT_LINES = 4  # a long moment is read as its best lines for the question, this many, in their own order
CUT_FROM = 6  # only a moment with more lines than this is cut: a short one is read whole


def cut(index: LineIndex, question: str, texts, mids: Sequence[int], *, per: int = CUT_LINES,
        longer: int = CUT_FROM) -> dict[int, str]:
    """Each moment in ``mids`` (``texts[m]`` its words) as it is read for ``question``: whole when it has at most ``longer`` lines, else its
    stamp and its ``per`` best lines by the question's words (and the bridge words of the best line overall), kept in
    their own order and joined by " … ". A pasted group chat of forty lines then costs four lines, not forty."""
    if not mids:
        return {}
    ls = index.line_scores(hinted(question))
    if index._owner is None or len(index._owner) != len(index.owner):
        index._owner = np.asarray(index.owner, dtype=np.int64)
    owner = index._owner
    out: dict[int, str] = {}
    for m in mids:
        lo, hi = int(np.searchsorted(owner, m, "left")), int(np.searchsorted(owner, m, "right"))
        text = texts[int(m)]
        if hi - lo <= longer or CODE.search(text):  # code is read whole: a function cut to lines no longer runs
            out[int(m)] = text
            continue
        top = sorted(lo + int(i) for i in np.argsort(-ls[lo:hi], kind="stable")[:per])
        stamp = STAMP.match(text)
        out[int(m)] = (stamp.group(0) if stamp else "") + " … ".join(index.lines[i] for i in top)
    return out


ROOM_LINES = 6  # an asleep room read as lines: its best lines for the question, this many at most


def room_lines(index: LineIndex, question: str, texts, mids: Sequence[int], *, most: int = ROOM_LINES,
               skip: Iterable[int] = ()) -> dict[int, str]:
    """An asleep room read through the question: across its moments ``mids`` (``texts[m]`` each one's words), the
    ``most`` lines that share a word with the question, best first, kept with their moment's stamp and in the
    room's order. Moments in ``skip`` (already read whole) and lines sharing no word are left out. The room keeps
    what it is for, related moments side by side, at a few lines' cost instead of the whole room's."""
    mids = [int(m) for m in mids if int(m) not in set(skip)]
    if not mids or most <= 0:
        return {}
    ls = index.line_scores(hinted(question))
    if index._owner is None or len(index._owner) != len(index.owner):
        index._owner = np.asarray(index.owner, dtype=np.int64)
    owner = index._owner
    cand: list[tuple[float, int, int]] = []  # (score, moment, line)
    for m in mids:
        lo, hi = int(np.searchsorted(owner, m, "left")), int(np.searchsorted(owner, m, "right"))
        cand += [(float(ls[i]), m, i) for i in range(lo, hi) if ls[i] > 0]
    keep = sorted(cand, key=lambda c: -c[0])[:most]
    out: dict[int, str] = {}
    for m in sorted({c[1] for c in keep}):
        lines = sorted(c[2] for c in keep if c[1] == m)
        stamp = STAMP.match(texts[m])
        out[m] = (stamp.group(0) if stamp else "") + " … ".join(index.lines[i] for i in lines)
    return out


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
