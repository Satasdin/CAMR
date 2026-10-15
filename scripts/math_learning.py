"""Learning formulas from corrections: does what memory learns generalise, or is it memorised?

A frozen model answers maths problems from ten formula families. When it is wrong, it is
corrected once: the rule and a worked solution of *that* problem are stored in memory (the
engine's external weights; the model's own weights never change). It is then tested on problems
it has never seen, evaluated the way one checks a trained model for overfitting:

* splits: training problems (where corrections happen) and held-out problems (new numbers, never
  shown); a rephrased held-out set (other words); and derived problems the rule was never shown
  solving: the formula inverted or applied twice, which the model has to work out itself;
* a learning curve: held-out accuracy after 0, 1, 2, 4 and 6 training rounds;
* the generalisation gap: accuracy on the training problems (seen) minus held-out (unseen);
* a memorisation probe: how often a wrong held-out answer is a stored training answer;
* interference: GSM8K accuracy with and without the corrections in memory.

Four of the families are invented (a made-up operator, made-up units, a made-up fee rule and a
made-up score), so the model cannot have known them before it was corrected.

Two ways to answer: ``reason`` (the model works the arithmetic out itself) and ``calc`` (the
model writes the formula as one expression and the engine's calculator evaluates it: the model
sets the problem up, the calculator does the arithmetic it is bad at).

    python scripts/math_learning.py run --model qwen2.5:0.5b --mode calc
    python scripts/math_learning.py report
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import operator
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/math"
DEV_SEED = 31    # the draw the method was developed on (looked at, changed against)
SEED = 47        # a fresh draw, run once the method was frozen: the reported numbers


# ---------------------------------------------------------------------- the families
@dataclass
class Family:
    key: str
    invented: bool
    rule: str                                   # what a correction teaches
    params: Callable[[random.Random], dict]
    ask: Callable[[dict, int], str]             # wording 0 (training) or 1 (rephrased)
    solve: Callable[[dict], tuple[float, str]]  # answer and worked steps
    derive: Callable[[random.Random], tuple[str, float]]  # a problem the rule was never shown solving
    expr: Callable[[dict], str] = lambda x: ""  # the answer as one expression (a fine-tuning target)


def _r(x: float, d: int = 2) -> float:
    return round(x + 0.0, d)


def _ci_params(g):
    return {"p": g.choice([800, 1200, 1500, 2000, 2500, 3000, 4500]), "r": g.choice([3, 4, 5, 6, 7, 8]),
            "n": g.randint(3, 9)}


def _ci_solve(x):
    a = x["p"] * (1 + x["r"] / 100) ** x["n"]
    return _r(a), f"A = {x['p']} * (1 + {x['r']}/100)**{x['n']} = {_r(a)}"


def _ci_derive(g):
    x = _ci_params(g)
    a = _r(x["p"] * (1 + x["r"] / 100) ** x["n"])
    return (f"After {x['n']} years at {x['r']}% interest compounded yearly, an account holds ${a:,.2f}. "
            f"How much was deposited at the start (to the nearest dollar)?", float(x["p"]))


def _as_params(g):
    return {"a": g.randint(2, 15), "d": g.randint(2, 9), "n": g.randint(8, 30)}


def _as_solve(x):
    s = x["n"] * (2 * x["a"] + (x["n"] - 1) * x["d"]) / 2
    return s, f"S = {x['n']}/2 * (2*{x['a']} + ({x['n']}-1)*{x['d']}) = {s:g}"


def _as_derive(g):
    x = _as_params(g)
    s = x["n"] * (2 * x["a"] + (x["n"] - 1) * x["d"]) // 2
    return (f"The first {x['n']} terms of an arithmetic sequence add up to {s}. The first term is {x['a']}. "
            f"What is the common difference?", float(x["d"]))


def _gs_params(g):
    return {"a": g.randint(2, 6), "r": g.choice([2, 3]), "n": g.randint(4, 8)}


def _gs_solve(x):
    s = x["a"] * (x["r"] ** x["n"] - 1) / (x["r"] - 1)
    return s, f"S = {x['a']} * ({x['r']}**{x['n']} - 1) / ({x['r']} - 1) = {s:g}"


def _gs_derive(g):
    x = _gs_params(g)
    k = g.randint(2, x["n"] - 1)
    s = x["a"] * (x["r"] ** x["n"] - x["r"] ** (k - 1)) / (x["r"] - 1)
    return (f"A geometric sequence starts at {x['a']} and each term is {x['r']} times the one before. What is the sum "
            f"of the terms from term {k} to term {x['n']} (inclusive)?", s)


def _he_params(g):
    while True:
        a, b, c = g.randint(5, 20), g.randint(5, 20), g.randint(5, 20)
        if a + b > c and a + c > b and b + c > a:
            return {"a": a, "b": b, "c": c}


def _he_area(x):
    s = (x["a"] + x["b"] + x["c"]) / 2
    return math.sqrt(s * (s - x["a"]) * (s - x["b"]) * (s - x["c"]))


def _he_solve(x):
    s = (x["a"] + x["b"] + x["c"]) / 2
    return _r(_he_area(x)), (f"s = ({x['a']}+{x['b']}+{x['c']})/2 = {s:g}; area = sqrt({s:g}*({s:g}-{x['a']})*"
                             f"({s:g}-{x['b']})*({s:g}-{x['c']})) = {_r(_he_area(x))}")


def _he_derive(g):
    x = _he_params(g)
    h = 2 * _he_area(x) / x["c"]
    return (f"A triangle has sides {x['a']} cm, {x['b']} cm and {x['c']} cm. What is its height measured to the "
            f"{x['c']} cm side, to two decimal places?", _r(h))


def _cb_params(g):
    n = g.randint(7, 15)
    return {"n": n, "k": g.randint(2, min(5, n - 2))}


def _cb_solve(x):
    v = math.comb(x["n"], x["k"])
    return v, f"C({x['n']}, {x['k']}) = {x['n']}! / ({x['k']}! * {x['n'] - x['k']}!) = {v}"


def _cb_derive(g):
    n, m, k, j = g.randint(6, 10), g.randint(5, 9), g.randint(2, 3), g.randint(2, 3)
    return (f"A committee needs {k} people from a group of {n} engineers and {j} people from a group of {m} "
            f"designers. How many different committees are possible?", float(math.comb(n, k) * math.comb(m, j)))


def _ke_params(g):
    return {"m": g.choice([2, 4, 5, 8, 10, 12, 20, 50]), "v": g.randint(3, 25)}


def _ke_solve(x):
    e = 0.5 * x["m"] * x["v"] ** 2
    return e, f"KE = 0.5 * {x['m']} * {x['v']}**2 = {e:g}"


def _ke_derive(g):
    x = _ke_params(g)
    e = 0.5 * x["m"] * x["v"] ** 2
    return (f"An object of mass {x['m']} kg has a kinetic energy of {e:g} J. How fast is it moving, in m/s?",
            float(x["v"]))


# invented: the zorbit operator, a ⊛ b = 3a - 2b + ab
def _zo_params(g):
    return {"a": g.randint(2, 12), "b": g.randint(2, 12)}


def _zo(a, b):
    return 3 * a - 2 * b + a * b


def _zo_solve(x):
    v = _zo(x["a"], x["b"])
    return v, f"{x['a']} zorbit {x['b']} = 3*{x['a']} - 2*{x['b']} + {x['a']}*{x['b']} = {v}"


def _zo_derive(g):
    a, b, c = g.randint(2, 6), g.randint(2, 6), g.randint(2, 6)
    return f"Using the zorbit operation, what is ({a} zorbit {b}) zorbit {c}?", float(_zo(_zo(a, b), c))


# invented: glim, trell and pom (1 glim = 7 trell, 1 trell = 12 pom)
def _gl_params(g):
    return {"q": g.randint(2, 60)}


def _gl_solve(x):
    v = x["q"] * 7 * 12
    return v, f"{x['q']} glim * 7 trell/glim * 12 pom/trell = {v} pom"


def _gl_derive(g):
    q = g.randint(2, 19)
    t = g.randint(1, 6)
    return (f"A crate holds {q * 84 + t * 12} pom. How many glims is that, as a decimal to two places?",
            _r((q * 84 + t * 12) / 84))


# invented: the Kessler fee, 4% of the amount plus 2.50 per item
def _kf_params(g):
    return {"amount": g.choice([120, 250, 380, 640, 900, 1250, 1600]), "items": g.randint(1, 9)}


def _kf_solve(x):
    f = 0.04 * x["amount"] + 2.5 * x["items"]
    return _r(f), f"fee = 0.04 * {x['amount']} + 2.50 * {x['items']} = {_r(f)}"


def _kf_derive(g):
    x = _kf_params(g)
    f = _r(0.04 * x["amount"] + 2.5 * x["items"])
    return (f"An order of {x['items']} items was charged a Kessler fee of ${f:.2f}. What was the order amount in "
            f"dollars?", float(x["amount"]))


# invented: the Vantor score, V = 2w + h^2/4
def _vs_params(g):
    return {"w": g.randint(3, 40), "h": g.choice([2, 4, 6, 8, 10, 12])}


def _vs_solve(x):
    v = 2 * x["w"] + x["h"] ** 2 / 4
    return v, f"V = 2*{x['w']} + {x['h']}**2/4 = {v:g}"


def _vs_derive(g):
    x = _vs_params(g)
    v = 2 * x["w"] + x["h"] ** 2 / 4
    return f"A crop has a Vantor score of {v:g} and h = {x['h']}. What is its w?", float(x["w"])


FAMILIES = [
    Family("compound interest", False,
           "Compound interest: A = P * (1 + r/100)**n, where P is the starting amount, r the yearly rate in percent "
           "and n the number of years (interest compounded yearly).",
           _ci_params,
           lambda x, w: (f"${x['p']} is deposited at {x['r']}% interest compounded yearly. How much is in the account "
                         f"after {x['n']} years (to the cent)?" if w == 0 else
                         f"What does a deposit of ${x['p']} grow to in {x['n']} years if it earns {x['r']}% a year, "
                         f"compounded annually? Give the amount to the cent."),
           _ci_solve, _ci_derive, lambda x: f"{x['p']}*(1+{x['r']}/100)**{x['n']}"),
    Family("arithmetic series", False,
           "Sum of an arithmetic series: S = n/2 * (2a + (n - 1)d), where a is the first term, d the common difference "
           "and n the number of terms.",
           _as_params,
           lambda x, w: (f"What is the sum of the first {x['n']} terms of the arithmetic sequence that starts at "
                         f"{x['a']} and goes up by {x['d']} each time?" if w == 0 else
                         f"A sequence begins {x['a']}, {x['a'] + x['d']}, {x['a'] + 2 * x['d']}, ... (adding "
                         f"{x['d']} each time). Add up its first {x['n']} terms."),
           _as_solve, _as_derive, lambda x: f"{x['n']}/2*(2*{x['a']}+({x['n']}-1)*{x['d']})"),
    Family("geometric series", False,
           "Sum of a geometric series: S = a * (r**n - 1) / (r - 1), where a is the first term, r the ratio and n the "
           "number of terms.",
           _gs_params,
           lambda x, w: (f"What is the sum of the first {x['n']} terms of the geometric sequence with first term "
                         f"{x['a']} and ratio {x['r']}?" if w == 0 else
                         f"Starting from {x['a']} and multiplying by {x['r']} each step, add up the first {x['n']} "
                         f"numbers you get."),
           _gs_solve, _gs_derive, lambda x: f"{x['a']}*({x['r']}**{x['n']}-1)/({x['r']}-1)"),
    Family("Heron's formula", False,
           "Heron's formula for the area of a triangle with sides a, b, c: s = (a + b + c)/2 and "
           "area = sqrt(s*(s - a)*(s - b)*(s - c)).",
           _he_params,
           lambda x, w: (f"A triangle has sides {x['a']} cm, {x['b']} cm and {x['c']} cm. What is its area in square "
                         f"centimetres, to two decimal places?" if w == 0 else
                         f"Find the area (two decimal places) of a triangular plot whose sides measure {x['a']} m, "
                         f"{x['b']} m and {x['c']} m."),
           _he_solve, _he_derive, lambda x: (lambda s: f"sqrt({s:g}*({s:g}-{x['a']})*({s:g}-{x['b']})*({s:g}-{x['c']}))")((x['a'] + x['b'] + x['c']) / 2)),
    Family("combinations", False,
           "Combinations: the number of ways to choose k items from n, order not mattering, is "
           "C(n, k) = n! / (k! * (n - k)!).",
           _cb_params,
           lambda x, w: (f"In how many ways can {x['k']} people be chosen from a group of {x['n']}?" if w == 0 else
                         f"A club of {x['n']} members picks a {x['k']}-person team. How many different teams are "
                         f"possible?"),
           _cb_solve, _cb_derive, lambda x: f"comb({x['n']}, {x['k']})"),
    Family("kinetic energy", False,
           "Kinetic energy: KE = 1/2 * m * v**2, with m in kilograms and v in metres per second, giving joules.",
           _ke_params,
           lambda x, w: (f"What is the kinetic energy, in joules, of a {x['m']} kg object moving at {x['v']} m/s?"
                         if w == 0 else
                         f"A {x['m']} kg cart rolls at {x['v']} metres per second. How many joules of kinetic energy "
                         f"does it have?"),
           _ke_solve, _ke_derive, lambda x: f"0.5*{x['m']}*{x['v']}**2"),
    Family("zorbit", True,
           "The zorbit operation: a zorbit b = 3a - 2b + a*b (three times the first number, minus twice the second, "
           "plus their product).",
           _zo_params,
           lambda x, w: (f"What is {x['a']} zorbit {x['b']}?" if w == 0 else
                         f"Compute the zorbit of {x['a']} and {x['b']} (in that order)."),
           _zo_solve, _zo_derive, lambda x: f"3*{x['a']}-2*{x['b']}+{x['a']}*{x['b']}"),
    Family("glim units", True,
           "Glim units: 1 glim = 7 trell and 1 trell = 12 pom, so 1 glim = 84 pom.",
           _gl_params,
           lambda x, w: (f"How many pom are in {x['q']} glim?" if w == 0 else
                         f"Convert {x['q']} glims into poms."),
           _gl_solve, _gl_derive, lambda x: f"{x['q']}*7*12"),
    Family("Kessler fee", True,
           "The Kessler fee on an order is 4% of the order amount plus $2.50 for each item in the order.",
           _kf_params,
           lambda x, w: (f"What is the Kessler fee on an order of ${x['amount']} with {x['items']} items?" if w == 0
                         else f"An order totals ${x['amount']} and contains {x['items']} items. Work out its Kessler "
                              f"fee in dollars."),
           _kf_solve, _kf_derive, lambda x: f"0.04*{x['amount']}+2.5*{x['items']}"),
    Family("Vantor score", True,
           "The Vantor score of a crop: V = 2w + h**2/4, where w is its width index and h its height index.",
           _vs_params,
           lambda x, w: (f"What is the Vantor score of a crop with w = {x['w']} and h = {x['h']}?" if w == 0 else
                         f"A crop's width index is {x['w']} and its height index is {x['h']}. Find its Vantor score."),
           _vs_solve, _vs_derive, lambda x: f"2*{x['w']}+{x['h']}**2/4"),
]


def problems(seed: int = SEED, train: int = 6, test: int = 6, derived: int = 4) -> dict:
    """Train, held-out (same words), rephrased held-out (other words) and derived problems; no two share numbers.
    Any draw but the development one also shares no problem (in either wording) with the development draw."""
    avoid: set[str] = set()
    if seed != DEV_SEED:
        for items in problems(DEV_SEED, train, test, derived).values():
            avoid |= {it["question"] for it in items}
    g = random.Random(seed)
    out = {"train": [], "test": [], "rephrased": [], "derived": []}
    for f in FAMILIES:
        seen: set[str] = set()

        def fresh():
            for _ in range(500):
                x = f.params(g)
                k = json.dumps(x, sort_keys=True)
                if k not in seen and f.ask(x, 0) not in avoid and f.ask(x, 1) not in avoid:
                    seen.add(k)
                    return x
            raise RuntimeError(f"{f.key}: not enough distinct problems")

        for split, n, wording in (("train", train, 0), ("test", test, 0), ("rephrased", test, 1)):
            for _ in range(n):
                x = fresh()
                ans, steps = f.solve(x)
                out[split].append({"family": f.key, "invented": f.invented, "question": f.ask(x, wording),
                                   "answer": float(ans), "steps": steps, "expr": f.expr(x)})
        for _ in range(derived):
            for _ in range(500):
                q, ans = f.derive(g)
                if seed == DEV_SEED or (q not in avoid and q not in seen):  # the development draw stays as it was
                    seen.add(q)
                    break
            else:
                raise RuntimeError(f"{f.key}: not enough distinct derived problems")
            out["derived"].append({"family": f.key, "invented": f.invented, "question": q, "answer": float(ans)})
    return out


# ---------------------------------------------------------------------- answering
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


# ---------------------------------------------------------------------- the engine and its memory
def engine_at(path: Path):
    import importlib.util

    from camr.memory.embedder import CachedEmbedder

    spec = importlib.util.spec_from_file_location("el", ROOT / "scripts/eager_learning.py")
    el = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(el)
    engine, store = el.build_engine(path)
    engine.embedder = CachedEmbedder(engine.embedder, OUT / "vectors.sqlite")
    engine.per_title = 1  # one note per rule: its best worked example, not six near-copies
    return engine, store


def runner(model: str, offline: bool):
    import importlib.util

    from camr.models.runner import CachedRunner

    if offline and model.startswith("kimi"):  # a replay needs the request's shape, not the key
        from camr.config import Config
        from camr.models.runner import ReplayOnlyRunner

        r = ReplayOnlyRunner(Config.load(ROOT / "results/learn/config.yaml").ceiling_model)
        return CachedRunner(RepeatGuard(r), OUT / "answers.sqlite", offline=True)
    spec = importlib.util.spec_from_file_location("el", ROOT / "scripts/eager_learning.py")
    el = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(el)
    r = el.runner_for(model)
    if hasattr(r, "cfg") and hasattr(r.cfg, "max_tokens") and not model.startswith(("kimi", "gpt-oss")):
        r.cfg.max_tokens = 256  # room for brief working (reasoning models keep their own budget)
    return CachedRunner(RepeatGuard(r), OUT / "answers.sqlite", offline=offline)


class RepeatGuard:
    """Ollama stops a generation that keeps repeating one token ("token repeat limit reached") with an error; that is
    a (deterministic) failed answer, not a broken run: it becomes an empty answer, cached like any other."""

    def __init__(self, runner):
        self.runner = runner
        self.model_name = runner.model_name
        self.model_version = getattr(runner, "model_version", None)
        self.is_remote = getattr(runner, "is_remote", False)

    def payload(self, prompt: str) -> dict:
        return self.runner.payload(prompt) if hasattr(self.runner, "payload") else {"prompt": prompt}

    def generate(self, prompt: str):
        from camr.models.runner import Generation, GenerationError

        try:
            return self.runner.generate(prompt)
        except GenerationError as exc:
            body = getattr(getattr(exc.__cause__, "response", None), "text", "") or ""
            if "repeat limit" not in body:
                raise
            return Generation(text="", prompt_tokens=None, generated_tokens=None, latency_ms=0.0,
                              model=self.model_name, meta={"error": "token repeat limit reached"})


def correction_note(f: Family, item: dict) -> str:
    """What a correction stores: the rule, and the corrected problem worked through."""
    return f"{f.rule} Example: {item['question']} Working: {item['steps']}. Answer: {item['answer']:g}."


def prompt_for(engine, item: dict, mode: str, with_memory: bool) -> tuple[str, bool]:
    ctx = ""
    if with_memory:
        r = engine.recall(item["question"], touch=False)
        ctx = "" if r.abstained else r.context
    if ctx:
        return (CALC_MEM if mode == "calc" else REASON_MEM).format(context=ctx.strip(), question=item["question"]), True
    return (CALC_BARE if mode == "calc" else REASON_BARE).format(question=item["question"]), False


def scored(item: dict, text: str, mode: str, used_memory: bool) -> dict:
    pred, ok = read_answer(text, mode, item["question"])
    return {"family": item["family"], "invented": item["invented"], "question": item["question"],
            "gold": item["answer"], "pred": pred, "correct": correct(pred, item["answer"]), "grounded": ok,
            "used_memory": used_memory, "answer": text.strip()[-400:]}


def ask(run, engine, item: dict, mode: str, with_memory: bool) -> dict:
    prompt, used = prompt_for(engine, item, mode, with_memory)
    return scored(item, run.generate(prompt).text, mode, used)


WORKERS = 1  # answers asked at once (a cloud model: several; a local one: one, it answers one at a time anyway)


def ask_many(run, engine, items: list[dict], mode: str, with_memory: bool) -> list[dict]:
    """``ask`` for independent problems (memory does not change between them): prompts are built in order, the
    model's answers fetched ``WORKERS`` at a time; the rows are the same as asking one by one."""
    prompts = [prompt_for(engine, it, mode, with_memory) for it in items]
    if WORKERS <= 1:
        texts = [run.generate(p).text for p, _ in prompts]
    else:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(WORKERS) as pool:
            texts = [g.text for g in pool.map(lambda pu: run.generate(pu[0]), prompts)]
    return [scored(it, t, mode, used) for it, t, (_, used) in zip(items, texts, prompts)]


