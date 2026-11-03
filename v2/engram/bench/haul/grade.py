"""Grading a Long Haul answer by rule. The same answer always gets the same verdict.

Verdicts:
  right         the expected answer (for a never-said question: a decline that does not then guess)
  wrong         something else, or a look-alike's value, or code or a page that fails its checks
  stale         a value an update replaced, the uncorrected method's number, or the old main colour
  declined      says it doesn't know, but the answer was told
  false_memory  answers a question about something never told, or declines and then guesses anyway

``grade(probe, answer_text)`` returns a ``Grade`` (verdict, reason). Each probe's ``grader`` spec says how:
exact (accept, stale, reject and others lists), timeline (a changed fact, resolved to exact), number, page, code or
never (with an optional pool of values that would be a guess).

Values are matched by kind: numbers as numbers (450 is 450.00, 0.80 is 0.8, 20.11 is 20.11.0, and 449 is not 450),
times as minutes since midnight (07:00 is 7 am, 7am and 0700, and 7:00 pm is not), and words as whole words. A
"day N" that the question itself names is not read as an answer.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import NamedTuple

from engram.bench.haul import codefit, page
from engram.ruler.grade import abstains

VERDICTS = ("right", "wrong", "stale", "declined", "false_memory")


class Grade(NamedTuple):
    verdict: str
    reason: str


_DECLINE = re.compile(
    r"\b(?:i\s+(?:don'?t|do\s+not)\s+(?:have|know|recall|remember|see)"
    r"|(?:no|not\s+any)\s+(?:record|records|mention|information|info|details?|notes?|data)\b"
    r"|(?:never|not|wasn'?t|was\s+not|haven'?t\s+been|has\s+not\s+been|hasn'?t\s+been|have\s+not\s+been)\s+"
    r"(?:been\s+)?(?:told|mentioned|said|given|shared|stated|recorded|specified|provided)"
    r"|(?:you|we|anyone|nobody)\s+(?:never|haven'?t|have\s+not|didn'?t|did\s+not)\s+(?:told|tell|mention|said|say|"
    r"share|shared|give|gave)"
    r"|(?:you'?ve|you\s+have|we'?ve|we\s+have)\s+(?:never|not)\s+(?:told|mentioned|said|shared|given)"
    r"|i\s+(?:don'?t|do\s+not)\s+think\s+(?:you|we|anyone|it|that)(?:'ve|\s+have|\s+ever|\s+was|\s+has)*\s+"
    r"(?:told|mentioned|said|shared|given|came\s+up|been\s+(?:told|mentioned|said))"
    r"|(?:nobody|no\s+one)\s+(?:ever\s+)?(?:told|mentioned|said|shared)"
    r"|(?:can'?t|cannot|could\s?n'?t|unable\s+to)\s+(?:find|tell|say|recall|determine|answer|know)"
    r"|not\s+(?:sure|certain|aware)|no\s+idea|unknown|not\s+in\s+(?:my|the)\s+(?:memory|notes|records))")


def declines(answer: str) -> bool:
    """Whether the answer says it does not know (the ruler's phrases plus a few more)."""
    a = answer.lower().replace("’", "'")
    return abstains(answer) or bool(_DECLINE.search(a))


def norm(text: str) -> str:
    """Lowercase, plain quotes and dashes, no thousands separators, no ordinal endings: "12,000th" -> "12000"."""
    t = text.casefold()
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("–", "-"), ("—", "-"), ("\u00a0", " "),
                 ("\u202f", " "), ("\u2009", " ")):
        t = t.replace(a, b)
    t = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", t)
    t = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", t)
    t = re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1", t)
    return " ".join(t.split())


# -- numbers and times ------------------------------------------------------------------------------------------

_IS_NUMBER = re.compile(r"\d+(?:\.\d+)*")
_NUMBERS = re.compile(r"(?<![\d.])\d+(?:\.\d+)*(?!\d|\.\d|:\d)")
_IS_TIME = re.compile(r"\d{1,2}(?::\d{2}(?:\s?[ap]\.?m\.?)?|[.]\d{2}\s?[ap]\.?m\.?|\s?[ap]\.?m\.?)")
_TIMES = re.compile(
    r"(?<![\d.:])(?:(?P<h1>\d{1,2})(?:[:.](?P<m1>\d{2}))?\s?(?P<ap>[ap])\.?\s?m\b\.?"
    r"|(?P<h2>\d{1,2})[:.](?P<m2>\d{2})(?!\d|\.\d)"
    r"|(?P<h3>[01]\d|2[0-3])(?P<m3>[0-5]\d)(?![\d.:]))"
    r"|\b(?P<noon>noon|midday)\b|\b(?P<midnight>midnight)\b")


