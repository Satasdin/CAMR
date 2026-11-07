"""The fact check: every checkable fact in what a model wrote must already be in what it was told.

A small model invents: asked for a café's site it writes a menu, prices and a phone number that exist nowhere. Asking
it not to helps little, so the check does not rely on the model. It reads the written text, pulls out what can be
checked by rule (money, phone numbers, e-mail addresses, times of day, hex colours, plain numbers and names) and looks
each one up in the source: the notes the model read. What is not found is ``invented``.

It is deliberately simple: exact facts only, normalised so "KES 1,200", "Ksh 1200" and "1200 shillings" are one price
and "7am", "7:00 AM" and "07:00" one time. It cannot tell whether a sentence is true, only whether its checkable facts
came from somewhere. A fact the model copied from the notes passes even if used wrongly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MONEY = re.compile(r"(?:KES|KSH|KSHS|Kshs?\.?|Ksh|USD|US\$|\$|€|£)\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:KES|Ksh|shillings|bob)\b",
                   re.I)
PHONE = re.compile(r"(?<![\w#])(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)\d{3}[\s-]?\d{3,4}(?!\w)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
TIME = re.compile(r"\b\d{1,2}(?::\d{2})?\s?(?:a\.?m\.?|p\.?m\.?)(?![a-z])|\b\d{1,2}:\d{2}\b", re.I)
HEX = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")
URL = re.compile(r"https?://[^\s\"'<>)]+|www\.[^\s\"'<>)]+")
NUMBER = re.compile(r"(?<![\w#.,:-])\d[\d,]*(?:\.\d+)?(?![\w:])")
NAME = re.compile(r"\b[A-Z][a-zA-Z'’]+(?:\s+[A-Z][a-zA-Z'’]+)+")
COMMON_NAMES = {"Opening Hours", "Our Menu", "Contact Us", "Find Us", "Visit Us", "About Us", "All Rights Reserved",
                "Get In Touch", "Monday To", "Welcome To", "Add To Cart", "Order Now", "Your Order", "The Menu",
                "Follow Us", "Book Now", "Call Us", "Menu Items", "Our Story", "Your Cart"}


@dataclass(frozen=True)
class Fact:
    kind: str  # money, phone, email, time, colour, url, number or name
    text: str  # as written
    key: str  # as compared


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _money(s: str) -> str:
    n = re.search(r"\d[\d,]*(?:\.\d+)?", s)
    value = float(n.group(0).replace(",", "")) if n else 0.0
    return f"{value:g}"


def _time(s: str) -> str:
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s?(a|p)?", s.lower())
    if not m:
        return s.lower()
    h, mins, half = int(m.group(1)), m.group(2) or "00", m.group(3)
    if half == "p" and h < 12:
        h += 12
    if half == "a" and h == 12:
        h = 0
    return f"{h:02d}:{mins}"


def _phone(s: str) -> str:
    d = _digits(s)
    return d[-9:] if len(d) >= 9 else d


def facts_in(text: str, *, names: bool = False, numbers: bool = False) -> list[Fact]:
    """The checkable facts in a text, each once. ``names`` adds capitalised names of two words or more, ``numbers``
    plain numbers of two digits or more that are not part of something already found."""
    out: dict[tuple[str, str], Fact] = {}
    taken: list[tuple[int, int]] = []

    def add(kind: str, pattern: re.Pattern, key) -> None:
        for m in pattern.finditer(text):
            if any(a < m.end() and m.start() < b for a, b in taken):
                continue
            taken.append(m.span())
            f = Fact(kind, m.group(0).strip().rstrip("."), key(m.group(0)))
            out.setdefault((kind, f.key), f)

    add("url", URL, lambda s: s.lower().rstrip("/."))
    add("email", EMAIL, str.lower)
    add("money", MONEY, _money)
    add("colour", HEX, str.lower)
    add("time", TIME, _time)
    add("phone", PHONE, _phone)
    if numbers:
        for m in NUMBER.finditer(text):
            if any(a < m.end() and m.start() < b for a, b in taken) or len(_digits(m.group(0))) < 2:
                continue
            f = Fact("number", m.group(0), _money(m.group(0)))
            out.setdefault(("number", f.key), f)
    if names:
        for m in NAME.finditer(text):
            name = re.sub(r"['’]s?$", "", m.group(0))  # Kahawa Corner's is Kahawa Corner
            if name.title() in COMMON_NAMES:
                continue
            f = Fact("name", name, name.lower())
            out.setdefault(("name", f.key), f)
    return list(out.values())


def _index(source: str) -> dict[str, set[str]]:
    found = facts_in(source, numbers=True)
    index: dict[str, set[str]] = {}
    for f in found:
        index.setdefault(f.kind, set()).add(f.key)
    numbers = index.setdefault("number", set())
    numbers |= index.get("money", set())  # "180" in the notes backs "KES 180" on the page, and the other way round
    for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", source):
        numbers.add(_money(m.group(0)))
    return index


def invented(written: str, source: str, *, names: bool = False, numbers: bool = False) -> list[Fact]:
    """The facts in ``written`` that are nowhere in ``source``."""
    index = _index(source)
    low = " ".join(source.lower().split())
    out = []
    for f in facts_in(written, names=names, numbers=numbers):
        if f.kind == "name":
            ok = f.key in low
        elif f.kind == "money":
            ok = f.key in index.get("money", set()) or f.key in index.get("number", set())
        elif f.kind == "number":
            ok = f.key in index.get("number", set())
        elif f.kind == "time":
            ok = f.key in index.get("time", set())
        elif f.kind == "phone":
            ok = f.key in index.get("phone", set()) or f.key in {_phone(x) for x in index.get("number", set())}
        else:
            ok = f.key in index.get(f.kind, set()) or f.key in low
        if not ok:
            out.append(f)
    return out


def answer_check(answer: str, notes: list[str]) -> dict:
    """An answer from memory against the notes it read: {checked, grounded, invented: [text]}."""
    source = "\n".join(notes)
    # money, phones, times and names; not plain numbers, as a right sum is not in the notes and is not made up
    found = facts_in(answer, names=True)
    bad = invented(answer, source, names=True)
    return {"checked": len(found), "grounded": len(found) - len(bad), "invented": [f.text for f in bad]}