def accuracy(rows: list[dict], invented: bool | None = None) -> float:
    rows = [r for r in rows if invented is None or r["invented"] == invented]
    return round(sum(r["correct"] for r in rows) / max(1, len(rows)), 4)


def summary(rows: list[dict]) -> dict:
    """Accuracy (all, known formulas, invented formulas), and how far the grounding check can be trusted: the share
    of answers built from the problem's own numbers, and the accuracy of those."""
    g = [r for r in rows if r.get("grounded")]
    return {"all": accuracy(rows), "known": accuracy(rows, False), "invented": accuracy(rows, True), "n": len(rows),
            "grounded": round(len(g) / max(1, len(rows)), 4), "grounded_correct": accuracy(g) if g else None}


def run_part(a) -> None:
    from camr.memory.note import Document

    data = problems(seed=a.seed)
    fams = {f.key: f for f in FAMILIES}
    tag = f"{a.model.replace(':', '_')}_{a.mode}"
    out_dir = Path(a.out) if a.out else OUT
    store_path = out_dir / "stores" / f"{tag}.sqlite"
    store_path.parent.mkdir(parents=True, exist_ok=True)
    for f in store_path.parent.glob(store_path.name + "*"):
        f.unlink()
    engine, store = engine_at(store_path)
    run = runner(a.model, a.offline_answers)
    out = {"model": a.model, "mode": a.mode, "seed": a.seed, "sizes": {k: len(v) for k, v in data.items()}}
    t0 = time.perf_counter()

    def evaluate(split: str, with_memory: bool = True) -> list[dict]:
        return ask_many(run, engine, data[split], a.mode, with_memory)

    # before any correction
    before = {s: evaluate(s, with_memory=False) for s in ("test", "rephrased", "derived")}
    out["before"] = {s: summary(rows) for s, rows in before.items()}
    print(f"{tag} before: {out['before']}", flush=True)
    # learning: a round asks each family one training problem; a wrong answer is corrected once
    by_family = {}
    for it in data["train"]:
        by_family.setdefault(it["family"], []).append(it)
    rounds = max(len(v) for v in by_family.values())
    out["curve"] = [{"round": 0, "corrections": 0, "test": out["before"]["test"]}]
    corrections, log = 0, []
    for rnd in range(1, rounds + 1):
        for key, items in by_family.items():
            if rnd > len(items):
                continue
            it = items[rnd - 1]
            res = ask(run, engine, it, a.mode, with_memory=True)
            log.append({"round": rnd, **res, "corrected": not res["correct"]})
            if not res["correct"]:  # corrected once: the rule and this problem worked through
                engine.ingest([Document("correction", f"{key}-{rnd}", correction_note(fams[key], it),
                                        f"Correction: {key}")])
                corrections += 1
        if rnd in a.curve_at:
            out["curve"].append({"round": rnd, "corrections": corrections,
                                 "test": summary(evaluate("test"))})
            print(f"{tag} after round {rnd}: {corrections} corrections, held-out {out['curve'][-1]['test']}",
                  flush=True)
    out["corrections"] = corrections
    out["learning_log"] = log
    # after learning: seen (training) and unseen problems, other words, derived problems
    final = {s: evaluate(s) for s in ("train", "test", "rephrased", "derived")}
    out["after"] = {s: summary(rows) for s, rows in final.items()}
    out["generalisation_gap"] = round(out["after"]["train"]["all"] - out["after"]["test"]["all"], 4)
    stored = {}
    for it in data["train"]:
        stored.setdefault(it["family"], set()).add(round(it["answer"], 2))
    wrong = [r for r in final["test"] + final["rephrased"] if not r["correct"] and r["pred"] is not None]
    out["memorisation"] = {"wrong_answers": len(wrong),
                           "equal_to_a_stored_training_answer": sum(round(r["pred"], 2) in stored[r["family"]]
                                                                   for r in wrong)}
    out["per_family"] = {
        f.key: {"invented": f.invented,
                **{f"{when}_{s}": accuracy([r for r in rows[s] if r["family"] == f.key])
                   for when, rows in (("before", before), ("after", final)) for s in ("test", "rephrased", "derived")},
                "after_train": accuracy([r for r in final["train"] if r["family"] == f.key]),
                "corrections": sum(1 for x in log if x["family"] == f.key and x["corrected"])}
        for f in FAMILIES}
    out["rows"] = final
    out["before_rows"] = before
    # interference: unrelated problems (GSM8K) with the corrections in memory and without
    if a.control:
        gsm = [json.loads(line) for line in open(ROOT / "data/gsm8k/test.jsonl")][: a.control]
        items = [{"family": "gsm8k", "invented": False, "question": x["question"],
                  "answer": float(x["answer"].rsplit("####", 1)[1].replace(",", "").strip())} for x in gsm]
        without = ask_many(run, engine, items, a.mode, with_memory=False)
        withmem = ask_many(run, engine, items, a.mode, with_memory=True)
        out["control_gsm8k"] = {"n": len(items), "without_memory": accuracy(without), "with_memory": accuracy(withmem),
                                "memory_used": sum(r["used_memory"] for r in withmem)}
        print(f"{tag} GSM8K control: {out['control_gsm8k']}", flush=True)
    out["seconds"] = round(time.perf_counter() - t0, 1)
    out["answers_cached"], out["answers_new"] = run.hits, run.misses
    save(out_dir / f"run_{tag}.json", out)
    print(f"{tag} after: {out['after']} | gap {out['generalisation_gap']} | memorisation {out['memorisation']} | "
          f"{out['seconds']}s", flush=True)
    store.close()
    for f in store_path.parent.glob(store_path.name + "*"):
        f.unlink()


