"""Dates in notes and periods in questions (``dated_context``, ``time_filter``), by rule and model-free.

A chat note carries the day it was said ("On 2026-10-13 the user said: ..."); a question may name a period
("last week", "in March", "two days ago"). Periods are read generously (where "last week" may mean the previous
calendar week or the past seven days, the window covers both), because a note wrongly dropped costs more than one
wrongly kept. Questions about the future ("for Friday", "next week") name no period here.
"""

from __future__ import annotations

import calendar
import datetime as dt
import re

_SAID = re.compile(r"^\s*On (\d{4})-(\d{2})-(\d{2}) the (user|assistant) said:\s*")
_BRACKET = re.compile(r"^\s*\[(\d{4})-(\d{2})-(\d{2})\]\s*")
_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
_WEEKDAYS = {d.lower(): i for i, d in enumerate(calendar.day_name)}
_NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
        "nine": 9, "ten": 10, "couple of": 2, "few": 3}
_N = r"(\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|couple of|few)"


def split_said(text: str) -> tuple[dt.date | None, str | None, str]:
    """("On 2026-10-13 the user said: X") -> (2026-10-13, "user", "X"); other text -> (None, None, text)."""
    m = _SAID.match(text)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))), m.group(4), text[m.end():]
        except ValueError:
            pass
    m = _BRACKET.match(text)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))), None, text[m.end():]
        except ValueError:
            pass
    return None, None, text


def note_date(text: str) -> dt.date | None:
    return split_said(text)[0]


def _month_window(year: int, month: int) -> tuple[dt.date, dt.date]:
    return dt.date(year, month, 1), dt.date(year, month, calendar.monthrange(year, month)[1])


def _monday(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def _n(word: str) -> int:
    return int(word) if word.isdigit() else _NUM[word]


def _shift_months(d: dt.date, months: int) -> dt.date:
    y, m = divmod(d.year * 12 + d.month - 1 - months, 12)
    return dt.date(y, m + 1, min(d.day, calendar.monthrange(y, m + 1)[1]))


_PAST = re.compile(r"\b(?:did|was|were|had|have|has|ago|last|yesterday|since|previous|earlier|used to)\b"
                   r"|\b\w{3,}ed\b", re.I)


def period(question: str, today: dt.date) -> tuple[dt.date, dt.date] | None:
    """The span of days a question asks about, as (start, today), or None.

    Only a question about the past names a period ("What did the electrician fix last week?"); "a show for
    tonight" or "rearranging my bedroom this weekend" ask for plans, so the notes they need may be from any day.
    The span always ends today: a note said after the period may tell of it ("last Thursday I earned ..."), so the
    filter drops only notes said before the period began."""
    q = question.lower()
    if re.search(r"\b(?:next|tomorrow|upcoming|coming|will|tonight|today|this weekend)\b", q) or not _PAST.search(q):
        return None
    start: dt.date | None = None
    m_past = re.search(rf"\b(?:in the |over the |during the )?(?:past|last) {_N} (day|week|month|year)s?\b", q)
    m_ago = re.search(rf"\b{_N} (day|week|month)s? ago\b", q)
    m_day = re.search(r"\blast (" + "|".join(_WEEKDAYS) + r")\b", q)
    names = "|".join(m.capitalize() for m in _MONTHS)
    m_month = re.search(rf"(?:\b(in|during|of|for|since)\s+)?\b({names})\b(?:\s+(\d{{4}}))?", question)
    if re.search(r"\byesterday\b", q):
        start = today - dt.timedelta(days=1)
    elif m_past:
        n, unit = _n(m_past.group(1)), m_past.group(2)
        start = (today - dt.timedelta(days=n) if unit == "day" else today - dt.timedelta(weeks=n) if unit == "week"
                 else _shift_months(today, n) if unit == "month" else dt.date(today.year - n, today.month, 1))
    elif m_ago:
        n, unit = _n(m_ago.group(1)), m_ago.group(2)
        start = (today - dt.timedelta(days=n + 1) if unit == "day" else today - dt.timedelta(weeks=n, days=4)
                 if unit == "week" else _shift_months(today, n).replace(day=1))
    elif re.search(r"\blast week(?:end)?\b", q):
        start = _monday(today) - dt.timedelta(days=7)
    elif re.search(r"\bthis week\b", q):
        start = _monday(today)
    elif re.search(r"\blast month\b", q):
        start = _shift_months(today.replace(day=1), 1)
    elif re.search(r"\bthis month\b", q):
        start = today.replace(day=1)
    elif re.search(r"\blast year\b", q):
        start = dt.date(today.year - 1, 1, 1)
    elif re.search(r"\bthis year\b", q):
        start = dt.date(today.year, 1, 1)
    elif m_day:  # "last Thursday": the most recent Thursday, or the one before it (people say both)
        start = today - dt.timedelta(days=((today.weekday() - _WEEKDAYS[m_day.group(1)]) % 7 or 7) + 8)
    elif m_month:  # a month by name, capitalised; "May" only after in/during/of/for/since or with a year
        prep, name, year = (m_month.group(1) or "").lower(), m_month.group(2).lower(), m_month.group(3)
        if name == "may" and not year and not prep:
            return None
        month = _MONTHS[name]
        y = int(year) if year else today.year if month <= today.month else today.year - 1
        start = dt.date(y, month, 1)
    if start is None or start > today:
        return None
    return start, today
