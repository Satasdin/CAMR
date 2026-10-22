"""Arithmetic for skills: the calculator a model's written expression is evaluated with, and the prompts that ask
for one (moved from scripts/math_learning.py, which the formula experiments F27 and F32 ran with, so CAMR Personal
reads a skill card's answer exactly as those experiments did).

A small model is taught the procedure (the formula, by a note or a skill card); the arithmetic is the calculator's:
the model writes one expression after '####', and ``read_answer`` evaluates it safely (numbers, + - * / **, sqrt,
comb, factorial, round; an equation in one unknown is solved).
"""

from __future__ import annotations

import ast
import math
import operator
import re

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod}
_FUNCS = {"sqrt": math.sqrt, "comb": math.comb, "factorial": math.factorial, "round": round, "abs": abs,
          "C": math.comb}


def _clean(expr: str) -> str:
    expr = expr.strip().rstrip(".").replace("^", "**").replace("×", "*").replace("÷", "/").replace("$", "")
    return re.sub(r"(?<=\d),(?=\d{3}\b)", "", expr)  # 1,200 -> 1200


def calculate(expr: str, x: float | None = None, var: str = "x") -> float | None:
    """Evaluate an arithmetic expression safely (numbers, + - * / ** ( ), sqrt, comb, factorial, round), with
    ``var`` standing for ``x`` when a value is passed."""
    expr = _clean(expr)
    if not expr or len(expr) > 300:
        return None

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name) and node.id == var and x is not None:
            return x
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("exponent too large")
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
            return _FUNCS[node.func.id](*[ev(a) for a in node.args])
        raise ValueError(f"not allowed: {ast.dump(node)[:40]}")

    try:
        v = ev(ast.parse(expr, mode="eval"))
        return float(v)
    except Exception:  # noqa: BLE001
        return None



def solve(lhs: str, rhs: str, var: str = "x") -> float | None:
    """The value of ``var`` that makes lhs = rhs (the model writes the formula forward with a letter for the
    unknown; the calculator does the algebra). Scans for sign changes, then bisects; the smallest non-negative root
    wins (amounts, speeds and counts are not negative), else the root nearest zero."""
    def f(v):
        a, b = calculate(lhs, v, var), calculate(rhs, v, var)
        return None if a is None or b is None or not (math.isfinite(a) and math.isfinite(b)) else a - b

    grid = sorted({0.0} | {s * 10 ** (e / 20) for e in range(-60, 141) for s in (1, -1)})
    roots, prev = [], None
    for v in grid:
        fv = f(v)
        if fv is None:
            prev = None
            continue
        if fv == 0:
            roots.append(v)
        elif prev is not None and (prev[1] < 0) != (fv < 0):
            lo, hi, flo = prev[0], v, prev[1]
            for _ in range(200):
                mid = (lo + hi) / 2
                fm = f(mid)
                if fm is None:
                    break
                if (fm < 0) == (flo < 0):
                    lo, flo = mid, fm
                else:
                    hi = mid
            fm = f((lo + hi) / 2)
            if fm is not None and abs(fm) <= 1e-6 * max(1.0, abs(calculate(rhs, (lo + hi) / 2, var) or 1.0)):
                roots.append((lo + hi) / 2)
        prev = (v, fv)
    if not roots:
        return None
    pos = [r for r in roots if r >= 0]
    return min(pos) if pos else min(roots, key=abs)


_NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")


def numbers(text: str) -> list[float]:
    return [float(m.replace(",", "")) for m in _NUM.findall(text.replace("$", " ")) if m.replace(",", "")]


_PERCENT = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*(?:%|per ?cent)")


def grounded(expr: str, question: str) -> bool:
    """Does the expression use the problem's own numbers? Every number the question gives must appear in it (a
    percentage may appear as a fraction). An expression that leaves one out was usually copied from a worked
    example with its numbers, the failure that looks like learning but is memorisation."""
    have = numbers(_clean(expr))
    pct = {float(m.replace(",", "")) for m in _PERCENT.findall(question.replace("$", " "))}
    for q in numbers(question):
        forms = (q, q / 100) if q in pct else (q,)
        if not any(math.isclose(h, v, rel_tol=1e-9, abs_tol=1e-9) for h in have for v in forms):
            return False
    return True

