"""LongMemEval S (Wu et al., 2024), cleaned: 500 questions, each over its own history of about 50 chat sessions
(about 115K tokens). The sessions are the chunks, oldest first. 30 questions are about things never said
(ids ending "_abs"): declining them is right.

Grading needs a judge model. ``judge_prompt`` gives the text to send it (the Claude runner sends it to
claude-haiku-5-5); ``verdict_from_judge`` reads its yes or no. The prompts follow the benchmark's rules for each kind
of question: an off-by-one count of days is let through for time questions, an answer that also names the old value
is right for updates, a preference answer is held to a rubric, and an "_abs" question wants a decline. ``precheck``
settles a reply that is the answer exactly, with no judge.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from camr_engine.bench.suites.common import Item, clean, data_dir, estimate_tokens, rng
from camr_engine.bench.suites.memoryagentbench import normalize, parsed
from camr_engine.ruler.grade import abstains

NAME = "longmemeval"
REPO = "xiaowu0162/longmemeval-cleaned"
REVISION = "98d7416c24c778c2fee6e6f3006e7a073259d48f"
FILE = "longmemeval_s_cleaned.json"
OLD_CACHE = Path.home() / ".cache" / "camr-bench" / "longmemeval" / FILE  # where the old CAMR runs downloaded it
JUDGE_MODEL = "claude-haiku-5-5"
INSTRUCTION = "Answer the question from the chat history. If the history never says, say that you don't know."


class NeedsJudge(Exception):
    """The rule check can't settle this reply: grade it with a judge (pass ``judge=`` to ``grade``)."""


def path() -> Path:
    """The S file: in ``data_dir("longmemeval")``, else the old CAMR cache, else downloaded (277 MB)."""
    p = data_dir("longmemeval") / FILE
    if p.exists():
        return p
    if OLD_CACHE.exists():
        return OLD_CACHE
    from huggingface_hub import hf_hub_download

    return Path(hf_hub_download(REPO, FILE, repo_type="dataset", revision=REVISION, local_dir=data_dir("longmemeval")))


def when(text: str) -> dt.datetime:
    """'2023/04/10 (Mon) 17:50' -> that moment."""
    day, _, rest = text.partition(" ")
    hm = rest.split(")")[-1].strip() or "00:00"
    return dt.datetime.strptime(f"{day} {hm}", "%Y/%m/%d %H:%M")


def session_text(date: str, turns: list[dict]) -> str:
    lines = [f"{t['role']}: {t['content'].strip()}" for t in turns if str(t.get("content", "")).strip()]
    return f"[Chat session, {date}]\n" + "\n".join(lines)


def _item(x: dict) -> Item:
    sessions = sorted(zip(x["haystack_dates"], x["haystack_session_ids"], x["haystack_sessions"]),
                      key=lambda s: when(s[0]))
    chunks = [session_text(d, turns) for d, _, turns in sessions]
    return Item(id=f"longmemeval/{x['question_id']}", suite=NAME, context=chunks, question=x["question"],
                answer=str(x["answer"]), length_tokens=estimate_tokens(chunks),
                meta={"kind": x["question_type"], "question_date": x["question_date"],
                      "abstention": x["question_id"].endswith("_abs"),
                      "answer_sessions": list(x.get("answer_session_ids") or []),
                      "session_ids": [s for _, s, _ in sessions], "instruction": INSTRUCTION})


def load(limit: int | None = None, *, file: Any = None) -> list[Item]:
    """The questions, in the file's order."""
    raw = json.loads(Path(file or path()).read_text())
    return [_item(x) for x in (raw[:limit] if limit else raw)]


def sample(n: int, seed: int = 0, *, file: Any = None) -> list[Item]:
    """``n`` questions of each kind, chosen by the seed."""
    by_kind: dict[str, list[Item]] = defaultdict(list)
    for it in load(file=file):
        by_kind[it.meta["kind"]].append(it)
    out = []
    for kind in sorted(by_kind):
        items = by_kind[kind]
        out += [items[k] for k in sorted(rng(seed, NAME, kind).sample(range(len(items)), min(n, len(items))))]
    return out


