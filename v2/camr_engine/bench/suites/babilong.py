"""BABILong (Kuratov et al., 2024): bAbI facts hidden in book text, at 4k to 1M tokens.

Each task file holds 100 stories, and story i has the same question and answer at every length, in more or less
book text. So a sample takes the same stories at every length, and the curve over length compares like with like.

The files for 4k and 16k are small (1.5 and 6.3 MB) and come down whole. From 64k up a file is 25 MB to 400 MB, so a
story is read alone, by byte range out of the JSON file: a guess at its offset lands near it, the story's question,
answer and facts tell which one is there, and a step or two lands on the one wanted (usually two requests, about
1.5 times the story's size). The facts come from the facts-only ``0k`` file, which holds the same stories except
qa3 86-99 and qa5 99; those 15 are fetched from the Hub's rows API instead, by number. Each story is kept on disk
once fetched.

Grading follows the dataset's own rule (``compare_answers`` in github.com/booydar/babilong): the reply's first
sentence must name the answer and no other word from the task's answer set, not counting words the question names.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import IO, Any, Callable

from camr_engine.bench.suites.common import Item, clean, data_dir, estimate_tokens, rng, verdict

NAME = "babilong"
REPO = "RMT-team/babilong"
REVISION = "ee0d588794c7ac098062ee0d247c733d62e94fe2"
ROWS_API = "https://datasets-server.huggingface.co/rows"
TASKS = ("qa1", "qa2", "qa3", "qa4", "qa5")
LENGTHS = ("4k", "16k", "64k", "128k", "256k", "512k", "1M")
STORIES = 100
WHOLE = {"0k", "1k", "2k", "4k", "8k", "16k"}  # at most 6.4 MB a file: fetched whole
MARK = b'{"input": "'  # starts every story; inside a JSON string the quote would be escaped, so it marks only starts
STEP = 1 << 20  # the largest read; a read is about a quarter of a story, at least 64 KB
MIN_STEP = 1 << 16
HOPS = 12

# every answer a task can have (TASK_LABELS in the dataset's metrics)
LABELS = {
    "qa1": ("bathroom", "bedroom", "garden", "hallway", "kitchen", "office"),
    "qa2": ("bathroom", "bedroom", "garden", "hallway", "kitchen", "office"),
    "qa3": ("bathroom", "bedroom", "garden", "hallway", "kitchen", "office"),
    "qa4": ("bathroom", "bedroom", "garden", "hallway", "kitchen", "office"),
    "qa5": ("Bill", "Fred", "Jeff", "Mary", "apple", "football", "milk"),
}

# the answer shape each task asks for, after the dataset's prompts
FORMAT = {
    "qa1": "Answer in this form: The most recent location of <person> is <location>.",
    "qa2": "Answer in this form: The <item> is in <location>.",
    "qa3": "Answer in this form: Before the <location 1> the <item> was in the <location 2>.",
    "qa4": "Answer with one word: the location.",
    "qa5": "Answer with one word.",
}
INSTRUCTION = ("The context hides facts about people, places and things among unrelated book text. Answer the question "
               "from those facts only; when a fact changes, the latest one counts.")

Opener = Callable[[str, str], tuple[IO[bytes], int]]
RowGetter = Callable[[str, str, int], "dict | None"]


def _hub_open(task: str, length: str) -> tuple[IO[bytes], int]:
    from huggingface_hub import HfFileSystem

    f = HfFileSystem().open(f"datasets/{REPO}@{REVISION}/data/{task}/{length}.json", "rb", block_size=STEP,
                            cache_type="none")
    return f, f.size


def _api_row(task: str, length: str, i: int, tries: int = 3, timeout: float = 180.0) -> dict | None:
    """Story ``i`` from the Hub's rows API, or None when the API fails or cuts the row short."""
    from huggingface_hub.utils import get_session

    url = f"{ROWS_API}?dataset={REPO}&config={length}&split={task}&offset={i}&length=1"
    for attempt in range(tries):
        try:
            r = get_session().get(url, timeout=timeout)
            if r.status_code == 200:
                rows = r.json().get("rows") or []
                if rows and rows[0].get("row_idx") == i and not rows[0].get("truncated_cells"):
                    row = rows[0]["row"]
                    return {"input": row["input"], "question": row["question"], "target": row["target"]}
                return None
        except Exception:
            pass
        time.sleep(2 ** attempt)
    return None


