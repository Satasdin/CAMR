"""Verified answers: an answer is stated as fact only when memory supports it.

A frozen small model reading notes can still answer from its own, unreliable, knowledge,
or copy the wrong name from the notes (the producer when the director was asked). The
engine checks every answer against the evidence it was given before stating it:

1. **Grounding**: every content word of the claim (the answer without the words of the
   question and a few frame words) occurs in one unit of evidence: a sentence of a note,
   or one fact line ("Directed by: Ravi Chopra").
2. **Subject**: that unit belongs to a note about what the question names (the note's
   title is the name, or the unit names it).
3. **Relation**: when the question asks for a relation that memory holds as a labelled
   fact ("Directed by", "Born", "Capital"), a fact line with another label is not
   support: a director's name is no answer to "who produced it".
4. **Confidence** (optional): the mean log-probability of the claim's tokens, when the
   runtime reports them; used only where there is no evidence to check against.

Everything except (4) is model-free and costs microseconds. ``read_facts`` answers a
question straight from a matching fact line, with no model at all.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from camr.memory.entities import norm, question_entities

# ---------------------------------------------------------------------- relations
# (name, what a question asking for it says, the infobox labels that hold it). Ordered: the first match wins, so
# the more specific relations come first ("who wrote the music" is the composer, not the author).
RELATIONS: list[tuple[str, re.Pattern, tuple[str, ...]]] = [(n, re.compile(q, re.I), l) for n, q, l in [
    ("composer", r"\bcompos(?:er|ed|itions?)\b|\bmusic (?:by|for|of)\b|\b(?:film )?score\b",
     ("music by", "composer", "composed by", "music", "composers")),
    ("screenwriter", r"\bscreen ?(?:writer|play)s?\b|\bscript\b|\bteleplay\b",
     ("screenplay by", "written by", "screenplay", "writer", "writers", "teleplay by", "story by")),
    ("director", r"\bdirect(?:or|ors|ed|s)\b", ("directed by", "director", "directors")),
    ("producer", r"\bproduc(?:er|ers|ed|es)\b", ("produced by", "producer", "producers", "executive producer",
                                                  "executive producers")),
    ("author", r"\bauthors?\b|\bwr(?:ote|itten|iter)\b", ("author", "authors", "written by", "writer", "writers")),
    ("father", r"\bfather\b|\bdad\b", ("father", "parents", "parent", "parent(s)")),
    ("mother", r"\bmother\b|\bmum\b|\bmom\b", ("mother", "parents", "parent", "parent(s)")),
    ("birthplace", r"\bborn\b|\bbirth ?place\b|\bplace of birth\b", ("born", "place of birth", "birthplace")),
    ("deathplace", r"\bdied\b|\bdeath\b", ("died", "death", "place of death")),
    ("capital", r"\bcapital\b|\bseat\b", ("capital", "seat", "county seat", "administrative centre",
                                          "administrative center", "capital and largest city", "capital city")),
    ("country", r"\bcountry\b|\bnation\b", ("country", "country of origin", "sovereign state", "nation")),
    ("genre", r"\bgenres?\b|\bkind of music\b|\bstyle of music\b", ("genre", "genres")),
    ("occupation", r"\boccupation\b|\bprofession\b|\bjob\b|\bfor a living\b|\bwork as\b",
     ("occupation", "occupations", "occupation(s)", "profession")),
    ("religion", r"\breligio(?:n|us)\b|\bfaith\b", ("religion", "religious affiliation", "denomination")),
    ("sport", r"\bsports?\b", ("sport", "sports", "discipline")),
    ("spouse", r"\bspouse\b|\bmarried\b|\bwife\b|\bhusband\b", ("spouse", "spouses", "spouse(s)", "partner")),
    ("founded", r"\bfound(?:ed|er|ers)\b|\bestablished\b", ("founded", "founder", "founders", "established")),
    ("population", r"\bpopulation\b|\bhow many people\b", ("population",)),
    ("language", r"\blanguages?\b", ("language", "languages", "official languages", "original language")),
    ("headquarters", r"\bheadquarter(?:s|ed)\b|\bbased\b", ("headquarters", "location")),
    ("party", r"\b(?:political )?party\b", ("political party", "party")),
    ("color", r"\bcolou?rs?\b", ("color", "colors", "colour", "colours")),
    ("starring", r"\bstar(?:s|red|ring)\b|\bcast\b|\bactors?\b", ("starring", "cast")),
    ("publisher", r"\bpublish(?:er|ed)\b", ("publisher", "published by")),
    ("label", r"\brecord label\b|\blabel\b", ("label", "labels")),
    ("network", r"\bnetwork\b|\bchannel\b|\baired\b", ("network", "original network", "original release")),
    ("released", r"\breleased?\b|\bcome out\b", ("release date", "released", "release")),
]]


def relation_of(question: str) -> tuple[str, tuple[str, ...]] | None:
    for name, pattern, labels in RELATIONS:
        if pattern.search(question):
            return name, labels
    return None


def label_matches(label: str, labels: tuple[str, ...]) -> bool:
    lab = norm(label)
    return any(lab == norm(x) or lab.startswith(norm(x) + " ") for x in labels)


# ---------------------------------------------------------------------- evidence units
@dataclass
class Unit:
    """One checkable piece of evidence: a sentence of a note, or one fact line of an article."""

    title: str
    text: str
    label: str = ""  # the fact's label ("Directed by"); empty for a sentence
    note_id: int | None = None
    score: float = 0.0

    def render(self) -> str:
        return f"{self.title}: {self.text}" if self.title else self.text


_SENT = re.compile(r"(?<=[.!?])\s+(?=[\"“(\[]?[A-Z0-9])")
_ABBREV = re.compile(r"(?:\b[A-Z]|\b(?:Mr|Mrs|Ms|Dr|St|Jr|Sr|Mt|Ft|No|Vol|Co|Inc|Ltd|vs|c|ca|U\.S|U\.K))\.$")


def sentences(text: str) -> list[str]:
    """Split on sentence ends, but not after an initial or a common abbreviation ("R. D. Burman", "St. Louis")."""
    out: list[str] = []
    for piece in _SENT.split(text.strip()):
        if out and _ABBREV.search(out[-1]):
            out[-1] = f"{out[-1]} {piece}"
        elif piece:
            out.append(piece)
    return out


def units_from_notes(store, notes) -> list[Unit]:
    """Evidence units of recalled notes: fact notes stay whole, other notes are split into sentences."""
    notes = list(notes)
    if not notes:
        return []
    ids = sorted({n.source_id for n in notes})
    marks = ",".join("?" * len(ids))
    src = {r[0]: (r[1] or "", r[2] or "") for r in store.conn.execute(
        f"SELECT source_id, title, doc_id FROM source WHERE source_id IN ({marks})", ids)}
    out: list[Unit] = []
    for n in notes:
        title, doc_id = src.get(n.source_id, ("", ""))
        body = n.text[len(title) + 2:] if title and n.text.startswith(title + ": ") else n.text
        if "#fact:" in doc_id:
            label, _, value = body.partition(": ")
            out.append(Unit(title, body, label=label, note_id=n.note_id))
        else:
            out += [Unit(title, s, note_id=n.note_id) for s in sentences(body)]
    return out


# ---------------------------------------------------------------------- the claim in an answer
# words that frame an answer rather than state it ("X was directed by Y", "the answer is Y")
_FRAME = {"the", "a", "an", "of", "in", "on", "at", "by", "is", "was", "were", "are", "be", "been", "and", "or", "to",
          "for", "with", "as", "from", "it", "its", "he", "she", "his", "her", "they", "their", "this", "that", "who",
          "which", "what", "answer", "directed", "produced", "written", "wrote", "composed", "born", "located", "known",
          "called", "named", "plays", "played", "created", "founded", "situated", "lies", "s", "also", "mainly",
          "primarily", "originally", "former", "currently", "best", "has", "had", "have", "did", "does", "do", "film",
          "movie", "series", "show", "song", "album", "book", "novel"}
_LEAD = re.compile(r"^\s*(?:answer\s*:|the answer is\s*:?|it is|it was|that is|this is)\s*", re.I)
_DECLINE = re.compile(r"\b(?:not (?:mentioned|provided|given|stated|specified|available|known)|no (?:information|mention)"
                      r"|(?:do|does|did) not (?:mention|say|state|include|contain|provide|specify)|unknown|cannot be "
                      r"determined|not enough information)\b", re.I)


def claim(answer: str) -> str:
    """The first line and sentence of an answer, without "Answer:" and quotes."""
    text = (answer or "").strip().split("\n")[0]
    text = _LEAD.sub("", text)
    first = sentences(text)
    text = first[0] if first else text
    return text.strip(" \"“”'.")


def claim_words(question: str, answer: str) -> list[str]:
    q = set(norm(question).split())
    return [w for w in norm(claim(answer)).split() if w not in q and w not in _FRAME]


# ---------------------------------------------------------------------- what the question is about
def subject_names(question: str) -> list[str]:
    from camr.memory.fetch import subjects

    names = [norm(s) for s in subjects(question)] + question_entities(question)
    return [n for n in dict.fromkeys(names) if len(n) >= 3]


def aboutness(unit: Unit, names: list[str]) -> int:
    """2: the unit's note is titled with a name the question gives; 1: its title contains the name, or the unit
    mentions it; 0: neither. A name that is only part of a longer one ("Son" in "Son contento") counts as 1."""
    from camr.memory.fetch import base_title

    if not names:
        return 2  # nothing to check against
    bare = [re.sub(r"^(?:the|a|an) ", "", n) for n in names]
    title = base_title(unit.title) if unit.title else ""
    text = f" {norm(unit.render())} "
    best = 0
    for n in bare:
        part_of_longer = any(n != m and f" {n} " in f" {m} " for m in bare)
        if title and title == n:
            best = max(best, 1 if part_of_longer else 2)
        elif title and (f" {n} " in f" {title} " or (len(title) >= 4 and f" {title} " in f" {n} ")):
            best = max(best, 1)
        elif f" {n} " in text:
            best = max(best, 1)
    return best


def about(unit: Unit, names: list[str]) -> bool:
    return aboutness(unit, names) > 0


# ---------------------------------------------------------------------- the check
@dataclass
class Verdict:
    supported: bool
    reason: str  # "supported", "declined", "not in memory", "another subject", "another relation", "no evidence"
    words: list[str] = field(default_factory=list)
    coverage: float = 0.0  # share of the claim's words found in the best unit
    evidence: Unit | None = None
    relation: str | None = None
    confidence: float | None = None  # mean log-probability of the claim's tokens

    def as_dict(self) -> dict:
        return {"supported": self.supported, "reason": self.reason, "words": self.words,
                "coverage": round(self.coverage, 3), "relation": self.relation,
                "evidence": self.evidence.render() if self.evidence else None,
                "confidence": None if self.confidence is None else round(self.confidence, 3)}


def claim_confidence(answer: str, logprobs: list[dict] | None, question: str = "") -> float | None:
    """Mean log-probability of the tokens that spell the claim's words (Ollama ``logprobs``)."""
    if not logprobs:
        return None
    words = set(claim_words(question, answer)) or set(norm(claim(answer)).split())
    vals = [t["logprob"] for t in logprobs if set(norm(t.get("token", "")).split()) & words]
    if not vals:
        vals = [t["logprob"] for t in logprobs[:8]]
    return sum(vals) / len(vals) if vals else None