def _is_number(v: str) -> bool:
    return bool(_IS_NUMBER.fullmatch(v))


def _is_time(v: str) -> bool:
    return bool(_IS_TIME.fullmatch(v))


def same_number(a: str, b: str) -> bool:
    """Two numbers written as text are the same number: 450 and 450.00, 0.80 and 0.8; versions with two or more
    dots compare part by part, ignoring trailing zero parts: 20.11 and 20.11.0."""
    if a.count(".") <= 1 and b.count(".") <= 1:
        try:
            return Decimal(a) == Decimal(b)
        except InvalidOperation:
            return a == b

    def parts(x: str) -> list[int]:
        p = [int(n) for n in x.split(".")]
        while len(p) > 1 and p[-1] == 0:
            p.pop()
        return p
    return parts(a) == parts(b)


def times(text: str) -> list[tuple[int, int]]:
    """(minutes since midnight, position) for every time of day in normalised ``text``: 07:00, 7:00 am, 7am, 7.30 pm,
    0700, noon. A 12-hour time whose am/pm does not fit its hour (19:00 am) is left out."""
    out = []
    for m in _TIMES.finditer(text):
        if m.group("noon"):
            out.append((720, m.start()))
            continue
        if m.group("midnight"):
            out.append((0, m.start()))
            continue
        if m.group("h1") is not None:
            h, mins, ap = int(m.group("h1")), int(m.group("m1") or 0), m.group("ap")
            if h > 23 or mins > 59 or h == 0 or (h > 12 and ap == "a"):
                continue
            if h <= 12:
                h = (h % 12) + (12 if ap == "p" else 0)
        else:
            h = int(m.group("h2") if m.group("h2") is not None else m.group("h3"))
            mins = int(m.group("m2") if m.group("m2") is not None else m.group("m3"))
            if h > 23 or mins > 59:
                continue
        out.append((h * 60 + mins, m.start()))
    return out


def _pattern(value: str) -> re.Pattern:
    v = norm(value)
    edge = r"[\w-]" if re.search(r"[-_]", v) else r"\w"
    return re.compile(r"(?<!" + edge + ")" + re.escape(v) + r"(?!" + edge + ")")


def _where(a: str, value: str) -> list[int]:
    """Where in normalised answer ``a`` the value is named: as a number, a time of day, or whole words."""
    v = norm(value)
    if not v.strip():
        return []
    if _is_time(v):
        want = {t for t, _ in times(v)}
        return [i for t, i in times(a) if t in want]
    if _is_number(v):
        return [m.start() for m in _NUMBERS.finditer(a) if same_number(v, m.group())]
    return [m.start() for m in _pattern(v).finditer(a)]


def scrub(answer: str, ask: str | None) -> str:
    """The normalised answer without the "day N" phrases its question names ("on day 14" is not an answer of 14)."""
    a = norm(answer)
    if ask:
        for n in set(re.findall(r"\bday\s+(\d+)\b", norm(ask))):
            a = re.sub(r"\bday\s+" + n + r"\b", "day", a)
    return a


def names(answer: str, values: list[str], ask: str | None = None) -> str | None:
    """The first of ``values`` the answer names (whole words, numbers as numbers, times as times), or None."""
    a = scrub(answer, ask)
    for v in values:
        if _where(a, v):
            return v
    return None


_CONTRAST = re.compile(r"\b(?:not|isn'?t|wasn'?t|aren'?t|never|other|unlike|vs\.?|versus|rather\s+than|instead\s+of|"
                       r"while|whereas|nor|confuse[ds]?|mix(?:ed)?\s+up|as\s+opposed\s+to|different\s+from|"
                       r"distinct\s+from|except|than)\b|n't\b")


def _contrasted(a: str, at: int) -> bool:
    """Whether the value at position ``at`` is named to set it apart ("not the bookkeeper", "the other Wanjiru")."""
    clause = re.split(r"[;!?\n]|\.(?=\s|$)", a[:at])[-1]
    window = " ".join(clause.split()[-6:])
    if re.search(r"\bnot\s+(?:sure|certain)\b|\beither\b|\bor\s*$", window):
        return False
    return bool(_CONTRAST.search(window))