class Store:
    """Where stories come from, all kept on disk under ``root``. ``opener`` gives a seekable JSON file and its size
    for byte-range reads (the Hub by default); ``api`` fetches one story by number for the stories whose facts are
    unknown (the Hub's rows API by default; None reads those by byte range too, telling them apart by position)."""

    def __init__(self, root: Path | None = None, opener: Opener | None = None, api: RowGetter | None = _api_row):
        self.root = Path(root) if root else data_dir("babilong")
        self.opener, self.api = opener, api
        self._rows: dict[tuple[str, str], list[dict]] = {}

    def rows(self, task: str, length: str) -> list[dict]:
        """A whole file's stories."""
        key = (task, length)
        if key not in self._rows:
            name = f"data/{task}/{length}.json"
            path = self.root / name
            if not path.exists():
                if self.opener is None:
                    from huggingface_hub import hf_hub_download

                    hf_hub_download(REPO, name, repo_type="dataset", revision=REVISION, local_dir=self.root)
                else:
                    f, size = self.opener(task, length)
                    with f:
                        data = f.read(size)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            self._rows[key] = json.loads(path.read_bytes())
        return self._rows[key]

    def reference(self, task: str) -> list[dict]:
        """What tells stories apart: each story's question and answer (from 4k, the same at every length), and its
        facts from the facts-only file when that file holds the same story (for qa3 86-99 and qa5 99 it does not)."""
        out = []
        for four, zero in zip(self.rows(task, "4k"), self.rows(task, "0k")):
            fs = facts(zero["input"])
            same = (zero["question"], zero["target"]) == (four["question"], four["target"]) and \
                _in_order(fs, four["input"])
            out.append({"question": four["question"], "target": four["target"], "facts": fs if same else None})
        return out

    def story(self, task: str, length: str, i: int) -> dict:
        """Story ``i`` (0-99) of a task at a length."""
        if length in WHOLE:
            return self.rows(task, length)[i]
        path = self.root / "stories" / task / length / f"{i:03d}.json"
        if path.exists():
            return json.loads(path.read_text())
        ref = self.reference(task)
        rec = self.api(task, length, i) if self.api and ref[i]["facts"] is None else None
        if rec is None:
            f, size = (self.opener or _hub_open)(task, length)
            with f:
                rec = locate(f, size, i, ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, ensure_ascii=False))
        return rec


def _find(f: IO[bytes], start: int, size: int, step: int = STEP) -> int:
    """The offset of the first story start at or after ``start``, or -1."""
    pos = max(0, start)
    while pos < size:
        f.seek(pos)
        buf = f.read(min(step + len(MARK) - 1, size - pos))
        k = buf.find(MARK)
        if k >= 0:
            return pos + k
        pos += step
    return -1


def _rfind(f: IO[bytes], before: int, step: int = STEP) -> int:
    """The offset of the last story start before ``before``, or -1."""
    hi = before
    while hi > 0:
        lo = max(0, hi - step)
        f.seek(lo)
        buf = f.read(hi - lo + len(MARK) - 1)
        k = buf.rfind(MARK)
        while k >= 0 and lo + k >= before:
            k = buf.rfind(MARK, 0, k)
        if k >= 0:
            return lo + k
        hi = lo
    return -1


def _read(f: IO[bytes], start: int, size: int, step: int = STEP, first: int = 0) -> tuple[dict, int]:
    """The story starting at ``start``, and where the next one starts (or the file's end). The first read is
    ``first`` bytes (about one story) when given, then ``step`` at a time."""
    buf, pos = b"", start
    while True:
        f.seek(pos)
        got = f.read(min(max(step, first) if not buf else step, size - pos))
        if not got:
            end = len(buf)
            break
        seen = max(1, len(buf) - len(MARK) + 1)
        buf += got
        pos += len(got)
        k = buf.find(MARK, seen)
        if k >= 0:
            end = k
            break
    body = buf[:end].rstrip()
    while body.endswith((b",", b"]")):
        body = body[:-1].rstrip()
    return json.loads(body), start + end


def facts(text: str) -> list[str]:
    return [s.strip() + "." for s in text.split(".") if s.strip()]


def _in_order(fs: Sequence[str], text: str) -> bool:
    pos = 0
    for fact in fs:
        pos = text.find(fact, pos)
        if pos < 0:
            return False
        pos += len(fact)
    return True


