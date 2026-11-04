"""Checking a maths answer: take the final answer out of a reply, then test it against the right one.

The order of checks follows HARP's checker (``latex_answer_check.py``, itself after Xwin-Math and ToRA): the same
text once normalised; then tuples, intervals, sets and lists part by part; then equal value or equal expression with
sympy. The LaTeX is turned into sympy by this module's own small converter, and only whitelisted names ever reach
sympy's parser, so a reply can never run code.
"""

from __future__ import annotations

import re
import signal
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from camr_engine.bench.suites.common import clean

TIMEOUT_S = 2.0
MAX_EXPR = 400  # longer expressions go to the text check only


# ---------------------------------------------------------------- taking the answer out of a reply

def _group(text: str, start: int) -> tuple[str, int] | None:
    """The brace group opening at ``text[start] == '{'``: its inside and the index after it."""
    depth = 0
    for k in range(start, len(text)):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:k], k + 1
    return None


def boxed(text: str) -> list[str]:
    """Every \\boxed{...} (or \\fbox{...}) in the text, in order."""
    out = []
    for m in re.finditer(r"\\(?:boxed|fbox)\s*", text):
        k = m.end()
        if k < len(text) and text[k] == "{":
            g = _group(text, k)
            if g:
                out.append(g[0])
        elif k < len(text):  # \boxed 5
            tok = re.match(r"[^\s$.,]+", text[k:])
            if tok:
                out.append(tok.group(0))
    return out


_PHRASE = re.compile(r"(?:final answer is|the answer is|answer\s*[:=])\s*:?\s*(.+)", re.I)


def extract(reply: str | None) -> str | None:
    """The final answer: the last \\boxed{}, else what follows "final answer is" / "Answer:", else a short reply
    whole. None when there is nothing to take."""
    text = clean(reply)
    if not text:
        return None
    boxes = boxed(text)
    if boxes:
        return boxes[-1].strip()
    found = None
    for line in text.splitlines():
        m = _PHRASE.search(line)
        if m:
            found = m.group(1)
    if found is not None:
        found = found.strip().strip("*").strip()
        found = re.sub(r"^\$+|\$+$", "", found).strip()
        found = re.sub(r"^\\\(|\\\)$|^\\\[|\\\]$", "", found).strip()
        return found.rstrip(".").strip() or None
    if len(text) <= 40 and "\n" not in text:
        return text.rstrip(".").strip() or None
    return None


# ---------------------------------------------------------------- normalising

_TEXT_CMDS = ("text", "textbf", "textit", "mathrm", "mathbf", "mbox", "operatorname", "textnormal")
_SPACES = (r"\!", r"\,", r"\;", r"\:", r"\ ", r"\quad", r"\qquad", "~")


def _unwrap(text: str, cmds: tuple[str, ...], keep: bool = True) -> str:
    """\\cmd{inside} -> inside (or nothing when ``keep`` is False)."""
    pat = re.compile(r"\\(" + "|".join(cmds) + r")\s*(?=\{)")
    while True:
        m = pat.search(text)
        if not m:
            return text
        g = _group(text, m.end())
        if not g:
            return text[: m.start()] + text[m.end():]
        text = text[: m.start()] + (g[0] if keep else " ") + text[g[1]:]


def tidy(text: str) -> str:
    """LaTeX without the parts that never change a value: dollars, \\left/\\right, spacing, \\dfrac, degrees,
    percent and currency signs, thousands commas, trailing full stops."""
    t = text.strip()
    t = re.sub(r"^\$+|\$+$", "", t).strip()
    t = re.sub(r"^\\\(|\\\)$|^\\\[|\\\]$", "", t).strip()
    t = t.replace("\\\\", "\x00")  # a matrix's row break is not a space
    for s in _SPACES:
        t = t.replace(s, " ")
    t = t.replace("\x00", "\\\\")
    t = t.replace("\\left", "").replace("\\right", "").replace("\\displaystyle", "")
    t = t.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    t = re.sub(r"\^\s*\{\s*\\circ\s*\}|\^\s*\\circ|°|\\circ|\\degree", "", t)
    t = t.replace("\\%", "").replace("%", "").replace("\\$", "").replace("$", "").replace("\\textdollar", "")
    t = t.replace("{,}", "")
    t = t.replace("\\{", "\\lbrace ").replace("\\}", " \\rbrace")
    t = t.replace("π", "\\pi").replace("∞", "\\infty").replace("√", "\\sqrt")
    t = re.sub(r"\\(?:hspace|vspace)\s*\{[^}]*\}", "", t)
    if re.fullmatch(r"[-+]?\d{1,3}(,\d{3})+(\.\d+)?", t.replace(" ", "")):
        t = t.replace(",", "")
    return t.strip().rstrip(".").strip()


