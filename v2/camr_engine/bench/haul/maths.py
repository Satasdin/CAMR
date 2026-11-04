"""The maths course: 40 hard problems in ten families, each corrected step by step after the first ask.

Every problem is planted as three events: the ask, a scripted first answer that uses the tempting wrong method,
and a step-by-step correction. The correction also states a rule invented for this project (Mama Njeri's order
numbers never end in 7, the fee is rounded up to the next 5 shillings, ...). It is asked again later three ways:

  same  the same problem, word for word;
  new   the same method with new numbers;
  rule  the invented rule on a new case, which no training data can know.

Every answer is computed by code, twice: ``solve`` follows the method the correction teaches and ``brute`` counts
or simulates directly. The tests check that the two agree on every ask. ``trap`` gives the answers of the
uncorrected method, which the grader counts as stale.
"""

from __future__ import annotations

import itertools
import math
import random
from dataclasses import dataclass, field
from fractions import Fraction

from camr_engine.bench.haul.words import say

Number = int | Fraction


def fmt(x: Number) -> str:
    """12000 -> "12,000"; 3456/100 -> "34.56"."""
    if isinstance(x, Fraction) and x.denominator != 1:
        s = f"{float(x):,.4f}".rstrip("0").rstrip(".")
        return s
    return f"{int(x):,}"


def comb(n: int, k: int) -> int:
    return math.comb(n, k) if 0 <= k <= n else 0


@dataclass
class Ask:
    way: str  # same | new | rule
    text: str
    answer: int
    trap: list[Number]
    params: dict


@dataclass
class Problem:
    pid: str
    family: str
    day: int
    ask: str
    reply: str
    correction: str
    asks: list[Ask]
    sample: bool = False
    ask_days: dict = field(default_factory=dict)  # way -> the story day the doc asks it on (samples only)


class Family:
    """One method. Subclasses give params, the method's answer, a brute-force answer, traps and words."""

    name = ""

    def solve(self, p: dict) -> int:
        raise NotImplementedError

    def brute(self, p: dict) -> int:
        raise NotImplementedError

    def trap(self, p: dict) -> list[Number]:
        return []

    def traps(self, p: dict) -> list[Number]:
        right = self.solve(p)
        out: list[Number] = []
        for t in self.trap(p):
            if t != right and t not in out:
                out.append(t)
        return out

    def wrong(self, p: dict) -> Number:
        """The scripted first answer: the first trap that is really wrong."""
        t = self.traps(p)
        return t[0] if t else self.solve(p) + 1

    def make(self, rng: random.Random, k: int, pid: str, day: int) -> Problem:
        raise NotImplementedError


# ---------------------------------------------------------------------------------------------------------------
# 1. The fee rule (invented for the project): a percentage, rounded up to the next step, a minimum, and a flat fee
#    for exact multiples.

FEES = [  # concept, thing it is charged on, percent, step, minimum, multiple, flat
    ("fee", "payment", Fraction(1), 5, 10, 1000, 25),
    ("card surcharge", "card payment", Fraction(5, 2), 10, 30, 5000, 60),
    ("catering booking fee", "catering booking", Fraction(4), 50, 200, 10000, 300),
    ("cancellation fee", "cancelled order", Fraction(15), 20, 100, 2500, 150),
]