_ABSTAIN = re.compile(r"^\s*(unknown|i\s+don'?t\s+know|i\s+do\s+not\s+know|not\s+sure|no\s+answer|n/?a|none|cannot\s+be"
                      r"\s+determined|i'?m\s+not\s+sure|i\s+cannot|i\s+can'?t)\b", re.I)


def abstention_like(answer: str | None) -> bool:
    return not (answer or "").strip() or bool(_ABSTAIN.search(answer or ""))


def check(question: str, answer: str, units: list[Unit], *, min_coverage: float = 1.0,
          logprobs: list[dict] | None = None) -> Verdict:
    rel = relation_of(question)
    conf = claim_confidence(answer, logprobs, question)
    if abstention_like(claim(answer)) or _DECLINE.search(answer):
        return Verdict(False, "declined", relation=rel and rel[0], confidence=conf)
    words = claim_words(question, answer)
    if not words:  # nothing beyond the question's own words: an echo, not an answer
        return Verdict(False, "declined", relation=rel and rel[0], confidence=conf)
    if not units:
        return Verdict(False, "no evidence", words, relation=rel and rel[0], confidence=conf)
    names = subject_names(question)
    level = {id(u): aboutness(u, names) for u in units}
    top = max(level.values())  # when memory has a note titled with the subject, only that subject's notes count
    best: tuple[float, int, Unit] | None = None
    candidates: list[tuple[float, Unit]] = []
    for u in units:
        toks = set(norm(u.render()).split())
        cov = sum(w in toks for w in words) / len(words)
        candidates.append((cov, u))
        key = (cov, level[id(u)], u)
        if best is None or key[:2] > best[:2]:
            best = key
    cov, _, unit = best
    if cov < min_coverage:
        return Verdict(False, "not in memory", words, cov, unit, rel and rel[0], conf)
    supporting = [u for c, u in candidates if c >= min_coverage and top > 0 and level[id(u)] == top]
    if not supporting:
        return Verdict(False, "another subject", words, cov, unit, rel and rel[0], conf)
    if rel:
        facts_here = [u for u in units if u.label and top > 0 and level[id(u)] == top]
        has_rel = [u for u in facts_here if label_matches(u.label, rel[1])]
        if has_rel and not any(u in has_rel or not u.label for u in supporting):
            # memory holds the asked relation as a labelled fact, and the claim matches only other labels
            return Verdict(False, "another relation", words, cov, supporting[0], rel[0], conf)
        if has_rel and not any(u in has_rel for u in supporting):
            # the claim is only in sentences, while a fact line holding the relation says something else
            if not any(set(words) <= set(norm(u.text).split()) for u in has_rel):
                return Verdict(False, "another relation", words, cov, supporting[0], rel[0], conf)
        pick = next((u for u in supporting if u in has_rel), supporting[0])
    else:
        pick = supporting[0]
    return Verdict(True, "supported", words, cov, pick, rel and rel[0], conf)