def _drop_lhs(t: str) -> str:
    """"x = 5" -> "5" when the left side is just a name; "y = 2x + 3" stays an equation only if both are."""
    if t.count("=") == 1:
        left, right = t.split("=")
        if re.fullmatch(r"\s*[A-Za-z](?:_\{?\w+\}?)?(?:\([A-Za-z]\))?\s*", left):
            return right.strip()
    return t


def as_text(text: str) -> str:
    """A form for comparing as plain text: tidy, text commands opened, lowercase, no spaces."""
    t = _unwrap(tidy(text), _TEXT_CMDS)
    t = _drop_lhs(t)
    t = re.sub(r"\s+", "", t).lower().replace("\\lbrace", "{").replace("\\rbrace", "}")
    return t.rstrip(".")


# ---------------------------------------------------------------- structure: tuples, intervals, sets, lists

def _split_top(t: str, sep: str = ",") -> list[str]:
    parts, depth, cur, k = [], 0, "", 0
    while k < len(t):
        if t.startswith("\\lbrace", k):
            depth += 1
            cur += "\\lbrace"
            k += 7
            continue
        if t.startswith("\\rbrace", k):
            depth -= 1
            cur += "\\rbrace"
            k += 7
            continue
        c = t[k]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        if depth == 0 and t.startswith(sep, k):
            parts.append(cur)
            cur = ""
            k += len(sep)
            continue
        cur += c
        k += 1
    parts.append(cur)
    return [p.strip() for p in parts]


def _closes(t: str, k: int = 0) -> int:
    """Index of the bracket closing the one at ``t[k]``."""
    depth = 0
    for j in range(k, len(t)):
        if t[j] in "([{":
            depth += 1
        elif t[j] in ")]}":
            depth -= 1
            if depth == 0:
                return j
    return -1


def structure(text: str) -> tuple[str, list[str]] | None:
    """("union", intervals), ("set", items), ("tuple"/"interval" with its brackets, items), ("matrix", rows) or
    ("list", items) for an answer with parts; None for one value."""
    t = tidy(text)
    t = re.sub(r"^\s*[A-Za-z]\s*\\in\s*", "", t)
    m = re.fullmatch(r"\\begin\{[pbv]?matrix\}(.*)\\end\{[pbv]?matrix\}", t.strip(), re.S)
    if m:
        rows = [r for r in re.split(r"\\\\", m.group(1)) if r.strip()]
        return "matrix", [",".join(c.strip() for c in r.split("&")) for r in rows]
    if "\\cup" in t:
        parts = _split_top(t, "\\cup")
        if len(parts) > 1:
            return "union", parts
    s = t.strip()
    if s.startswith("\\lbrace") and s.endswith("\\rbrace"):
        return "set", [p for p in _split_top(s[7:-7].strip()) if p]
    if len(s) > 2 and s[0] in "([" and s[-1] in ")]" and _closes(s) == len(s) - 1:
        inner = _split_top(s[1:-1])
        if len(inner) > 1:
            return ("interval" if len(inner) == 2 else "tuple"), [s[0] + s[-1], *inner]
    parts = _split_top(s)
    if len(parts) > 1 and all(parts):
        return "list", parts
    return None


# ---------------------------------------------------------------- LaTeX to sympy, safely

_NAMES = {"sqrt", "pi", "oo", "log", "ln", "sin", "cos", "tan", "sec", "csc", "cot", "exp", "asin", "acos", "atan",
          "Abs"}
_LATEX_FUNCS = {"\\sin": "sin", "\\cos": "cos", "\\tan": "tan", "\\sec": "sec", "\\csc": "csc", "\\cot": "cot",
                "\\ln": "log", "\\log": "log", "\\exp": "exp", "\\arcsin": "asin", "\\arccos": "acos",
                "\\arctan": "atan"}