def names_plainly(answer: str, values: list[str], ask: str | None = None) -> str | None:
    """The first of ``values`` the answer names other than to set it apart, or None."""
    a = scrub(answer, ask)
    for v in values:
        if any(not _contrasted(a, i) for i in _where(a, v)):
            return v
    return None


def as_number(s: str) -> Fraction:
    return Fraction(s.replace(",", ""))


_NUM = r"-?\d+(?:\.\d+)?(?:/\d+)?"


def final_number(answer: str) -> Fraction | None:
    """The answer's final number: the last \\boxed{}, else the last "answer: X" or "answer is X", else the last
    bold number, else the last number in the text."""
    t = norm(answer.replace("**", " ** "))
    for pat in (r"\\boxed\{\s*(?:kes|ksh)?\s*(" + _NUM + r")", r"answer\s*(?:is|:|=)?\s*(?:kes|ksh)?\s*\**\s*(" + _NUM
                + ")", r"\*\*\s*(?:kes|ksh)?\s*(" + _NUM + r")\s*\*\*", r"(" + _NUM + ")"):
        found = re.findall(pat, t)
        if found:
            try:
                return as_number(found[-1])
            except (ValueError, ZeroDivisionError):
                return None
    return None


# ---------------------------------------------------------------------------------------------------------------

def grade_exact(spec: dict, answer: str, ask: str | None = None) -> Grade:
    good = names(answer, spec["accept"], ask)
    if good:
        bad = names_plainly(answer, spec.get("reject", []), ask)
        if bad:
            return Grade("wrong", f"names {good} but also the look-alike {bad}")
        other = names_plainly(answer, [v for v in spec.get("others", []) if v not in spec["accept"]], ask)
        if other:
            return Grade("wrong", f"names {good} but also {other}: a list of candidates is not an answer")
        return Grade("right", f"names {good}")
    bad = names(answer, spec.get("reject", []), ask)
    if bad:
        return Grade("wrong", f"names the look-alike {bad}")
    old = names(answer, spec.get("stale", []), ask)
    if old:
        return Grade("stale", f"names {old}, which an update replaced")
    if declines(answer):
        return Grade("declined", "declined, but the answer was told")
    return Grade("wrong", f"does not name {spec['accept'][0]}")


def grade_number(spec: dict, answer: str) -> Grade:
    got = final_number(answer)
    want = as_number(spec["value"])
    if got is None:
        if declines(answer):
            return Grade("declined", "declined, but the method was taught")
        return Grade("wrong", "no number in the answer")
    if got == want:
        return Grade("right", f"final number {spec['value']}")
    stale = [as_number(s) for s in spec.get("stale", [])]
    if got in stale:
        return Grade("stale", f"final number {_show(got)} is what the uncorrected method gives")
    return Grade("wrong", f"final number {_show(got)}, not {spec['value']}")


def _show(x: Fraction) -> str:
    return str(x.numerator) if x.denominator == 1 else f"{float(x):g}"


def grade_page(spec: dict, answer: str, browser: bool = False) -> Grade:
    src = page.extract_html(answer)
    if src is None:
        if declines(answer):
            return Grade("declined", "declined, but the design system was told")
        return Grade("wrong", "no HTML page in the answer")
    checks = page.check(src, spec)
    if checks.get("no_old_colour") is not True and "no_old_colour" in checks:
        return Grade("stale", str(checks["no_old_colour"]))
    failed = [str(v) for v in checks.values() if v is not True]
    note = ""
    if browser and not failed:
        ok, note = page.load_check(src)
        if ok is False:
            failed.append(note)
        note = "; " + note
    if failed:
        return Grade("wrong", "; ".join(failed))
    return Grade("right", "passes every design-system check" + note)


def grade_code(spec: dict, answer: str) -> Grade:
    code = codefit.extract_code(answer)
    if code is None:
        if declines(answer):
            return Grade("declined", "declined, but the helpers were planted")
        return Grade("wrong", "no Python code in the answer")
    r = codefit.run_tests(spec, code)
    if r["error"]:
        return Grade("wrong", f"tests could not run: {r['error']}")
    if r["passed"] == r["total"]:
        return Grade("right", f"passes all {r['total']} tests")
    return Grade("wrong", f"passes {r['passed']} of {r['total']} tests; " + "; ".join(r["failures"][:2]))


