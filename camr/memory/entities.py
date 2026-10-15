"""Named entities in a question, for the entity-anchored gate.

A cheap, model-free heuristic: maximal runs of capitalised words (allowing short
lower-case connectors inside a name, e.g. "The Lord of the Rings", "Leonardo da
Vinci") and quoted strings. A sentence's first word is dropped when it is an
interrogative, auxiliary or instruction ("What", "Who", "Is", "Find", "Give", ...), since
it is capitalised only because it starts the sentence; every sentence of a question
counts ("A sequence begins 6, 11, 16. Add up its first 11 terms.").
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
# instructions and openers that start a sentence of a task ("Find its area.", "Give the amount to the cent.")
_LEADING |= {"find", "give", "compute", "calculate", "work", "add", "convert", "use", "using", "solve", "determine",
             "express", "write", "list", "show", "round", "starting", "suppose", "if", "after", "each", "every",
             "one", "there", "please", "let", "assume", "given", "estimate", "say", "explain"}
# words that open a terse request or a greeting ("Reply with the fix.", "Any idea?", "Hello, …"); only at the start
# of a sentence, since elsewhere they are titles ("the composer of Hello", "Help!")
_OPENERS = {"reply", "handle", "create", "send", "check", "answer", "describe", "ask", "help", "any", "hi", "hello",
            "thanks", "dear"}
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


_ABBREV = {"st", "mt", "mr", "mrs", "ms", "dr", "jr", "sr", "no", "vs", "co", "inc", "ltd", "ft", "vol", "pt"}


def _ends_sentence(tok: str) -> bool:
    """A token that closes a sentence ("Volta-2.", "E57?"); not an initial ("J."), dotted initials ("A.I."), a
    title abbreviation ("St.") or an ellipsis inside a title ("Viruddh... Family Comes First")."""
    if tok[-1:] not in ".?!:":
        return False
    if tok.endswith(".") and (re.fullmatch(r"(?:[A-Za-z]\.)+", tok) or tok.endswith("...")
                              or tok[:-1].lower() in _ABBREV):
        return False
    return True


def _asks(i: int, toks: list[str], qmark: list[bool]) -> bool:
    """The sentence that starts at token i asks for something: it ends with a question mark, says "please", or is
    a fragment that runs to the end of the text without a full stop ("Price of the Helio bird mesh kit please").
    A statement ends with a full stop ("Josh decides to try flipping a house.")."""
    for j in range(i, len(toks)):
        if qmark[j] or toks[j].lower().strip(".,!") == "please":
            return True
        if _ends_sentence(toks[j]):
            return False
    return True


def question_entities(question: str) -> list[str]:
    """Normalised entity strings named in the question (possibly empty)."""
    out = [norm(m.group(1)) for m in _QUOTED.finditer(question)]
    found = list(_TOKEN.finditer(question))
    toks = [_POSSESSIVE.sub("", m.group(0)) for m in found]
    qmark = [question[m.end():m.end() + 1] == "?" for m in found]  # the token is followed by a question mark
    starts = {0} | {k + 1 for k, t in enumerate(toks) if t[-1:] in ".?!:"}
    i = 0
    while i < len(toks):
        t = toks[i]
        nxt0 = toks[i + 1] if i + 1 < len(toks) else ""
        # a capitalised first word followed by a lower-case one opens a sentence; it is not a name ("Recommended
        # cleaning interval?", "Bird mesh kit price?", "Price of the Helio kit"); a lone word ("Fix?") neither
        # only in a question fragment: in a statement the first word is usually a name ("Josh decides to ...")
        opener = (i in starts and not (nxt0[:1].isupper() or nxt0[:1].isdigit()) and not _ends_sentence(t)
                  and _asks(i, toks, qmark))
        if t[:1].isupper() and not opener and not (i in starts and t.lower().rstrip(".") in _LEADING | _OPENERS):
            j, run = i, [t]
            while j + 1 < len(toks):
                nxt = toks[j + 1]
                if _ends_sentence(toks[j]):  # a name ends with its sentence ("E57. Any idea?", "Volta-2. Reply")
                    break
                if j + 1 in starts and nxt.lower().rstrip(".") in _LEADING | _OPENERS:  # sentence ended ("J. How")
                    break
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
            if len(span) >= 3 and span not in _LEADING and not (i in starts and span in _OPENERS):
                out.append(span)
            i = j + 1
        else:
            i += 1
    return list(dict.fromkeys(s for s in out if s))


def mentions_any(text: str, entities: list[str]) -> bool:
    t = f" {norm(text)} "
    return any(f" {e} " in t for e in entities)
