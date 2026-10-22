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


# Words of time that are capitalised but are not names: with ``skip_time`` a run made only of them (and numbers) is
# not an entity ("Can you suggest a dinner place for Friday?" names nothing memory must mention).
_TIME_WORDS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "today", "tomorrow",
               "yesterday", "tonight", "january", "february", "march", "april", "may", "june", "july", "august",
               "september", "october", "november", "december", "weekend", "christmas", "easter", "morning",
               "evening", "afternoon", "noon", "midnight"}


def _only_time(span: str) -> bool:
    words = span.split()
    return bool(words) and all(w in _TIME_WORDS or w.isdigit() or w in {"last", "next", "this", "of", "the"}
                               for w in words)


def question_entities(question: str, skip_time: bool = False) -> list[str]:
    """Normalised entity strings named in the question (possibly empty). ``skip_time`` leaves out spans that are
    only days, months and words like "today" (off by default: the research configurations never set it)."""
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
    return list(dict.fromkeys(s for s in out if s and not (skip_time and _only_time(s))))


def mentions_any(text: str, entities: list[str]) -> bool:
    t = f" {norm(text)} "
    return any(f" {e} " in t for e in entities)


# ---------------------------------------------------------------------- personal slots (``slot_gate``)
# Words that name an attribute of a thing rather than the thing ("my passport *number*", "the *name* of my hamster").
_ATTRIBUTES = {"number", "numbers", "name", "names", "date", "day", "time", "address", "code", "type", "kind", "size",
               "colour", "color", "price", "cost", "age", "model", "brand", "make", "breed", "speed", "score",
               "amount", "total", "rate", "length", "height", "weight", "value", "level", "status", "title",
               "version", "id", "details", "detail", "registration", "pin", "password", "location", "place"}
_SLOT_STOP = {"a", "an", "the", "my", "our", "new", "old", "current", "first", "last", "next", "own", "favourite",
              "favorite", "usual", "previous", "recent", "latest", "is", "was", "are", "were", "and", "or", "in", "on",
              "at", "for", "to", "from", "with", "of", "when", "where", "what", "which", "how", "did", "do", "does"}
# nouns that end in -ing (elsewhere an -ing word after "X's" is a verb: "my kitchen's becoming" = "kitchen is")
_ING_NOUNS = {"wedding", "weddings", "meeting", "meetings", "building", "painting", "paintings", "evening",
              "morning", "clothing", "ceiling", "booking", "setting", "training", "ring", "rings", "earring",
              "earrings", "thing", "things", "string", "spring", "wing", "bedding", "pudding", "housewarming",
              "christening", "graduation", "parking", "recording", "drawing", "drawings", "dumpling", "sibling",
              "siblings", "offspring", "seedling", "seedlings", "duckling", "king", "swing", "ping"}
_MY_PHRASE = re.compile(r"\bmy\s+((?:[a-z][\w'’-]*\s*){1,4})", re.I)


def personal_slots(question: str) -> list[list[str]]:
    """What a first-person question asks about, when it asks for a specific thing of the user's, as groups of
    words: a note must mention a word of every group. "When is my brother's wedding?" -> [["brother"],
    ["wedding"]] (whose, and what); "What is my passport number?" -> [["passport"]]; "What's the code for my bike
    lock?" -> [["bike", "lock"]] (either). Empty when the question asks for no such thing: it names no attribute
    ("number", "name", ...) and no "X's Y" ("My kitchen's becoming a mess" is "kitchen is")."""
    q = question.strip().rstrip("?.! ")
    out: list[list[str]] = []
    for m in _MY_PHRASE.finditer(q):
        words = [w.lower().strip("'’") for w in m.group(1).split()]
        phrase: list[str] = []
        for w in words:
            if w in _SLOT_STOP and phrase:
                break
            if w not in _SLOT_STOP:
                phrase.append(w)
        def verb(w: str) -> bool:
            return w.endswith("ing") and w not in _ING_NOUNS

        poss = next((i for i, w in enumerate(phrase[:-1]) if w.endswith(("'s", "’s")) and not verb(phrase[i + 1])),
                    None)
        if poss is None and any(w.endswith(("'s", "’s")) for w in phrase[:-1]):
            phrase = phrase[:next(i for i, w in enumerate(phrase) if w.endswith(("'s", "’s"))) + 1]
        before = q[:m.start()].lower()
        attr_before = re.search(r"\b(?:" + "|".join(_ATTRIBUTES) + r")\s+(?:of|for)\s+$", before) is not None or \
            re.search(r"\bwhat\s+(?:" + "|".join(_ATTRIBUTES) + r")\s+(?:is|was|are|were)\s+$", before) is not None
        nouns = [re.sub(r"['’]s$", "", w) for w in phrase]
        nouns = [w for w in nouns if w and w not in _ATTRIBUTES and w not in _SLOT_STOP
                 and not w.endswith(("ly", "ed")) and not verb(w)]
        if not nouns:
            continue
        if poss is not None:  # "my brother's wedding": whose (brother) and what (the last word)
            owner = re.sub(r"['’]s$", "", phrase[poss])
            out += [[owner], [nouns[-1]]] if nouns[-1] != owner else [[owner]]
        elif attr_before or any(w in _ATTRIBUTES for w in phrase):
            out.append(nouns)
    return out


def mentions_slot(text: str, slot: str) -> bool:
    """The text mentions the slot word, allowing a plural or another ending ("motorbike" ~ "motorbikes")."""
    stem = slot[:-1] if slot.endswith("s") and len(slot) > 3 else slot
    stem = stem[:6] if len(stem) > 6 else stem
    return re.search(rf"\b{re.escape(stem)}", text.lower()) is not None
