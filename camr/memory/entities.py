"""Named entities in a question, for the entity-anchored gate.

A cheap, model-free heuristic: maximal runs of capitalised words (allowing short
lower-case connectors inside a name, e.g. "The Lord of the Rings", "Leonardo da
Vinci") and quoted strings. The question's first word is dropped when it is an
interrogative or auxiliary ("What", "Who", "Is", ...), since it is capitalised only
because it starts the sentence.
"""

from __future__ import annotations

import re
import unicodedata

# lower-case words that occur *inside* names ("Lord of the Rings", "Leonardo da Vinci"); not "and",
# which joins two separate names ("Scott Derrickson and Ed Wood")
_CONNECTORS = {"of", "the", "de", "da", "di", "del", "la", "le", "von", "van", "der", "du", "y"}
_LEADING = {"what", "who", "whom", "whose", "which", "when", "where", "why", "how", "is", "are", "was", "were", "do",
            "does", "did", "can", "could", "would", "should", "will", "in", "on", "at", "for", "name", "tell", "the", "a",
            "an", "my", "i"}
_TOKEN = re.compile(r"[\w'’.&-]+", re.UNICODE)
_POSSESSIVE = re.compile(r"['’]s?$")
_ARTICLE = re.compile(r"^(?:the|a|an) ")
_QUOTED = re.compile(r"[\"“”']([^\"“”']{3,})[\"“”']")


def norm(text: str) -> str:
    """Lower case, possessives removed ("Peck's" -> "peck"), punctuation to spaces. The same normalisation is
    applied to the question and to the notes, so a name matches however it is punctuated (defect D-15)."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"['’]s\b", "", text)
    return " ".join(re.findall(r"\w+", text, re.UNICODE))


def question_entities(question: str) -> list[str]:
    """Normalised entity strings named in the question (possibly empty)."""
    out = [norm(m.group(1)) for m in _QUOTED.finditer(question)]
    toks = [_POSSESSIVE.sub("", t) for t in _TOKEN.findall(question)]
    i = 0
    while i < len(toks):
        t = toks[i]
        if t[:1].isupper() and not (i == 0 and t.lower() in _LEADING):
            j, run = i, [t]
            while j + 1 < len(toks):
                nxt = toks[j + 1]
                if nxt[:1].isupper() or nxt[:1].isdigit():
                    run.append(nxt)
                    j += 1
                elif nxt.lower() in _CONNECTORS:
                    k = j + 1  # one or more connectors ("of the"), then a capitalised word continues the name
                    while k < len(toks) and toks[k].lower() in _CONNECTORS:
                        k += 1
                    if k < len(toks) and toks[k][:1].isupper():
                        run += toks[j + 1:k + 1]
                        j = k
                    else:
                        break
                else:
                    break
            span = _ARTICLE.sub("", norm(" ".join(run)))
            if len(span) >= 3 and span not in _LEADING:
                out.append(span)
            i = j + 1
        else:
            i += 1
    return list(dict.fromkeys(s for s in out if s))


def mentions_any(text: str, entities: list[str]) -> bool:
    t = f" {norm(text)} "
    return any(f" {e} " in t for e in entities)