REASON_BARE = ("Solve the problem. Show brief working, then give the final numeric answer on the last line in the form "
               "'#### <number>'.\n\nProblem: {question}\n")
REASON_MEM = ("Use the notes below if they are relevant. Solve the problem. Show brief working, then give the final "
              "numeric answer on the last line in the form '#### <number>'.\n\nNotes:\n{context}\n\nProblem: "
              "{question}\n")
_CALC = ("Solve the problem. Write the formula you use in one short line of plain text (no LaTeX), then on the last "
         "line write '#### ' followed by ONE arithmetic expression with the numbers put in, for example "
         "'#### 3*12 + 5' for 'three boxes of 12 eggs and 5 loose eggs'. Use the problem's numbers and the formula's "
         "constants, with only + - * / ** and parentheses (sqrt(x) and comb(n, k) are allowed). Do not work the arithmetic out: a calculator will "
         "evaluate the expression. If the problem gives the result and asks for a value that goes into the formula, "
         "write the formula as an equation with x for the unknown, for example '#### 2*x + 4 = 19' for 'a number "
         "doubled plus 4 is 19': the calculator solves it.")
CALC_BARE = _CALC + "\n\nProblem: {question}\n"
CALC_MEM = "Use the notes below if they are relevant. " + _CALC + "\n\nNotes:\n{context}\n\nProblem: {question}\n"


_LATEX = [(r"\\[()\[\]]", " "), (r"\\text\{[^}]*\}", " "), (r"\\(?:times|cdot)", "*"), (r"\\div", "/"),
          (r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"((\1)/(\2))"), (r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)"),
          (r"\\(?:approx|left|right|,|!|;|quad)", " "), (r"[{}]", "")]


def plain(text: str) -> str:
    for pat, rep in _LATEX:
        text = re.sub(pat, rep, text)
    return text


def _line_value(line: str) -> tuple[float | None, str]:
    """The value of one '####' line and the expression it came from. An equation in x is solved; otherwise the
    parts between '=' are tried left to right ("A = 800*(1+4/100)**4 = 960.00": the expression is trusted, not the
    model's own arithmetic)."""
    parts = [p for p in line.split("=") if p.strip()]
    names = set(re.findall(r"(?<![A-Za-z_\d.])([A-Za-z_]\w*)(?![\w(])", _clean(line))) - set(_FUNCS)
    if len(parts) == 2 and len(names) == 1:  # an equation in one unknown ("26 = 2*w + 8**2/4"): solve it
        return solve(parts[0], parts[1], names.pop()), line
    for part in parts:
        part = re.sub(r"^\s*[A-Za-z_][A-Za-z_ ]*$", "", part)
        if not re.search(r"\d", part):
            continue
        v = calculate(part)
        if v is not None:
            return v, part
    return None, ""


def read_answer(text: str, mode: str, question: str = "") -> tuple[float | None, bool]:
    """The answer a generation gives, and whether it is grounded in the problem's own numbers.

    In calc mode, every '####' line is a candidate: the last one built from the problem's numbers wins (a small
    model sometimes also writes out the worked example it read); if none is, the last one that evaluates, marked
    ungrounded. Otherwise, or if no expression evaluates, the last number (ungrounded in calc mode)."""
    from camr.eval.scoring import final_number

    text = plain(text)
    if mode == "calc" and "####" in text:
        found = []
        for chunk in text.split("####")[1:]:
            line = chunk.strip().splitlines()[0] if chunk.strip() else ""
            v, expr = _line_value(line)
            if v is not None and math.isfinite(v):
                found.append((v, grounded(expr, question) if question else False))
        for v, ok in reversed(found):
            if ok:
                return v, True
        if found:
            return found[-1][0], False
    n = final_number(text)
    return (float(n) if n is not None else None), mode != "calc" and n is not None


def final_value(text: str, mode: str, question: str = "") -> float | None:
    return read_answer(text, mode, question)[0]


def correct(pred: float | None, gold: float) -> bool:
    return pred is not None and math.isfinite(pred) and abs(pred - gold) <= max(0.011, 0.002 * abs(gold))