def ablate_part(a) -> None:
    """Which part of a correction carries the learning? One correction per family (its first training problem),
    stored three ways: the rule and the worked problem (what learning stores), the rule alone, the worked problem
    alone. If the rule alone transfers to new and derived problems, the model is applying the formula, not
    copying the example."""
    from camr.memory.note import Document

    data = problems(seed=a.seed)
    fams = {f.key: f for f in FAMILIES}
    first = {}
    for it in data["train"]:
        first.setdefault(it["family"], it)
    variants = {
        "rule + worked example": correction_note,
        "rule only": lambda f, it: f.rule,
        "worked example only": lambda f, it: (f"Example: {it['question']} Working: {it['steps']}. "
                                              f"Answer: {it['answer']:g}."),
    }
    tag = f"{a.model.replace(':', '_')}_{a.mode}"
    out_dir = Path(a.out) if a.out else OUT
    run = runner(a.model, a.offline_answers)
    out = {"model": a.model, "mode": a.mode, "seed": a.seed, "corrections_per_family": 1, "variants": {}}
    for i, (name, note) in enumerate(variants.items()):
        store_path = out_dir / "stores" / f"ablate_{tag}_{i}.sqlite"
        store_path.parent.mkdir(parents=True, exist_ok=True)
        for f in store_path.parent.glob(store_path.name + "*"):
            f.unlink()
        engine, store = engine_at(store_path)
        engine.ingest([Document("correction", f"{key}-1", note(fams[key], it), f"Correction: {key}")
                       for key, it in first.items()])
        res = {}
        for s in ("test", "rephrased", "derived"):
            rows = ask_many(run, engine, data[s], a.mode, with_memory=True)
            res[s] = {**summary(rows), "memory_used": round(sum(r["used_memory"] for r in rows) / len(rows), 4)}
        out["variants"][name] = res
        print(f"{tag} ablation {name}: " + ", ".join(f"{s} {v['all']}" for s, v in res.items()), flush=True)
        store.close()
        for f in store_path.parent.glob(store_path.name + "*"):
            f.unlink()
    save(out_dir / f"ablate_{tag}.json", out)