def prompt(item: Item) -> str:
    return (f"Current date: {item.meta['question_date']}\n{item.meta['instruction']}\n\n"
            f"Question: {item.question}\nAnswer:")


# ---------------------------------------------------------------- judging

_RULES = {
    "default": ("Say yes if the response contains the correct answer, or says something that means the same. Also "
                "say yes if it shows every step needed to reach the correct answer. Say no if it gives only part of "
                "what the correct answer needs, or something else."),
    "temporal-reasoning": ("Say yes if the response contains the correct answer, or says something that means the "
                           "same. Also say yes if it shows every step needed to reach the correct answer. Say no if "
                           "it gives only part of what the correct answer needs, or something else. Do not count an "
                           "off-by-one error in a number of days, weeks or months against it: if the correct answer "
                           "is 18 days, 19 days is also right."),
    "knowledge-update": ("Say yes if the response contains the correct answer, or says something that means the "
                         "same. If it also mentions older information but gives the updated answer as the current "
                         "one, that is still yes. Say no if it gives an older value as the answer, or something "
                         "else."),
    "single-session-preference": ("The rubric describes what a good, personal reply would do. Say yes if the "
                                  "response remembers and uses the user's own information as the rubric describes; it "
                                  "need not cover every point. Say no if it is generic, or goes against the rubric."),
}


def judge_prompt(item: Item, answer: str) -> str:
    """The text to send the judge. Its reply should be one word, yes or no."""
    reply = clean(answer)
    if item.should_decline:
        return ("I will give you a question about a user's chat history, a note on why it can't be answered from "
                "that history, and a response from a model.\n\n"
                "Say yes if the response says it can't answer, that it doesn't have that information, or points out "
                "that what the question asks about was never mentioned. Say no if it answers the question anyway.\n\n"
                f"Question: {item.question}\n\nNote: {item.answer}\n\nResponse: {reply}\n\n"
                "Did the model correctly decline? Reply with one word: yes or no.")
    kind = item.meta.get("kind", "")
    rules = _RULES.get(kind, _RULES["default"])
    label = "Rubric" if kind == "single-session-preference" else "Correct answer"
    return ("I will give you a question about a user's chat history, the correct answer, and a response from a "
            "model.\n\n" + rules + "\n\n"
            f"Question: {item.question}\n\n{label}: {item.answer}\n\nResponse: {reply}\n\n"
            "Is the model's response right? Reply with one word: yes or no.")


def parse_judge(text: str | None) -> bool | None:
    """The judge's yes (True) or no (False); None when it said neither first."""
    words = clean(text).lower().replace("*", " ").replace(".", " ").split()
    for w in words[:3]:
        if w.strip(":,!\"'") in ("yes", "no"):
            return w.strip(":,!\"'") == "yes"
    return None


def verdict_from_judge(item: Item, answer: str, judge_reply: str | None) -> str:
    """The verdict, given the judge's reply to ``judge_prompt(item, answer)``; "judge_error" if it said neither."""
    yes = parse_judge(judge_reply)
    if yes is None:
        return "judge_error"
    if item.should_decline:
        return "right_abstain" if yes else "false_memory"
    if yes:
        return "right"
    return "declined" if abstains(clean(answer)) else "wrong"


def precheck(item: Item, answer: str) -> str | None:
    """"right" when the reply, whole or after "Answer:", is the answer itself; None when only a judge can say."""
    if item.should_decline or item.meta.get("kind") == "single-session-preference":
        return None
    text = clean(answer)
    gold = normalize(str(item.answer))
    return "right" if gold and gold in {normalize(text), normalize(parsed(text))} else None


def grade(item: Item, reply: str, judge: Callable[[str], str] | None = None, **_: Any) -> str:
    """The rule pre-check, then the judge. Without a judge, a reply the pre-check can't settle raises NeedsJudge."""
    pre = precheck(item, reply)
    if pre is not None:
        return pre
    if judge is None:
        raise NeedsJudge(item.id)
    return verdict_from_judge(item, reply, judge(judge_prompt(item, reply)))