def which(story: dict, reference: Sequence[dict]) -> list[int]:
    """The stories this one could be: same question and answer, and its known facts in order. A bAbI story can be an
    earlier one plus more facts, so only the matches with the most facts are kept."""
    found: list[tuple[int, int]] = []
    for k, ref in enumerate(reference):
        if ref["question"] != story["question"] or ref["target"] != story["target"]:
            continue
        fs = ref.get("facts")
        if fs is None:
            found.append((k, 0))
        elif _in_order(fs, story["input"]):
            found.append((k, len(fs)))
    most = max((n for _, n in found), default=0)
    return [k for k, n in found if n == most]


def locate(f: IO[bytes], size: int, i: int, reference: Sequence[dict]) -> dict:
    """Story ``i`` out of a long file read by byte range: guess its offset, see which story is there, step to it.
    Two stories with the same question and answer and no known facts can only be told apart by position."""
    avg = size / len(reference)
    step = int(min(STEP, max(MIN_STEP, avg / 4)))
    start = _find(f, max(1, int(i * avg - avg / 2)), size, step)
    if start < 0:
        start = _rfind(f, size, step)
    for _ in range(HOPS):
        rec, end = _read(f, start, size, step, first=int(avg * 1.25))
        found = which(rec, reference)
        if not found:
            raise ValueError(f"the story at byte {start} matches no known story")
        j = i if i in found else min(found, key=lambda k: abs(k - i))
        if j == i:
            return rec
        start = end if j < i else _rfind(f, start, step)
        if start < 0 or start >= size:
            break
    raise ValueError(f"could not reach story {i} in {HOPS} steps")


def _item(task: str, length: str, i: int, story: dict) -> Item:
    text = story["input"]
    return Item(id=f"babilong/{task}/{length}/{i:03d}", suite=NAME, context=text, question=story["question"].strip(),
                answer=story["target"], length_tokens=estimate_tokens(text),
                meta={"task": task, "length": length, "index": i, "labels": list(LABELS[task]),
                      "instruction": INSTRUCTION, "format": FORMAT[task]})


def load(tasks: Iterable[str] = TASKS, lengths: Iterable[str] = LENGTHS, indices: Iterable[int] | None = None, *,
         store: Store | None = None) -> list[Item]:
    """Items for these tasks, lengths and story numbers (all 100 when ``indices`` is None)."""
    store = store or Store()
    lengths, picks = list(lengths), None if indices is None else list(indices)
    out = []
    for task in tasks:
        for length in lengths:
            for i in range(STORIES) if picks is None else picks:
                out.append(_item(task, length, i, store.story(task, length, i)))
    return out


def sample(n: int, seed: int = 0, tasks: Iterable[str] = TASKS, lengths: Iterable[str] = LENGTHS, *,
           store: Store | None = None) -> list[Item]:
    """``n`` stories per task, chosen by the seed, each at every length."""
    store = store or Store()
    lengths = list(lengths)
    out = []
    for task in tasks:
        picks = sorted(rng(seed, NAME, task).sample(range(STORIES), min(n, STORIES)))
        out += load([task], lengths, picks, store=store)
    return out


def prompt(item: Item, with_context: bool = True) -> str:
    """The question as the dataset asks it; the context goes in first unless a memory holds it."""
    ctx = f"<context>\n{item.chunks[0].strip()}\n</context>\n\n" if with_context else ""
    return f"{item.meta['instruction']}\n{item.meta['format']}\n\n{ctx}Question: {item.question}"


def right(target: str, reply: str, question: str, labels: Sequence[str]) -> bool:
    """The dataset's rule: the first sentence names the target and no other label (labels in the question don't
    count). A qa8-style target "a,b" needs exactly those labels."""
    out = reply.lower().split(".")[0]
    for stop in ("<context>", "<example>", "question:"):
        out = out.split(stop)[0]
    target = target.lower()
    names = {x.lower() for x in labels}
    named = {x for x in names if x in out} - {x for x in names if x in question.lower()}
    if "," in target and len(target) > 3:
        parts = target.split(",")
        return all(p in named for p in parts) and len(named) == len(parts)
    return target in named and len(named) == 1


def grade(item: Item, reply: str, **_: Any) -> str:
    text = clean(reply)
    return verdict(right(str(item.answer), text, item.question, item.meta["labels"]), text)