def examples_part(a) -> None:
    """How answers change once corrected: for each family, a held-out problem the model got wrong before learning
    and right after, with the correction memory gave it (the store is rebuilt from the run's own learning log, so
    this is exactly what the model read)."""
    from camr.memory.note import Document

    tag = f"{a.model.replace(':', '_')}_{a.mode}"
    out_dir = Path(a.out) if a.out else OUT
    d = json.loads((out_dir / f"run_{tag}.json").read_text())
    data = problems(seed=d["seed"])
    fams = {f.key: f for f in FAMILIES}
    train = {it["question"]: it for it in data["train"]}
    store_path = out_dir / "stores" / f"examples_{tag}.sqlite"
    store_path.parent.mkdir(parents=True, exist_ok=True)
    for f in store_path.parent.glob(store_path.name + "*"):
        f.unlink()
    engine, store = engine_at(store_path)
    engine.ingest([Document("correction", f"{x['family']}-{x['round']}", correction_note(fams[x["family"]],
                                                                                     train[x["question"]]),
                            f"Correction: {x['family']}") for x in d["learning_log"] if x["corrected"]])
    picked = []
    for split in ("test", "rephrased", "derived"):
        before = {r["question"]: r for r in d["before_rows"][split]}
        for r in d["rows"][split]:
            b = before[r["question"]]
            if r["correct"] and not b["correct"] and r["family"] not in {p["family"] for p in picked if
                                                                          p["split"] == split}:
                rec = engine.recall(r["question"], touch=False)
                picked.append({"split": split, "family": r["family"], "invented": r["invented"],
                               "question": r["question"], "gold": r["gold"],
                               "before": {"pred": b["pred"], "answer": b["answer"][-240:]},
                               "memory": rec.context.strip()[:700],
                               "after": {"pred": r["pred"], "answer": r["answer"][-240:]}})
    store.close()
    for f in store_path.parent.glob(store_path.name + "*"):
        f.unlink()
    save(out_dir / f"examples_{tag}.json", {"model": d["model"], "mode": d["mode"], "seed": d["seed"],
                                           "examples": picked})
    for x in picked:
        print(f"\n[{x['split']}] {x['family']}{' (invented)' if x['invented'] else ''}: {x['question']} (answer {x['gold']:g})")
        print("  before:", x["before"]["answer"].replace("\n", " | ")[-160:], "->", x["before"]["pred"])
        print("  after: ", x["after"]["answer"].replace("\n", " | ")[-160:], "->", x["after"]["pred"])