def _arg(t: str, k: int) -> tuple[str, int] | None:
    """One argument at ``t[k]``: a brace group, or a single character."""
    while k < len(t) and t[k] == " ":
        k += 1
    if k >= len(t):
        return None
    if t[k] == "{":
        return _group(t, k)
    return t[k], k + 1


def to_sympy_text(text: str) -> str | None:
    """LaTeX turned into sympy's syntax, or None when it holds anything this converter doesn't know."""
    t = _drop_lhs(tidy(text))
    unit = re.compile(r"\\(?:" + "|".join(_TEXT_CMDS) + r")\s*\{[^{}]*\}\s*$")
    while unit.search(t):  # units at the end go: "5\text{ cm}" -> "5"; words inside stay, so it can't be read
        t = unit.sub("", t).strip()
    t = re.sub(r"(?<![\d.])(\d+)\s*\\frac\s*\{(\d+)\}\s*\{(\d+)\}", r"(\1+\\frac{\2}{\3})", t)  # 3\frac{1}{2}
    for k, v in _LATEX_FUNCS.items():
        t = re.sub(re.escape(k) + r"(?![a-zA-Z])", v, t)
    t = t.replace("\\pi", " pi ").replace("\\infty", " oo ").replace("\\cdot", "*").replace("\\times", "*")
    t = t.replace("\\div", "/").replace("\\lbrace", "(").replace("\\rbrace", ")").replace("\\mid", "|")
    for _ in range(50):
        m = re.search(r"\\frac|\\sqrt", t)
        if not m:
            break
        if m.group(0) == "\\frac":
            a = _arg(t, m.end())
            b = _arg(t, a[1]) if a else None
            if not b:
                return None
            t = t[: m.start()] + f"(({a[0]})/({b[0]}))" + t[b[1]:]
        else:
            k = m.end()
            root = None
            if k < len(t) and t[k] == "[":
                j = t.find("]", k)
                if j < 0:
                    return None
                root, k = t[k + 1:j], j + 1
            a = _arg(t, k)
            if not a:
                return None
            t = t[: m.start()] + (f"(({a[0]})**(1/({root})))" if root else f"sqrt({a[0]})") + t[a[1]:]
    if "\\" in t:
        return None
    t = t.replace("{", "(").replace("}", ")").replace("^", "**")
    if not re.fullmatch(r"[0-9A-Za-z+\-*/().| ]*", t) or not t.strip():
        return None

    def names(m: re.Match) -> str:  # a run of letters is a known name, or single letters multiplied
        w = m.group(0)
        if w in _NAMES:
            return f" {w} "
        out, k = [], 0
        while k < len(w):
            for n in sorted(_NAMES, key=len, reverse=True):
                if w.startswith(n, k):
                    out.append(n)
                    k += len(n)
                    break
            else:
                out.append(w[k])
                k += 1
        return " " + "*".join(out) + " "

    t = re.sub(r"[A-Za-z]+", names, t)
    t = re.sub(r"\|([^|]*)\|", r"Abs(\1)", t)
    return None if "|" in t else t


class _Timeout(Exception):
    pass


@contextmanager
def _limit(seconds: float) -> Iterator[None]:
    """A time limit for sympy (only on the main thread, where signals work)."""
    if threading.current_thread() is not threading.main_thread() or not hasattr(signal, "SIGALRM"):
        yield
        return

    def ring(*_: Any) -> None:
        raise _Timeout

    old = signal.signal(signal.SIGALRM, ring)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def parse(text: str) -> Any | None:
    """A sympy expression for a LaTeX answer, or None."""
    s = to_sympy_text(text)
    if s is None or len(s) > MAX_EXPR or re.search(r"\*\*\s*\(*\s*\d{5,}|\*\*[^*]*\*\*[^*]*\*\*", s):
        return None  # towers and huge powers could run for ever
    import sympy
    from sympy.parsing.sympy_parser import (implicit_multiplication_application, parse_expr, rationalize,
                                            standard_transformations)

    names = {n: getattr(sympy, n) for n in _NAMES - {"ln"}}
    names.update({"ln": sympy.log, "i": sympy.I, "e": sympy.E, "E": sympy.E, "I": sympy.I})
    glob = {"__builtins__": {}, "Integer": sympy.Integer, "Float": sympy.Float, "Rational": sympy.Rational,
            "Symbol": sympy.Symbol}
    try:
        with _limit(TIMEOUT_S):
            return parse_expr(s, local_dict=names, global_dict=glob,
                              transformations=standard_transformations + (implicit_multiplication_application,
                                                                          rationalize))
    except (_Timeout, Exception):
        return None