# ---------------------------------------------------------------------- reading a fact without a model
def read_facts(question: str, units: list[Unit]) -> Unit | None:
    """The fact line that answers the question, when memory holds exactly one for its subject and relation."""
    rel = relation_of(question)
    if not rel:
        return None
    names = subject_names(question)
    hits = [u for u in units if u.label and label_matches(u.label, rel[1]) and about(u, names)]
    if not hits:
        return None
    exact = [u for u in hits if aboutness(u, names) == 2]
    pool = exact or hits
    values = {norm(u.text.partition(": ")[2]) for u in pool}
    titles = {u.title for u in pool}
    if len(values) == 1 or len(titles) == 1:
        # one value, or one article (several labels for the relation, e.g. "Directed by" and "Director")
        return sorted(pool, key=lambda u: (not label_matches(u.label, rel[1][:1]), -u.score))[0]
    return None


def fact_value(unit: Unit) -> str:
    return unit.text.partition(": ")[2]


# ---------------------------------------------------------------------- what the small model reads
def compress(question: str, units: list[Unit], embedder, tokenizer, budget: int = 128,
             relation_bonus: float = 0.30, subject_bonus: float = 0.10) -> list[Unit]:
    """The evidence most worth reading, within ``budget`` tokens: units ranked by similarity to the question,
    with a bonus for a fact line holding the asked relation and for units about the question's subject."""
    import numpy as np

    if not units:
        return []
    rel = relation_of(question)
    names = subject_names(question)
    q = np.asarray(embedder.encode_one(question, is_query=True), dtype=np.float32)
    d = np.asarray(embedder.encode([u.render() for u in units]), dtype=np.float32)
    q /= np.linalg.norm(q) or 1.0
    d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-12)
    sims = d @ q
    for u, s in zip(units, sims):
        u.score = float(s) + (relation_bonus if rel and u.label and label_matches(u.label, rel[1]) else 0.0) + (
            subject_bonus * aboutness(u, names) / 2)
    picked, used, seen = [], 0, set()
    for u in sorted(units, key=lambda u: -u.score):
        key = norm(u.render())
        if key in seen:
            continue
        n = tokenizer.count(u.render()) if hasattr(tokenizer, "count") else len(u.render().split())
        if used + n > budget and picked:
            continue
        picked.append(u)
        seen.add(key)
        used += n
        if used >= budget:
            break
    return picked


def is_finite(x: float | None) -> bool:
    return x is not None and math.isfinite(x)