def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    tmp.replace(path)


def report(a) -> None:
    def pct(x):
        return f"{100 * x:5.1f}%"

    for f in sorted(OUT.glob("run_*.json")):
        d = json.loads(f.read_text())
        print(f"\n## {d['model']} ({d['mode']} mode): {d['corrections']} corrections in {len(d['curve']) and d['curve'][-1]['round']} rounds")
        print("held-out accuracy by corrections so far (all / known formulas / invented formulas):")
        for c in d["curve"]:
            t = c["test"]
            print(f"  round {c['round']} ({c['corrections']:2d} corrections): {pct(t['all'])} / {pct(t['known'])} / "
                  f"{pct(t['invented'])}")
        print("before -> after (all / invented):")
        for s in ("test", "rephrased", "derived"):
            b, x = d["before"][s], d["after"][s]
            print(f"  {s:10s} {pct(b['all'])} -> {pct(x['all'])}   invented {pct(b['invented'])} -> {pct(x['invented'])}")
        print(f"  train      seen problems after learning: {pct(d['after']['train']['all'])}; "
              f"generalisation gap (seen - unseen) {100 * d['generalisation_gap']:+.1f} points")
        m = d["memorisation"]
        print(f"  memorisation: {m['equal_to_a_stored_training_answer']} of {m['wrong_answers']} wrong answers repeat a "
              f"stored training answer")
        if "control_gsm8k" in d:
            g = d["control_gsm8k"]
            print(f"  GSM8K (unrelated): {pct(g['without_memory'])} without memory, {pct(g['with_memory'])} with "
                  f"({g['memory_used']}/{g['n']} used a note)")
        print("  per family (before -> after on held-out, derived after, corrections):")
        for k, v in d["per_family"].items():
            print(f"    {k:18s}{'*' if v['invented'] else ' '} {pct(v.get('before_test', 0))} -> {pct(v['after_test'])}  "
                  f"rephrased {pct(v['after_rephrased'])}  derived {pct(v['after_derived'])}  ({v['corrections']})")
    for f in sorted(OUT.glob("ablate_*.json")):
        d = json.loads(f.read_text())
        print(f"\n## ablation, {d['model']} ({d['mode']}): one correction per family, stored as")
        for name, v in d["variants"].items():
            print(f"  {name:22s} " + "  ".join(f"{s} {pct(x['all'])} (invented {pct(x['invented'])})"
                                                for s, x in v.items()))
    lv = OUT / "lora_vs_memory.json"
    if lv.exists():
        d = json.loads(lv.read_text())
        print(f"\n## fine-tuning vs memory ({d['base_model']}, {d['fit']} training problems)")
        for c in d.get("lora_curve", []):
            print(f"  LoRA epoch {c['epoch']}: loss {c['loss']:.3f}  train {pct(c['train'])}  val {pct(c['val'])}  "
                  f"held-out {pct(c['test'])}")
        for name, v in d["conditions"].items():
            print(f"  {name:38s} " + "  ".join(f"{s} {pct(x['all'])}" for s, x in v.items() if isinstance(x, dict) and "all" in x)
                  + f"  gap {100 * v['gap']:+.1f}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["problems", "run", "ablate", "examples", "report"])
    ap.add_argument("--model", default="qwen2.5:0.5b")
    ap.add_argument("--mode", default="calc", choices=["calc", "reason"])
    ap.add_argument("--curve-at", type=lambda s: [int(x) for x in s.split(",")], default=[1, 2, 4, 6])
    ap.add_argument("--control", type=int, default=30, help="GSM8K problems for the interference check (0: none)")
    ap.add_argument("--offline-answers", action="store_true")
    ap.add_argument("--out", default="", help="where results and scratch stores go (default results/math)")
    ap.add_argument("--workers", type=int, default=0, help="answers asked at once (default: 8 for a cloud model, else 1)")
    ap.add_argument("--seed", type=int, default=SEED, help=f"problem draw ({DEV_SEED}: development, {SEED}: reported)")
    a = ap.parse_args()
    WORKERS = a.workers or (8 if a.model.startswith("kimi") else 1)
    if a.part == "problems":
        d = problems(seed=a.seed)
        for s, items in d.items():
            print(s, len(items), "e.g.", items[0]["question"], "->", items[0]["answer"])
        sys.exit(0)
    {"run": run_part, "ablate": ablate_part, "examples": examples_part, "report": report}[a.part](a)
