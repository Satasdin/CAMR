"""How an answer is marked right or wrong, and the sign test. Used by run.py and score.py."""
import math
import re
import unicodedata

_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_SPACE = re.compile(r"\s+")
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?")
# A file reference such as "Garden/irrigation.md:3" or "notes.md:12-14". Burrow's answers end with
# these, and their line numbers are not the model's answer to a sum.
_FILE_REF = re.compile(r"""[\w./\\-]+\.[A-Za-z]{1,6}["'`*]{0,3}:\d+(?:\s*[-–]\s*\d+)?""")


def visible(answer):
    """The answer without any private reasoning the model printed."""
    return _THINK.sub(" ", answer or "")


def normalise(text):
    """Lower case, single spaces, and 12,000 written as 12000."""
    text = unicodedata.normalize("NFKC", text or "")
    text = _THOUSANDS.sub("", text)
    return _SPACE.sub(" ", text).strip().lower()


def includes_all(answer, must_include):
    """True when every group has at least one of its strings in the answer."""
    if not must_include:
        return False
    hay = normalise(visible(answer))
    for group in must_include:
        if isinstance(group, str):
            group = [group]
        if not any(normalise(alt) and normalise(alt) in hay for alt in group):
            return False
    return True


def last_number(answer):
    """The last number written in the answer, as a float, or None."""
    text = _THOUSANDS.sub("", visible(answer))
    text = _FILE_REF.sub(" ", text)
    found = _NUMBER.findall(text)
    return float(found[-1]) if found else None


def last_number_is(answer, expected):
    got = last_number(answer)
    if got is None:
        return False
    want = float(_THOUSANDS.sub("", str(expected)).replace(",", "").strip())
    return math.isclose(got, want, rel_tol=1e-9, abs_tol=1e-9)


def is_correct(task, answer):
    if not answer:
        return False
    if task.get("type") == "reasoning":
        return last_number_is(answer, task["answer"])
    return includes_all(answer, task.get("must_include") or [])


def sign_test(wins, losses):
    """Exact two-sided sign test on the pairs that disagree. Returns the p value."""
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)