_CLAUSES = re.compile(r"[;!?\n()]+|[.,:](?=\s|$)|\s-+\s|\b(?:but|though|although|however|yet)\b")
_GUESS = re.compile(r"\b(?:probably|maybe|perhaps|possibly|presumably|likely|i\s+think|i\s+believe|i\s+guess|"
                    r"i'?d\s+(?:guess|say|imagine)|my\s+(?:best\s+)?guess|if\s+i\s+(?:had|have)\s+to\s+guess|"
                    r"might\s+be|could\s+be|may\s+be|i\s+assume|i\s+suspect|i\s+imagine|i\s+recall|"
                    r"i\s+seem\s+to\s+(?:recall|remember)|chances\s+are|i'?m\s+(?:fairly|pretty|quite)\s+sure|"
                    r"most\s+likely|odds\s+are)\b")
_DEFER = re.compile(r"\b(?:ask|asking|check|checking|confirm|confirming|verify|look\s+(?:it\s+)?up|knows?|"
                    r"worth|contact|tell\s+me|let\s+me\s+know|remind\s+me|share\s+it)\b")


def guesses(answer: str, pool: list[str] | None = None, ask: str | None = None) -> str | None:
    """What an answer commits to although it was never told, or None: a clause that does not itself decline or
    point elsewhere ("ask Otieno") and either hedges a guess ("probably Ochieng", "I think it's Odhiambo") or names
    a value from ``pool`` that the question itself does not name. A pool entry "#number" stands for any number."""
    a = norm(answer)
    q = norm(ask or "")
    words = [v for v in (pool or []) if v != "#number" and not _where(q, v)]
    numbers = "#number" in (pool or [])
    asked = {m.group() for m in _NUMBERS.finditer(q)}
    for clause in _CLAUSES.split(a):
        clause = clause.strip(" '\"*-")
        if not clause or declines(clause) or _DEFER.search(clause):
            continue
        m = _GUESS.search(clause)
        if m and not re.match(r"\s*(?:not\b|n't\b|any(?:thing|one|body)?\b)", clause[m.end():]):
            return clause
        if any(_where(clause, v) for v in words):
            return clause
        if numbers and any(n.group() not in asked for n in _NUMBERS.finditer(clause)):
            return clause
    return None


def grade_never(answer: str, spec: dict | None = None, ask: str | None = None) -> Grade:
    if not declines(answer):
        return Grade("false_memory", "answers something that was never told")
    guess = guesses(answer, (spec or {}).get("pool"), ask)
    if guess:
        return Grade("false_memory", f"declines, then guesses: \"{guess[:80]}\"")
    return Grade("right", "declined: it was never told")


def resolve_timeline(spec: dict, cut: int | None = None) -> dict | None:
    """A changed fact's timeline as an exact spec at ``cut`` tokens (None: the whole script), or None when it is not
    askable there. "Now" needs at least one change seen; a past date needs that day to be over."""
    seen = [v for v in spec["values"] if cut is None or v["tokens"] <= cut]
    day = spec.get("on_day")
    if day is None:
        if len(seen) < 2:
            return None
        right = seen[-1]
    else:
        if cut is not None and spec.get("day_over_at") is not None and spec["day_over_at"] > cut:
            return None
        before = [v for v in seen if v["day"] <= day]
        if not before:
            return None
        right = before[-1]
    stale = [a for v in seen if v is not right for a in v["accept"]]
    return {"type": "exact", "accept": right["accept"], "stale": stale}


def grade(probe: dict, answer_text: str, browser: bool = False) -> Grade:
    """The verdict on ``answer_text`` for ``probe`` (see the module docstring). ``browser`` also loads a page answer
    in a headless browser; it is skipped with a note if none is installed."""
    spec = probe["grader"]
    kind = spec["type"]
    if kind == "timeline":
        spec = resolve_timeline(spec)
        if spec is None:
            raise ValueError(f"{probe['id']} is not askable on the whole script")
        kind = "exact"
    if kind == "exact":
        return grade_exact(spec, answer_text, probe.get("ask"))
    if kind == "number":
        return grade_number(spec, answer_text)
    if kind == "page":
        return grade_page(spec, answer_text, browser)
    if kind == "code":
        return grade_code(spec, answer_text)
    if kind == "never":
        return grade_never(answer_text, spec, probe.get("ask"))
    raise ValueError(f"unknown grader {kind}")