def _close(x: Any, y: Any) -> bool:
    """Two sympy numbers equal to nine significant figures, worked in sympy's own precision (no float overflow)."""
    import sympy

    d, m = sympy.N(x - y, 40), sympy.N(y, 40)
    if d.has(sympy.nan, sympy.zoo, sympy.oo, -sympy.oo):
        return False
    return bool(abs(d) <= sympy.Float("1e-9") * sympy.Max(1, abs(m)))


def same_value(a: Any, b: Any) -> bool:
    """Equal numbers, or expressions equal everywhere: a zero difference, or equal at a few fixed points."""
    import sympy

    try:
        with _limit(TIMEOUT_S):
            if a == b:
                return True
            if a.has(sympy.oo, -sympy.oo, sympy.zoo) or b.has(sympy.oo, -sympy.oo, sympy.zoo):
                return bool(sympy.simplify(a - b) == 0)
            free = sorted(a.free_symbols | b.free_symbols, key=str)
            if not free:
                return _close(a, b)
            if sympy.simplify(a - b) == 0:
                return True
            for point in ((0.37, 1.13, 2.71, 0.59), (1.71, 0.23, 3.07, 1.41), (2.29, 1.83, 0.41, 2.17)):
                sub = {s: sympy.Rational(point[k % len(point)]).limit_denominator(1000) + sympy.Rational(k // 4, 10)
                       for k, s in enumerate(free)}
                if not _close(a.subs(sub), b.subs(sub)):
                    return False
            return True
    except (_Timeout, Exception):
        return False


# ---------------------------------------------------------------- the check

def _match_parts(xs: list[str], ys: list[str], ordered: bool) -> bool:
    if len(xs) != len(ys):
        return False
    if ordered:
        return all(equivalent(x, y) for x, y in zip(xs, ys))
    left = list(ys)
    for x in xs:
        for k, y in enumerate(left):
            if equivalent(x, y):
                del left[k]
                break
        else:
            return False
    return True


def equivalent(answer: str | None, gold: str) -> bool:
    """Whether ``answer`` (already taken out of the reply) means the same as ``gold``."""
    if answer is None or not answer.strip():
        return False
    a, g = as_text(answer), as_text(gold)
    if a == g:
        return True
    letter = re.compile(r"\(?([a-e])\)?")
    if letter.fullmatch(a) and letter.fullmatch(g):  # multiple choice: "(C)" and "C"
        return letter.fullmatch(a).group(1) == letter.fullmatch(g).group(1)
    sa, sg = structure(answer), structure(gold)
    if sa or sg:
        if not (sa and sg):
            return False
        (ka, xa), (kg, xg) = sa, sg
        if {ka, kg} <= {"interval", "tuple"} and ka != kg:
            return False
        if ka != kg and {ka, kg} != {"set", "list"}:
            return False
        if ka in ("interval", "tuple"):
            if ka == "interval" and xa[0] != xg[0]:  # (1, 2] is not [1, 2]
                return False
            return _match_parts(xa[1:], xg[1:], ordered=True)
        if ka == "matrix":
            return len(xa) == len(xg) and all(_match_parts(_split_top(r), _split_top(s), ordered=True)
                                              for r, s in zip(xa, xg))
        return _match_parts(xa, xg, ordered=False)  # union, set, list: any order
    x, y = parse(answer), parse(gold)
    if x is not None and y is not None:
        return same_value(x, y)
    return False


def check(reply: str | None, gold: str) -> tuple[bool, str | None]:
    """(right, the answer taken out of the reply)."""
    ans = extract(reply)
    return equivalent(ans, gold), ans