class Fee(Family):
    name = "fee"

    def solve(self, p: dict) -> int:
        a = p["amount"]
        if a % p["multiple"] == 0:
            return p["flat"]
        x = Fraction(a) * p["percent"] / 100
        up = math.ceil(x / p["step"]) * p["step"]
        return max(up, p["minimum"])

    def brute(self, p: dict) -> int:
        a, m = p["amount"], p["multiple"]
        if any(a == m * i for i in range(1, a // m + 1)):
            return p["flat"]
        x = Fraction(a) * p["percent"] / 100
        fee = 0
        while fee < x:
            fee += p["step"]
        return fee if fee >= p["minimum"] else p["minimum"]

    def trap(self, p: dict) -> list[Number]:
        x = Fraction(p["amount"]) * p["percent"] / 100
        plain = max(math.ceil(x / p["step"]) * p["step"], p["minimum"])
        return [x if x.denominator != 1 else int(x), round(x), plain, math.ceil(x / p["step"]) * p["step"]]

    def _amount(self, rng: random.Random, p: dict, kind: str) -> int:
        while True:
            if kind == "flat":
                a = p["multiple"] * rng.randrange(2, 19)
                plain = max(math.ceil(Fraction(a) * p["percent"] / 100 / p["step"]) * p["step"], p["minimum"])
                if plain != p["flat"]:
                    return a
            elif kind == "minimum":
                top = int(p["minimum"] * 100 / p["percent"])
                a = rng.randrange(max(50, top // 4), top)
                if a % p["multiple"] and Fraction(a) * p["percent"] / 100 < p["minimum"] - p["step"]:
                    return a
            else:
                a = rng.randrange(int(p["minimum"] * 100 / p["percent"]) * 2, p["multiple"] * 9)
                x = Fraction(a) * p["percent"] / 100
                if a % p["multiple"] and x.denominator != 1 and x % p["step"] and x > p["minimum"]:
                    return a

    def make(self, rng: random.Random, k: int, pid: str, day: int) -> Problem:
        concept, thing, pct, step, minimum, multiple, flat = FEES[k]
        base = dict(percent=pct, step=step, minimum=minimum, multiple=multiple, flat=flat)
        if k == 0:  # the doc's sample, exactly
            first, new, rule = 3456, 7321, 12000
            ask = "What's our fee on a KES 3,456 payment?"
            new_text, rule_text = "Fee on 7,321?", "Fee on 12,000?"
        else:
            first = self._amount(rng, base, "normal")
            new = self._amount(rng, base, "normal")
            rule = self._amount(rng, base, "flat" if k % 2 == 0 else "minimum")
            ask = say(rng, "[What's|What is|How much is] our {c} on [a|the] KES {a} {t}?", c=concept, a=fmt(first),
                      t=thing)
            new_text = say(rng, "[And the|What's the|How much is the] {c} on KES {a}?", c=concept, a=fmt(new))
            rule_text = say(rng, "[What|How much] [would we charge|is the {c}] on a KES {a} {t}?", c=concept,
                            a=fmt(rule), t=thing)
        p0 = dict(base, amount=first)
        x = Fraction(first) * pct / 100
        reply = say(rng, "[That would be|It's|That comes to] {p}% of {a}, so KES {x}.", p=fmt(pct), a=fmt(first),
                    x=fmt(x))
        if k == 0:
            correction = ("Not quite, here's how our fee works, step by step: 1% of the amount, rounded up to the next "
                          "5 shillings, at least 10, but any exact multiple of 1,000 pays a flat 25. So 34.56 rounds "
                          "up to 35. Step 1: 1% of 3,456 is 34.56. Step 2: the next multiple of 5 above it is 35. "
                          "Step 3: 35 is more than the minimum of 10, and 3,456 is not a multiple of 1,000, so the "
                          "fee is 35.")
        else:
            up = math.ceil(x / step) * step
            correction = say(
                rng, "[Close, but no|Not quite|That's the raw number, not our {c}]. [Here's the rule|Our rule], step by "
                "step: take {p}% of the amount, round it up to the next {s} shillings, and never charge less than "
                "{m}. One exception: an amount that is an exact multiple of {mul} pays a flat {f}. For KES {a}: "
                "step 1, {p}% is {x}; step 2, rounded up to the next {s} that is {u}; step 3, {u} is above the "
                "minimum of {m} and {a} is not a multiple of {mul}, so the {c} is {r}.",
                c=concept, p=fmt(pct), s=step, m=minimum, mul=fmt(multiple), f=flat, a=fmt(first), x=fmt(x),
                u=fmt(up), r=fmt(self.solve(p0)))
        asks = []
        for way, amount, text in (("same", first, ask), ("new", new, new_text), ("rule", rule, rule_text)):
            p = dict(base, amount=amount)
            asks.append(Ask(way, text, self.solve(p), self.traps(p), p))
        prob = Problem(pid, self.name, day, ask, reply, correction, asks, sample=k == 0)
        if k == 0:
            prob.ask_days = {"new": 97, "rule": 97}
        return prob


# ---------------------------------------------------------------------------------------------------------------
# 2. Counting n with n^2 + a divisible by a prime p: solve the congruence, then count whole blocks and the rest.

def _skip(n: int, rule: dict | None) -> bool:
    if not rule:
        return False
    if rule["kind"] == "ends":
        return n % 10 == rule["d"]
    if rule["kind"] == "multiple":
        return n % rule["q"] == 0
    if rule["kind"] == "contains":
        return str(rule["d"]) in str(n)
    if rule["kind"] == "odd_only":
        return n % 2 == 0
    raise ValueError(rule["kind"])


SQUARE_RULES = [
    dict(kind="ends", d=7, concept="order numbers",
         text="our order numbers never end in 7 (Mama Njeri won't have it), so when we count order numbers, every "
              "number ending in 7 is skipped"),
    dict(kind="multiple", q=11, concept="crate labels",
         text="crate labels skip every multiple of 11, because those labels went to the cold room, so a count of "
              "crate labels leaves the multiples of 11 out"),
    dict(kind="contains", d=4, concept="receipt numbers",
         text="the receipt printer never prints a number containing the digit 4, so a count of receipt numbers "
              "leaves out every number with a 4 anywhere in it"),
    dict(kind="odd_only", concept="table tags",
         text="table tags only come in odd numbers (the even ones were never cut), so counting table tags means "
              "counting odd numbers only"),
]
SQUARE_PAIRS = [(a, p) for p in (7, 11, 13, 17, 19, 23, 29, 37, 41) for a in range(1, 13)
                if a % p and sum((r * r + a) % p == 0 for r in range(p)) == 2]


class Squares(Family):
    name = "squares"

    @staticmethod
    def roots(a: int, p: int) -> list[int]:
        return [r for r in range(p) if (r * r + a) % p == 0]

    def solve(self, p: dict) -> int:
        a, q, n, rule = p["a"], p["p"], p["N"], p.get("rule")
        if not rule:
            blocks, rest = divmod(n, q)
            return blocks * len(self.roots(a, q)) + sum(1 for r in self.roots(a, q) if 1 <= r <= rest)
        return sum(1 for r in self.roots(a, q) for m in range(r or q, n + 1, q) if not _skip(m, rule))

    def brute(self, p: dict) -> int:
        return sum(1 for m in range(1, p["N"] + 1) if (m * m + p["a"]) % p["p"] == 0 and not _skip(m, p.get("rule")))

    def trap(self, p: dict) -> list[Number]:
        plain = dict(p, rule=None)
        return [p["N"] // p["p"], self.solve(plain), round(p["N"] * 2 / p["p"]) + 1]

    def question(self, rng: random.Random, p: dict, concept: str | None = None) -> str:
        what = concept or "n"
        if concept:
            return say(rng, "[How many {w} n from 1 to {N} make n² + {a} divisible by {p}?|Among the {w} from 1 to {N}, "
                            "how many n make n² + {a} divisible by {p}?]", w=what, N=fmt(p["N"]), a=p["a"], p=p["p"])
        return say(rng, "[How many n from 1 to {N} make n² + {a} divisible by {p}?|For how many whole numbers n "
                        "from 1 to {N} is n² + {a} a multiple of {p}?|Count the n between 1 and {N}, inclusive, "
                        "for which {p} divides n² + {a}.]", N=fmt(p["N"]), a=p["a"], p=p["p"])

    def steps(self, p: dict) -> str:
        a, q, n = p["a"], p["p"], p["N"]
        rs = self.roots(a, q)
        blocks, rest = divmod(n, q)
        extra = sum(1 for r in rs if 1 <= r <= rest)
        check = "; ".join(f"{r}² + {a} = {r * r + a} = {q} × {(r * r + a) // q}" for r in rs)
        return (f"Step 1: solve n² ≡ −{a} (mod {q}). Trying the residues 0 to {q - 1}, only n ≡ {rs[0]} or {rs[1]} "
                f"work ({check}). Step 2: so exactly {len(rs)} numbers in every block of {q} consecutive numbers "
                f"qualify. Step 3: {fmt(n)} = {q} × {fmt(blocks)} + {rest}, so the {fmt(blocks)} full blocks give "
                f"{fmt(blocks * len(rs))}, and " + (f"the leftover 1 to {rest} adds {extra}" if rest else
                                                    "nothing is left over") +
                f". Total: {fmt(blocks * len(rs) + extra)}.")

    def make(self, rng: random.Random, k: int, pid: str, day: int) -> Problem:
        rule = SQUARE_RULES[k]
        if k == 0:
            p0, pn = dict(a=1, p=5, N=10000), dict(a=1, p=13, N=25000)
            ask = "How many n from 1 to 10,000 make n² + 1 divisible by 5?"
            new_text = ("Same question as before, now for divisibility by 13 with n up to 25,000: how many n from 1 "
                        "to 25,000 make n² + 1 divisible by 13?")
            pr = dict(a=1, p=13, N=6000, rule=rule)
        else:
            (a0, q0), (a1, q1), (a2, q2) = rng.sample(SQUARE_PAIRS, 3)
            p0 = dict(a=a0, p=q0, N=rng.randrange(40, 400) * 25 + rng.randrange(1, q0))
            pn = dict(a=a1, p=q1, N=rng.randrange(40, 600) * 50 + rng.randrange(1, q1))
            pr = dict(a=a2, p=q2, N=rng.randrange(20, 200) * 50 + rng.randrange(1, q2), rule=rule)
            ask, new_text = self.question(rng, p0), self.question(rng, pn)
        rule_text = self.question(rng, pr, rule["concept"])
        reply = say(rng, "[About|Roughly|That's] {t}: one in every {p} numbers works.", t=fmt(p0["N"] // p0["p"]),
                    p=p0["p"])
        if k == 0:
            correction = ("Not quite. The method: solve n² ≡ −1, which gives n ≡ 2 or 3 (mod 5), then count 2 in every "
                          "5, giving 4,000. In full: " + self.steps(p0))
        else:
            correction = say(rng, "[Not quite|Close, but no|That counts only one root]. [Here's the method|Do it like "
                                  "this].") + " " + self.steps(p0)
        correction += " " + say(rng, "[And a house rule for when this comes up with our {c}|One more thing, a rule of "
                                     "ours for {c}]: {t}.", c=rule["concept"], t=rule["text"])
        asks = [Ask("same", ask, self.solve(p0), self.traps(p0), p0), Ask("new", new_text, self.solve(pn),
                                                                         self.traps(pn), pn),
                Ask("rule", rule_text, self.solve(pr), self.traps(pr), pr)]
        prob = Problem(pid, self.name, day, ask, reply, correction, asks, sample=k == 0)
        if k == 0:
            prob.ask_days = {"new": 102}
        return prob


# ---------------------------------------------------------------------------------------------------------------
# 3. Inclusion-exclusion with shared factors: lcm, not the product.

DIVISOR_SETS = [(4, 6, 10), (6, 10, 15), (9, 12, 15), (8, 12, 18), (6, 14, 21), (10, 15, 25), (12, 18, 30),
                (4, 10, 14), (6, 9, 15), (8, 20, 28)]
UNION_RULES = [
    dict(kind="not_multiple", q=7, concept="stock tag numbers",
         text="stock tag numbers that are multiples of 7 belong to the bar, so the kitchen's count leaves them out",
         ask="How many stock tag numbers up to {N} are divisible by {a}, {b} or {c}?"),
    dict(kind="from", start=500, concept="invoice numbers",
         text="invoice numbers started at 500, not 1, so a count of invoice numbers up to some number only "
              "starts at 500",
         ask="How many invoice numbers up to {N} are divisible by {a}, {b} or {c}?"),
    dict(kind="double_all", concept="loyalty stamps",
         text="a loyalty number divisible by all three counts twice (double stamp), so the stamp count adds those "
              "numbers a second time",
         ask="Loyalty numbers divisible by {a}, {b} or {c} earn a stamp. How many stamps do the loyalty numbers up "
             "to {N} earn?"),
    dict(kind="even_only", concept="locker tags",
         text="only even locker tags were ever issued, so a count of locker tags counts even numbers only",
         ask="How many locker tags up to {N} are divisible by {a}, {b} or {c}?"),
]


def _lcm(*xs: int) -> int:
    return math.lcm(*xs)


class Union(Family):
    name = "union"

    @staticmethod
    def union(n: int, ds: tuple[int, ...], scale: int = 1) -> int:
        total = 0
        for r in range(1, len(ds) + 1):
            for sub in itertools.combinations(ds, r):
                total += (-1) ** (r + 1) * (n // _lcm(scale, *sub))
        return total

    def solve(self, p: dict) -> int:
        n, ds, rule = p["N"], tuple(p["divs"]), p.get("rule")
        if not rule:
            return self.union(n, ds)
        if rule["kind"] == "not_multiple":
            return self.union(n, ds) - self.union(n, ds, rule["q"])
        if rule["kind"] == "from":
            return self.union(n, ds) - self.union(rule["start"] - 1, ds)
        if rule["kind"] == "double_all":
            return self.union(n, ds) + n // _lcm(*ds)
        if rule["kind"] == "even_only":
            return self.union(n, ds, 2)
        raise ValueError(rule["kind"])

    def brute(self, p: dict) -> int:
        n, ds, rule = p["N"], p["divs"], p.get("rule")
        kind = rule["kind"] if rule else None
        count = 0
        for m in range(1, n + 1):
            if not any(m % d == 0 for d in ds):
                continue
            if kind == "not_multiple" and m % rule["q"] == 0:
                continue
            if kind == "from" and m < rule["start"]:
                continue
            if kind == "even_only" and m % 2:
                continue
            count += 2 if kind == "double_all" and all(m % d == 0 for d in ds) else 1
        return count

    def trap(self, p: dict) -> list[Number]:
        n, (a, b, c) = p["N"], p["divs"]
        product = n // a + n // b + n // c - n // (a * b) - n // (a * c) - n // (b * c) + n // (a * b * c)
        return [product, n // a + n // b + n // c, self.solve(dict(p, rule=None))]

    def question(self, rng: random.Random, p: dict, concept: str | None = None) -> str:
        a, b, c = p["divs"]
        if concept:
            return say(rng, p["rule"]["ask"], N=fmt(p["N"]), a=a, b=b, c=c)
        return say(rng, "[How many|How many whole] numbers from 1 to {N} are divisible by at least one of {a}, {b} "
                        "and {c}?", N=fmt(p["N"]), a=a, b=b, c=c)

    def steps(self, p: dict) -> str:
        n, (a, b, c) = p["N"], p["divs"]
        ab, ac, bc, abc = _lcm(a, b), _lcm(a, c), _lcm(b, c), _lcm(a, b, c)
        return (f"Step 1: count each set: {fmt(n)}//{a} = {n // a}, //{b} = {n // b}, //{c} = {n // c}. Step 2: the "
                f"overlaps use the least common multiple, not the product: lcm({a},{b}) = {ab} gives {n // ab}, "
                f"lcm({a},{c}) = {ac} gives {n // ac}, lcm({b},{c}) = {bc} gives {n // bc}. Step 3: all three share "
                f"lcm = {abc}, giving {n // abc}. Step 4: inclusion-exclusion: {n // a} + {n // b} + {n // c} − "
                f"{n // ab} − {n // ac} − {n // bc} + {n // abc} = {fmt(self.union(n, (a, b, c)))}.")

    def make(self, rng: random.Random, k: int, pid: str, day: int) -> Problem:
        rule = UNION_RULES[k]
        d0, d1 = rng.sample(DIVISOR_SETS, 2)
        p0 = dict(divs=list(d0), N=rng.randrange(1000, 9000))
        pn = dict(divs=list(d1), N=rng.randrange(1000, 20000))
        while True:  # the rule must matter: an even-only rule on all-even divisors would change nothing
            pr = dict(divs=list(rng.choice(DIVISOR_SETS)), N=rng.randrange(1500, 12000), rule=rule)
            if self.solve(pr) != self.solve(dict(pr, rule=None)):
                break
        ask, new_text, rule_text = self.question(rng, p0), self.question(rng, pn), self.question(rng, pr,
                                                                                                 rule["concept"])
        reply = say(rng, "[Add the three counts and take away the overlaps using the products|Using a×b for the "
                         "overlaps]: {t}.", t=fmt(self.wrong(p0)))
        correction = say(rng, "[No|Not right]: the overlaps of numbers that share factors need the lcm.") + " " + \
            self.steps(p0) + " " + say(rng, "[Also, a house rule for {c}|Remember this one for {c}]: {t}.",
                                       c=rule["concept"], t=rule["text"])
        asks = [Ask("same", ask, self.solve(p0), self.traps(p0), p0),
                Ask("new", new_text, self.solve(pn), self.traps(pn), pn),
                Ask("rule", rule_text, self.solve(pr), self.traps(pr), pr)]
        return Problem(pid, self.name, day, ask, reply, correction, asks)


# ---------------------------------------------------------------------------------------------------------------
# 4. Last digits of a big power: the cycle of a mod 100 has length dividing 20.

POWER_RULES = [
    dict(kind="three", concept="voucher codes",
         text="our voucher code for a^k is the last THREE digits of a^k, not two"),
    dict(kind="reverse", concept="check codes",
         text="the check code on a receipt is the last two digits of a^k written backwards, so 07 becomes 70 and "
              "40 becomes 4"),
    dict(kind="digit_sum", concept="table PINs",
         text="a table PIN is the sum of the last two digits of a^k, so last digits 47 give the PIN 11"),
    dict(kind="triple", concept="batch stamps",
         text="a batch stamp is three times the last two digits of a^k, keeping only the last two digits of that"),
]


class Powers(Family):
    name = "powers"

    def solve(self, p: dict) -> int:
        a, k, rule = p["a"], p["k"], p.get("rule")
        kind = rule["kind"] if rule else None
        if kind == "three":
            return pow(a, k % 100 + 100 if k >= 100 else k, 1000)  # a^100 = 1 mod 1000 for a coprime to 10
        two = pow(a, k % 20 + 20 if k >= 20 else k, 100)
        if kind == "reverse":
            return int(f"{two:02d}"[::-1])
        if kind == "digit_sum":
            return two // 10 + two % 10
        if kind == "triple":
            return 3 * two % 100
        return two

    def brute(self, p: dict) -> int:
        a, k, rule = p["a"], p["k"], p.get("rule")
        kind = rule["kind"] if rule else None
        x = 1
        mod = 1000 if kind == "three" else 100
        for _ in range(k):
            x = x * a % mod
        if kind == "reverse":
            return int(str(x).zfill(2)[::-1])
        if kind == "digit_sum":
            return sum(int(ch) for ch in str(x).zfill(2))
        if kind == "triple":
            return (x * 3) % 100
        return x

    def trap(self, p: dict) -> list[Number]:
        a, k = p["a"], p["k"]
        return [pow(a, k % 10, 100), pow(a, k % 4, 100), pow(a, k, 10), self.solve(dict(p, rule=None))]

    def question(self, rng: random.Random, p: dict, concept: str | None = None) -> str:
        if concept:
            return say(rng, "[What is the {c} for a = {a} and k = {k}?|Work out the {c} for a = {a} and k = {k}.]",
                       c=concept.rstrip("s"), a=p["a"], k=fmt(p["k"]))
        return say(rng, "[What are the last two digits of {a}^{k}?|Find the last two digits of {a}^{k}.|What do the "
                        "last two digits of {a}^{k} come to?]", a=p["a"], k=p["k"])

    def steps(self, p: dict) -> str:
        a, k = p["a"], p["k"]
        r = k % 20
        return (f"Step 1: {a} has no factor 2 or 5, so {a}^20 ≡ 1 (mod 100) (Carmichael: λ(100) = 20). Step 2: "
                f"reduce the exponent: {k} = 20 × {k // 20} + {r}. Step 3: so {a}^{k} ≡ {a}^{r if r else 20} "
                f"(mod 100). Step 4: work it out by repeated multiplication mod 100 to get {pow(a, k, 100):02d}. "
                f"The last two digits are {pow(a, k, 100):02d}.")

    def _draw(self, rng: random.Random) -> dict:
        a = rng.choice([3, 7, 9, 11, 13, 17, 19, 21, 23, 27, 29, 31, 33, 37, 39, 41, 43, 47, 49, 51, 53, 57, 59, 61,
                        63, 67, 69, 71, 73, 77, 79, 81, 83, 87, 89, 91, 93, 97, 99])
        return dict(a=a, k=rng.randrange(150, 5000))

    def make(self, rng: random.Random, k: int, pid: str, day: int) -> Problem:
        rule = POWER_RULES[k]
        p0, pn = self._draw(rng), self._draw(rng)
        pr = dict(self._draw(rng), rule=rule)
        while self.solve(pr) == self.solve(dict(pr, rule=None)):
            pr = dict(self._draw(rng), rule=rule)
        ask, new_text, rule_text = self.question(rng, p0), self.question(rng, pn), self.question(rng, pr,
                                                                                                 rule["concept"])
        reply = say(rng, "[Using the cycle of the last digit,|Reducing the exponent mod 10,] I get {t}.",
                    t=f"{self.wrong(p0):02d}")
        correction = say(rng, "[Not quite|No], [the cycle mod 100 is 20|you need the cycle mod 100, not mod 10].") + " " + \
            self.steps(p0) + " " + say(rng, "[And for our {c}|House rule for {c}]: {t}.", c=rule["concept"],
                                       t=rule["text"])
        asks = [Ask("same", ask, self.solve(p0), self.traps(p0), p0),
                Ask("new", new_text, self.solve(pn), self.traps(pn), pn),
                Ask("rule", rule_text, self.solve(pr), self.traps(pr), pr)]
        return Problem(pid, self.name, day, ask, reply, correction, asks)


# ---------------------------------------------------------------------------------------------------------------
# 5. Choosing k of n places in a row with no two side by side: the gap method, C(n-k+1, k).

SPACING_RULES = [
    dict(kind="circle", concept="stools at the round tasting table",
         text="the tasting table is round, so the first and last stools are next to each other too"),
    dict(kind="ends_empty", concept="chafing dishes on the buffet line",
         text="on the buffet line the two end places always stay empty (the plates and the cutlery go there)"),
    dict(kind="gap2", concept="parking bays for the vans",
         text="the vans need at least two empty bays between any two vans, not one"),
    dict(kind="first_taken", concept="seats at the counter",
         text="at the counter, seat 1 is always Mama Njeri's and counts as one of the people seated"),
]


def _ok_places(chosen: tuple[int, ...], n: int, kind: str | None) -> bool:
    gap = 3 if kind == "gap2" else 2
    if any(b - a < gap for a, b in zip(chosen, chosen[1:])):
        return False
    if kind == "circle" and len(chosen) > 1 and chosen[0] + n - chosen[-1] < 2:
        return False
    if kind == "ends_empty" and (chosen[0] == 0 or chosen[-1] == n - 1):
        return False
    if kind == "first_taken" and chosen[0] != 0:
        return False
    return True


class Spacing(Family):
    name = "spacing"

    def solve(self, p: dict) -> int:
        n, k, rule = p["n"], p["k"], p.get("rule")
        kind = rule["kind"] if rule else None
        if kind == "circle":
            return comb(n - k, k) + comb(n - k - 1, k - 1)
        if kind == "ends_empty":
            return comb(n - k - 1, k)
        if kind == "gap2":
            return comb(n - 2 * (k - 1), k)
        if kind == "first_taken":
            return comb(n - k, k - 1)
        return comb(n - k + 1, k)

    def brute(self, p: dict) -> int:
        n, k, rule = p["n"], p["k"], p.get("rule")
        kind = rule["kind"] if rule else None
        return sum(1 for c in itertools.combinations(range(n), k) if _ok_places(c, n, kind))

    def trap(self, p: dict) -> list[Number]:
        return [comb(p["n"], p["k"]), comb(p["n"] - p["k"], p["k"]), self.solve(dict(p, rule=None))]

    def question(self, rng: random.Random, p: dict, concept: str | None = None) -> str:
        if concept:
            return say(rng, "[In how many ways can we use|How many ways are there to use] {k} of the {n} {c} with no "
                            "two side by side?", k=p["k"], n=p["n"], c=concept)
        return say(rng, "[In how many ways can you choose|How many ways are there to choose] {k} of {n} chairs in a "
                        "row so that no two chosen chairs are next to each other?", k=p["k"], n=p["n"])

    def steps(self, p: dict) -> str:
        n, k = p["n"], p["k"]
        return (f"Step 1: put the {k} chosen chairs down first with one empty chair between each pair: that uses "
                f"{k} + {k - 1} = {2 * k - 1} chairs. Step 2: the other {n - 2 * k + 1} empty chairs can go into the "
                f"{k + 1} gaps (before, between, after) freely. Step 3: that is the same as choosing {k} positions "
                f"out of {n} − {k} + 1 = {n - k + 1}, so C({n - k + 1}, {k}) = {fmt(self.solve(p))}.")

    def _draw(self, rng: random.Random) -> dict:
        k = rng.randrange(3, 6)
        return dict(n=rng.randrange(2 * k + 3, 21), k=k)

    def make(self, rng: random.Random, k: int, pid: str, day: int) -> Problem:
        rule = SPACING_RULES[k]
        p0, pn = self._draw(rng), self._draw(rng)
        while pn == p0:
            pn = self._draw(rng)
        pr = dict(self._draw(rng), rule=rule)
        ask, new_text, rule_text = self.question(rng, p0), self.question(rng, pn), self.question(rng, pr,
                                                                                                 rule["concept"])
        reply = say(rng, "[That's just|It's] C({n}, {k}) = {t}.", n=p0["n"], k=p0["k"], t=fmt(comb(p0["n"], p0["k"])))
        correction = say(rng, "[No, that ignores the no-neighbours rule|Not quite: C(n, k) lets chosen chairs touch].") \
            + " " + self.steps(p0) + " " + say(rng, "[And for the {c}|A rule for the {c}]: {t}.", c=rule["concept"],
                                         t=rule["text"])
        asks = [Ask("same", ask, self.solve(p0), self.traps(p0), p0),
                Ask("new", new_text, self.solve(pn), self.traps(pn), pn),
                Ask("rule", rule_text, self.solve(pr), self.traps(pr), pr)]
        return Problem(pid, self.name, day, ask, reply, correction, asks)


# ---------------------------------------------------------------------------------------------------------------
# 6. Sharing N identical things among k with at least m each: stars and bars after giving out the minimum.

SHARE_RULES = [
    dict(kind="cap", U=9, concept="mandazi trays",
         text="a mandazi tray holds at most 9, so no tray may get more than 9"),
    dict(kind="even", concept="chapati boxes",
         text="chapatis are packed in pairs, so every box must hold an even number"),
    dict(kind="first_double", concept="soda coolers",
         text="the first cooler (the one at the door) must hold at least twice the minimum"),
    dict(kind="last_cap", U=6, concept="egg crates",
         text="the last egg crate is the cracked one, so it may hold at most 6"),
]


class Share(Family):
    name = "share"

    def solve(self, p: dict) -> int:
        n, k, m, rule = p["N"], p["k"], p["m"], p.get("rule")
        kind = rule["kind"] if rule else None
        if kind == "cap":
            u = rule["U"]
            rest = n - k * m
            return sum((-1) ** j * comb(k, j) * comb(rest - j * (u - m + 1) + k - 1, k - 1)
                       for j in range(k + 1) if rest - j * (u - m + 1) >= 0)
        if kind == "even":
            return comb(n // 2 - k * (m // 2) + k - 1, k - 1) if n % 2 == 0 else 0
        if kind == "first_double":
            return comb(n - (k + 1) * m + k - 1, k - 1)
        if kind == "last_cap":
            return sum(comb(n - x - (k - 1) * m + k - 2, k - 2) for x in range(m, rule["U"] + 1)
                       if n - x - (k - 1) * m >= 0)
        return comb(n - k * m + k - 1, k - 1)

    def brute(self, p: dict) -> int:
        n, k, m, rule = p["N"], p["k"], p["m"], p.get("rule")
        kind = rule["kind"] if rule else None

        def allowed(i: int, x: int) -> bool:
            if x < m:
                return False
            if kind == "cap" and x > rule["U"]:
                return False
            if kind == "even" and x % 2:
                return False
            if kind == "first_double" and i == 0 and x < 2 * m:
                return False
            if kind == "last_cap" and i == k - 1 and x > rule["U"]:
                return False
            return True

        ways = [1] + [0] * n
        for i in range(k):
            nxt = [0] * (n + 1)
            for total, w in enumerate(ways):
                if w:
                    for x in range(n - total + 1):
                        if allowed(i, x):
                            nxt[total + x] += w
            ways = nxt
        return ways[n]

    def trap(self, p: dict) -> list[Number]:
        n, k = p["N"], p["k"]
        return [comb(n + k - 1, k - 1), comb(n - 1, k - 1), self.solve(dict(p, rule=None))]

    def question(self, rng: random.Random, p: dict, concept: str | None = None) -> str:
        if concept:
            return say(rng, "In how many ways can {N} items be shared among {k} {c} if each gets at least {m}?",
                       N=p["N"], k=p["k"], c=concept, m=p["m"])
        return say(rng, "[In how many ways can we share|How many ways are there to share] {N} identical "
                        "[mandazis|samosas|chapatis] among {k} [stalls|stands|riders], each getting at least {m}?",
                   N=p["N"], k=p["k"], m=p["m"])

    def steps(self, p: dict) -> str:
        n, k, m = p["N"], p["k"], p["m"]
        rest = n - k * m
        return (f"Step 1: give every one of the {k} their minimum of {m} first: that uses {k * m}, leaving {rest}. "
                f"Step 2: share the {rest} left over freely: stars and bars, {rest} stars and {k - 1} bars. Step 3: "
                f"C({rest} + {k - 1}, {k - 1}) = C({rest + k - 1}, {k - 1}) = {fmt(self.solve(p))}.")

    def _draw(self, rng: random.Random, even: bool = False) -> dict:
        k, m = rng.randrange(3, 6), rng.randrange(1, 4)
        if even:
            m = 2 * rng.randrange(1, 3)
        n = rng.randrange(k * m + 6, k * m + 30)
        if even and n % 2:
            n += 1
        return dict(N=n, k=k, m=m)

    def make(self, rng: random.Random, k: int, pid: str, day: int) -> Problem:
        rule = SHARE_RULES[k]
        p0, pn = self._draw(rng), self._draw(rng)
        while pn == p0:
            pn = self._draw(rng)
        while True:
            pr = dict(self._draw(rng, even=rule["kind"] == "even"), rule=rule)
            if self.solve(pr) and self.solve(pr) != self.solve(dict(pr, rule=None)):
                break
        ask, new_text, rule_text = self.question(rng, p0), self.question(rng, pn), self.question(rng, pr,
                                                                                                 rule["concept"])
        reply = say(rng, "[Stars and bars|By stars and bars]: C({a}, {b}) = {t}.", a=p0["N"] + p0["k"] - 1,
                    b=p0["k"] - 1, t=fmt(comb(p0["N"] + p0["k"] - 1, p0["k"] - 1)))
        correction = say(rng, "[That forgets the minimum|Not quite, the minimum has to come out first].") + " " + \
            self.steps(p0) + " " + say(rng, "[House rule for {c}|And for {c}]: {t}.", c=rule["concept"],
                                       t=rule["text"])
        asks = [Ask("same", ask, self.solve(p0), self.traps(p0), p0),
                Ask("new", new_text, self.solve(pn), self.traps(pn), pn),
                Ask("rule", rule_text, self.solve(pr), self.traps(pr), pr)]
        return Problem(pid, self.name, day, ask, reply, correction, asks)


# ---------------------------------------------------------------------------------------------------------------
# 7. A starter that doubles every day and is then fed less a discard: a_n = 2^n S - X(2^n - 1).

STARTER_RULES = [
    dict(kind="before", concept="the sourdough starter",
         text="in this kitchen we always discard BEFORE feeding, so each day it is (grams − discard) × 2"),
    dict(kind="alternate", concept="the mandazi yeast culture",
         text="on even-numbered days the discard is doubled, because that is when we bake twice"),
    dict(kind="skip_first", concept="the ginger bug for the dawa",
         text="nothing is discarded on day 1, the day it is started"),
    dict(kind="growing", concept="the rye starter",
         text="the discard grows by 5 grams every day: day 1 is the usual discard, day 2 is 5 g more, and so on"),
]


class Starter(Family):
    name = "starter"

    @staticmethod
    def discard(i: int, x: int, kind: str | None) -> int:
        if kind == "alternate" and i % 2 == 0:
            return 2 * x
        if kind == "skip_first" and i == 1:
            return 0
        if kind == "growing":
            return x + 5 * (i - 1)
        return x

    def solve(self, p: dict) -> int:
        s, x, n, rule = p["S"], p["X"], p["n"], p.get("rule")
        kind = rule["kind"] if rule else None
        if kind is None:
            return 2 ** n * s - x * (2 ** n - 1)
        shift = 1 if kind == "before" else 0
        return 2 ** n * s - sum(self.discard(i, x, kind) * 2 ** (n - i + shift) for i in range(1, n + 1))

    def brute(self, p: dict) -> int:
        a, x, rule = p["S"], p["X"], p.get("rule")
        kind = rule["kind"] if rule else None
        for i in range(1, p["n"] + 1):
            d = self.discard(i, x, kind)
            a = (a - d) * 2 if kind == "before" else a * 2 - d
        return a

    def trap(self, p: dict) -> list[Number]:
        s, x, n = p["S"], p["X"], p["n"]
        return [2 ** n * s - n * x, 2 ** n * (s - x), self.solve(dict(p, rule=None))]

    def question(self, rng: random.Random, p: dict, concept: str | None = None) -> str:
        if concept:
            return say(rng, "{c} starts at {S} g; every day it doubles and we discard {X} g. How many grams after "
                            "{n} days?", c=concept[:1].upper() + concept[1:], S=p["S"], X=p["X"], n=p["n"])
        return say(rng, "[A starter|Our culture] starts at {S} g. Each day it doubles, then {X} g is taken out. "
                        "[How many grams are there|What does it weigh] after {n} days?", S=p["S"], X=p["X"], n=p["n"])

    def steps(self, p: dict) -> str:
        s, x, n = p["S"], p["X"], p["n"]
        return (f"Step 1: write a(i) = 2·a(i−1) − {x}. Step 2: each discard keeps doubling afterwards, so after "
                f"{n} days the start has grown to 2^{n} × {s} = {fmt(2 ** n * s)} and the discards to {x} × "
                f"(2^{n - 1} + … + 2 + 1) = {x} × (2^{n} − 1) = {fmt(x * (2 ** n - 1))}. Step 3: {fmt(2 ** n * s)} − "
                f"{fmt(x * (2 ** n - 1))} = {fmt(self.solve(p))} g.")

    def _draw(self, rng: random.Random) -> dict:
        x = rng.choice([10, 15, 20, 25, 30, 40, 50])
        return dict(S=rng.randrange(3 * x, 8 * x), X=x, n=rng.randrange(5, 11))

    def make(self, rng: random.Random, k: int, pid: str, day: int) -> Problem:
        rule = STARTER_RULES[k]
        p0, pn = self._draw(rng), self._draw(rng)
        while True:
            pr = dict(self._draw(rng), rule=rule)
            if self.brute(pr) > 0:
                break
        ask, new_text, rule_text = self.question(rng, p0), self.question(rng, pn), self.question(rng, pr,
                                                                                                 rule["concept"])
        reply = say(rng, "[It doubles {n} times and loses {X} g a day|Double {n} times, minus {n} discards]: "
                         "{t} g.", n=p0["n"], X=p0["X"], t=fmt(self.wrong(p0)))
        correction = say(rng, "[No: each discard also misses out on the doubling that comes after it|Not quite, the "
                              "early discards would have doubled too].") + " " + self.steps(p0) + " " + \
            say(rng, "[And for {c}|Kitchen rule for {c}]: {t}.", c=rule["concept"], t=rule["text"])
        asks = [Ask("same", ask, self.solve(p0), self.traps(p0), p0),
                Ask("new", new_text, self.solve(pn), self.traps(pn), pn),
                Ask("rule", rule_text, self.solve(pr), self.traps(pr), pr)]
        return Problem(pid, self.name, day, ask, reply, correction, asks)


# ---------------------------------------------------------------------------------------------------------------
# 8. Paying exactly N with packs of a and b: solutions of a x + b y = N with x, y >= 0.

PACK_RULES = [
    dict(kind="both", concept="chapati packs",
         text="every chapati order must contain at least one pack of each size"),
    dict(kind="pairs", concept="egg trays",
         text="small egg trays are only sold in pairs, so the number of small trays must be even"),
    dict(kind="max_big", Y=3, concept="juice bottles",
         text="we never have more than 3 of the big bottles in stock, so at most 3 big ones"),
    dict(kind="min_big", concept="samosa boxes",
         text="a samosa order always includes at least 2 big boxes (one for the office, one for the driver)"),
]


class Packs(Family):
    name = "packs"

    def solve(self, p: dict) -> int:
        a, b, n, rule = p["a"], p["b"], p["N"], p.get("rule")
        kind = rule["kind"] if rule else None
        if kind == "both":
            n -= a + b
        elif kind == "pairs":
            a *= 2
        elif kind == "min_big":
            n -= 2 * b
        if n < 0:
            return 0
        g = math.gcd(a, b)
        if n % g:
            return 0
        a2, b2, n2 = a // g, b // g, n // g
        y0 = (n2 * pow(b2, -1, a2)) % a2 if a2 > 1 else 0  # smallest y with b*y = n (mod a)
        if b2 * y0 > n2:
            return 0
        ys = (n2 - b2 * y0) // (a2 * b2) + 1  # y = y0, y0 + a2, ... while b*y <= n
        if kind == "max_big":
            if y0 > rule["Y"]:
                return 0
            ys = min(ys, (rule["Y"] - y0) // a2 + 1)
        return ys

    def brute(self, p: dict) -> int:
        a, b, n, rule = p["a"], p["b"], p["N"], p.get("rule")
        kind = rule["kind"] if rule else None
        count = 0
        for y in range(n // b + 1):
            for x in range(n // a + 1):
                if a * x + b * y != n:
                    continue
                if kind == "both" and (x < 1 or y < 1):
                    continue
                if kind == "pairs" and x % 2:
                    continue
                if kind == "max_big" and y > rule["Y"]:
                    continue
                if kind == "min_big" and y < 2:
                    continue
                count += 1
        return count

    def trap(self, p: dict) -> list[Number]:
        a, b, n = p["a"], p["b"], p["N"]
        return [n // (a * b) + 1, n // b + 1, n // math.lcm(a, b), self.solve(dict(p, rule=None))]

    def question(self, rng: random.Random, p: dict, concept: str | None = None) -> str:
        if concept:
            return say(rng, "With {c} of {a} and {b}, in how many ways can we make up an order of exactly {N}?",
                       c=concept, a=p["a"], b=p["b"], N=p["N"])
        return say(rng, "[Chapatis come in packs of {a} and {b}.|We sell packs of {a} and of {b}.] [In how many ways "
                        "can|How many ways can] a customer buy exactly {N}?", a=p["a"], b=p["b"], N=p["N"])

    def steps(self, p: dict) -> str:
        a, b, n = p["a"], p["b"], p["N"]
        sols = [(x, (n - a * x) // b) for x in range(n // a + 1) if (n - a * x) % b == 0]
        listed = ", ".join(f"({x}, {y})" for x, y in sols[:6]) + (", …" if len(sols) > 6 else "")
        g = math.gcd(a, b)
        return (f"Step 1: we need whole x, y ≥ 0 with {a}x + {b}y = {n}; gcd({a}, {b}) = {g} divides {n}, so "
                f"solutions exist. Step 2: find one solution and step: x goes up by {b // g} while y goes down by "
                f"{a // g}. Step 3: listing them, (x, y) = {listed}. That is {len(sols)} ways.")

    def _draw(self, rng: random.Random) -> dict:
        while True:
            a, b = sorted(rng.sample([4, 5, 6, 7, 8, 9, 10, 12, 15, 18, 20, 25], 2))
            n = rng.randrange(60, 260)
            p = dict(a=a, b=b, N=n)
            if self.solve(p) >= 3:
                return p

    def make(self, rng: random.Random, k: int, pid: str, day: int) -> Problem:
        rule = PACK_RULES[k]
        p0, pn = self._draw(rng), self._draw(rng)
        while True:
            pr = dict(self._draw(rng), rule=rule)
            if self.solve(pr) and self.solve(pr) != self.solve(dict(pr, rule=None)):
                break
        ask, new_text, rule_text = self.question(rng, p0), self.question(rng, pn), self.question(rng, pr,
                                                                                                 rule["concept"])
        reply = say(rng, "[Roughly|About] {t} ways.", t=self.wrong(p0))
        correction = say(rng, "[Not quite, you have to actually solve the equation|No, count the solutions "
                              "properly].") + " " + self.steps(p0) + " " + say(rng, "[A rule for {c}|And for {c}]: {t}.",
                                                                          c=rule["concept"], t=rule["text"])
        asks = [Ask("same", ask, self.solve(p0), self.traps(p0), p0),
                Ask("new", new_text, self.solve(pn), self.traps(pn), pn),
                Ask("rule", rule_text, self.solve(pr), self.traps(pr), pr)]
        return Problem(pid, self.name, day, ask, reply, correction, asks)


# ---------------------------------------------------------------------------------------------------------------
# 9. Grid routes east and north that avoid a closed junction: all routes minus those through it.

GRID_RULES = [
    dict(kind="through", concept="the cash run",
         text="on the cash run the rider must pass the bank at a given junction, and the closed junction is open "
              "again by then"),
    dict(kind="two_blocks", concept="the market-day route",
         text="on market day a second junction is closed too"),
    dict(kind="diagonal", concept="the waiters' floor plan",
         text="on the floor plan a waiter may also cut one square diagonally (north-east) in a single move"),
    dict(kind="top_last", concept="the CBD delivery route",
         text="the top street is one-way, so the rider may only enter the top row at the very last junction"),
]


def delannoy(a: int, b: int) -> int:
    return sum(comb(a, k) * comb(b, k) * 2 ** k for k in range(min(a, b) + 1))


def routes(a: int, b: int) -> int:
    return comb(a + b, a) if a >= 0 and b >= 0 else 0


class Grid(Family):
    name = "grid"

    def solve(self, p: dict) -> int:
        a, b, (i, j), rule = p["a"], p["b"], p["block"], p.get("rule")
        kind = rule["kind"] if rule else None
        if kind == "through":
            (u, v) = rule_point(p)
            return routes(u, v) * routes(a - u, b - v)
        if kind == "two_blocks":
            (i2, j2) = p["block2"]
            both = routes(i, j) * routes(i2 - i, j2 - j) * routes(a - i2, b - j2)
            return (routes(a, b) - routes(i, j) * routes(a - i, b - j) - routes(i2, j2) * routes(a - i2, b - j2)
                    + both)
        if kind == "diagonal":
            return delannoy(a, b) - delannoy(i, j) * delannoy(a - i, b - j)
        if kind == "top_last":
            return routes(a, b - 1) - (routes(i, j) * routes(a - i, b - 1 - j) if j <= b - 1 else 0)
        return routes(a, b) - routes(i, j) * routes(a - i, b - j)

    def brute(self, p: dict) -> int:
        a, b, rule = p["a"], p["b"], p.get("rule")
        kind = rule["kind"] if rule else None
        closed = set() if kind == "through" else {tuple(p["block"])}
        if kind == "two_blocks":
            closed.add(tuple(p["block2"]))
        moves = [(1, 0), (0, 1)] + ([(1, 1)] if kind == "diagonal" else [])
        must = tuple(rule_point(p)) if kind == "through" else None
        ways: dict[tuple[int, int, bool], int] = {(0, 0, must == (0, 0)): 1}
        total = 0
        for s in range(a + b + 1):
            for (x, y, hit), w in list(ways.items()):
                if x + y != s:
                    continue
                if (x, y) == (a, b):
                    total += w if (must is None or hit) else 0
                    continue
                for dx, dy in moves:
                    nx, ny = x + dx, y + dy
                    if nx > a or ny > b or (nx, ny) in closed:
                        continue
                    if kind == "top_last" and ny == b and nx != a:
                        continue
                    key = (nx, ny, hit or (nx, ny) == must)
                    ways[key] = ways.get(key, 0) + w
        return total

    def trap(self, p: dict) -> list[Number]:
        return [routes(p["a"], p["b"]), routes(p["a"], p["b"]) - 1, self.solve(dict(p, rule=None))]

    def question(self, rng: random.Random, p: dict, concept: str | None = None) -> str:
        a, b, (i, j) = p["a"], p["b"], p["block"]
        extra = ""
        if concept and p["rule"]["kind"] == "through":
            u, v = rule_point(p)
            extra = f" The bank is at ({u}, {v})."
        if concept and p["rule"]["kind"] == "two_blocks":
            extra = f" The second closed junction is ({p['block2'][0]}, {p['block2'][1]})."
        if concept:
            return say(rng, "For {c}: from (0, 0) to ({a}, {b}), with the junction at ({i}, {j}) closed, how many "
                            "routes are there?{e}", c=concept, a=a, b=b, i=i, j=j, e=extra)
        return say(rng, "A rider goes from (0, 0) to ({a}, {b}) on a street grid, [moving only east or north|one block "
                        "east or north at a time]. The junction at ({i}, {j}) is closed. How many routes are there?",
                   a=a, b=b, i=i, j=j)

    def steps(self, p: dict) -> str:
        a, b, (i, j) = p["a"], p["b"], p["block"]
        through = routes(i, j) * routes(a - i, b - j)
        return (f"Step 1: all routes: C({a + b}, {a}) = {fmt(routes(a, b))}. Step 2: routes through ({i}, {j}): "
                f"C({i + j}, {i}) × C({a - i + b - j}, {a - i}) = {routes(i, j)} × {routes(a - i, b - j)} = "
                f"{fmt(through)}. Step 3: {fmt(routes(a, b))} − {fmt(through)} = {fmt(self.solve(p))}.")

    def _draw(self, rng: random.Random) -> dict:
        a, b = rng.randrange(4, 8), rng.randrange(3, 7)
        return dict(a=a, b=b, block=[rng.randrange(1, a), rng.randrange(1, b)])

    def make(self, rng: random.Random, k: int, pid: str, day: int) -> Problem:
        rule = GRID_RULES[k]
        p0, pn = self._draw(rng), self._draw(rng)
        while pn == p0:
            pn = self._draw(rng)
        while True:
            pr = dict(self._draw(rng), rule=rule)
            if rule["kind"] == "two_blocks":
                i, j = pr["block"]
                if i + 1 >= pr["a"] or j + 1 >= pr["b"]:
                    continue
                pr["block2"] = [rng.randrange(i + 1, pr["a"]), rng.randrange(j + 1, pr["b"])]
            if rule["kind"] == "through":
                pr["point"] = [rng.randrange(1, pr["a"]), rng.randrange(1, pr["b"])]
                if pr["point"] == pr["block"]:
                    continue
            if self.solve(pr) != self.solve(dict(pr, rule=None)) and self.solve(pr) > 0:
                break
        ask, new_text, rule_text = self.question(rng, p0), self.question(rng, pn), self.question(rng, pr,
                                                                                                 rule["concept"])
        reply = say(rng, "[That's|It's] C({n}, {a}) = {t}.", n=p0["a"] + p0["b"], a=p0["a"], t=fmt(routes(p0["a"],
                                                                                                         p0["b"])))
        correction = say(rng, "[That counts the routes through the closed junction too|Not quite, take out the routes "
                              "through the closure].") + " " + self.steps(p0) + " " + \
            say(rng, "[A rule for {c}|And for {c}]: {t}.", c=rule["concept"], t=rule["text"])
        asks = [Ask("same", ask, self.solve(p0), self.traps(p0), p0),
                Ask("new", new_text, self.solve(pn), self.traps(pn), pn),
                Ask("rule", rule_text, self.solve(pr), self.traps(pr), pr)]
        return Problem(pid, self.name, day, ask, reply, correction, asks)


def rule_point(p: dict) -> list[int]:
    return p["point"]


# ---------------------------------------------------------------------------------------------------------------
# 10. Leftovers in piles of three sizes: the Chinese remainder theorem.

REMAINDER_RULES = [
    dict(kind="above", B=1000, concept="batch numbers",
         text="batch numbers start above 1,000, so we want the smallest such number above 1,000"),
    dict(kind="count", L=5000, concept="pallet counts",
         text="a pallet count means how many such numbers there are up to 5,000, not the smallest"),
    dict(kind="largest", L=3000, concept="tray stacks",
         text="for tray stacks we want the largest such number below 3,000"),
    dict(kind="even", concept="bread rolls",
         text="bread rolls are baked in twos, so the number must also be even"),
]
MODULI = [(3, 5, 7), (4, 5, 7), (5, 7, 9), (3, 7, 8), (4, 7, 9), (5, 8, 9), (7, 9, 11), (3, 8, 11), (4, 9, 11),
          (5, 7, 11), (3, 5, 11), (7, 8, 9)]


def crt(rs: list[int], ms: list[int]) -> tuple[int, int]:
    """The least non-negative n with n = r_i (mod m_i), and the product of the moduli."""
    big = math.prod(ms)
    n = sum(r * (big // m) * pow(big // m, -1, m) for r, m in zip(rs, ms)) % big
    return n, big


class Remainders(Family):
    name = "remainders"

    def solve(self, p: dict) -> int:
        rs, ms, rule = p["rs"], p["ms"], p.get("rule")
        kind = rule["kind"] if rule else None
        if kind == "even" and all(m % 2 for m in ms):
            rs, ms = rs + [0], ms + [2]
        n, big = crt(rs, ms)
        if kind == "even" and not all(m % 2 for m in p["ms"]):
            raise ValueError("even rule needs odd moduli")
        n = n or big
        if kind == "above":
            return n + max(0, -(-(rule["B"] + 1 - n) // big)) * big
        if kind == "count":
            return (rule["L"] - n) // big + 1 if n <= rule["L"] else 0
        if kind == "largest":
            return n + (rule["L"] - 1 - n) // big * big
        return n

    def brute(self, p: dict) -> int:
        rs, ms, rule = p["rs"], p["ms"], p.get("rule")
        kind = rule["kind"] if rule else None

        def fits(n: int) -> bool:
            return all(n % m == r for r, m in zip(rs, ms)) and (kind != "even" or n % 2 == 0)

        if kind == "count":
            return sum(1 for n in range(1, rule["L"] + 1) if fits(n))
        if kind == "largest":
            return max(n for n in range(1, rule["L"]) if fits(n))
        start = rule["B"] + 1 if kind == "above" else 1
        n = start
        while not fits(n):
            n += 1
        return n

    def trap(self, p: dict) -> list[Number]:
        rs, ms = p["rs"], p["ms"]
        two, m2 = crt(rs[:2], ms[:2])
        return [two or m2, math.prod(ms) - 1, self.solve(dict(p, rule=None))]

    def question(self, rng: random.Random, p: dict, concept: str | None = None) -> str:
        (r1, r2, r3), (m1, m2, m3) = p["rs"], p["ms"]
        lead = f"For {concept}: a" if concept else say(rng, "[Mama Njeri counts the chapatis:|Counting the samosas:] a")
        tail = {"above": "What is the smallest such number above 1,000?", "count": "How many such numbers are there "
                "up to 5,000?", "largest": "What is the largest such number below 3,000?"}
        kind = p["rule"]["kind"] if concept else None
        q = tail.get(kind, "What is the smallest positive number that fits?")
        return (f"{lead} number leaves {r1} over in piles of {m1}, {r2} over in piles of {m2} and {r3} over in piles "
                f"of {m3}. {q}")

    def steps(self, p: dict) -> str:
        (r1, r2, r3), (m1, m2, m3) = p["rs"], p["ms"]
        big = m1 * m2 * m3
        parts = []
        for r, m in zip(p["rs"], p["ms"]):
            mm = big // m
            parts.append(f"{mm} × {pow(mm, -1, m)} ≡ 1 (mod {m})")
        n, _ = crt(p["rs"], p["ms"])
        return (f"Step 1: the moduli {m1}, {m2}, {m3} share no factor, so there is exactly one answer below "
                f"{m1} × {m2} × {m3} = {big}. Step 2: for each modulus take the product of the other two and its "
                f"inverse: {'; '.join(parts)}. Step 3: combine: {r1}·{big // m1}·{pow(big // m1, -1, m1)} + "
                f"{r2}·{big // m2}·{pow(big // m2, -1, m2)} + {r3}·{big // m3}·{pow(big // m3, -1, m3)}, reduced mod "
                f"{big}, is {n or big}. Check: {n or big} leaves {r1}, {r2}, {r3}.")

    def _draw(self, rng: random.Random, odd: bool = False) -> dict:
        while True:
            ms = list(rng.choice(MODULI))
            if odd and not all(m % 2 for m in ms):
                continue
            rs = [rng.randrange(1, m) for m in ms]
            return dict(rs=rs, ms=ms)

    def make(self, rng: random.Random, k: int, pid: str, day: int) -> Problem:
        rule = REMAINDER_RULES[k]
        p0, pn = self._draw(rng), self._draw(rng)
        while True:
            pr = dict(self._draw(rng, odd=rule["kind"] == "even"), rule=rule)
            if self.solve(pr) != self.solve(dict(pr, rule=None)):
                break
        ask, new_text, rule_text = self.question(rng, p0), self.question(rng, pn), self.question(rng, pr,
                                                                                                 rule["concept"])
        reply = say(rng, "[Trying the first two conditions|From the first two piles], {t}.", t=self.wrong(p0))
        correction = say(rng, "[That one fails the third pile|Check the third condition: it fails].") + " " + \
            self.steps(p0) + " " + say(rng, "[Rule for {c}|And for {c}]: {t}.", c=rule["concept"], t=rule["text"])
        asks = [Ask("same", ask, self.solve(p0), self.traps(p0), p0),
                Ask("new", new_text, self.solve(pn), self.traps(pn), pn),
                Ask("rule", rule_text, self.solve(pr), self.traps(pr), pr)]
        return Problem(pid, self.name, day, ask, reply, correction, asks)


FAMILIES: dict[str, Family] = {f.name: f for f in (Fee(), Squares(), Union(), Powers(), Spacing(), Share(), Starter(),
                                                   Packs(), Grid(), Remainders())}
PER_FAMILY = 4  # 10 families x 4 = 40 problems


def problems(rng: random.Random, days: int) -> list[Problem]:
    """The 40 problems with the day each is first asked. The two doc samples keep their days (3 and 9)."""
    slots = sorted(rng.sample([d for d in range(2, min(days, 86)) if d not in (3, 9)], len(FAMILIES) * PER_FAMILY - 2))
    out: list[Problem] = []
    order = [(name, k) for k in range(PER_FAMILY) for name in FAMILIES]
    rng.shuffle(order)
    order.remove(("fee", 0))
    order.remove(("squares", 0))
    for i, (name, k) in enumerate([("fee", 0), ("squares", 0)] + order):
        day = 3 if i == 0 else 9 if i == 1 else slots[i - 2]
        out.append(FAMILIES[name].make(random.Random(f"{rng.random()}:{name}:{k}"), k, f"maths-{i + 1:02d}", day))
    return sorted(out, key=lambda p: (p.day, p.pid))


def lesson_example(rng: random.Random, name: str) -> tuple[str, str]:
    """A worked example of a family's plain method (no house rule), for the course notes in the noise."""
    fam = FAMILIES[name]
    if name == "fee":
        raise ValueError("the fee rule is never taught in the course notes")
    p = fam._draw(rng) if hasattr(fam, "_draw") else None
    if name == "squares":
        a, q = rng.choice(SQUARE_PAIRS)
        p = dict(a=a, p=q, N=rng.randrange(100, 3000))
    if name == "union":
        p = dict(divs=list(rng.choice(DIVISOR_SETS)), N=rng.randrange(200, 5000))
    return fam.question(rng, p), fam.steps(p)
