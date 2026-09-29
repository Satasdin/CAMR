"""Benchmark loaders (DR-01 to DR-04).

Supported inputs, as distributed officially:

* ``hotpotqa`` - ``hotpot_dev_distractor_v1.json`` (list of records with
  ``context = [[title, [sentences]], ...]``; gold and distractor paragraphs).
* ``2wikimultihopqa`` - ``dev.json`` in the same shape (the Hugging Face
  variant with ``context = {"title": [...], "sentences": [...]}`` is also read).
* ``popqa`` - ``test.tsv`` / JSONL with ``id, question, possible_answers``.
  PopQA ships *no* documents, so a corpus file is required: JSONL of
  ``{"doc_id", "title", "text"}`` (e.g. the Wikipedia pages of ``s_wiki_title``)
  or of per-question ``{"ctxs": [{"title", "text"}, ...]}`` retrieval dumps.
* ``gsm8k`` - ``test.jsonl`` with ``question`` and ``answer`` (``#### n``).

The sample is drawn once per benchmark from a recorded seed, persisted to
``samples/<benchmark>.json`` and reused by every condition and ablation, so every
comparison is paired even if the dataset file is later re-ordered.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from camr.config import BenchmarkConfig
from camr.eval.analysis import TASK_TYPES
from camr.memory.note import Document, normalise_text


class LeakageError(RuntimeError):
    """An evaluation question (or its answer record) reached the memory corpus."""


@dataclass
class Question:
    qid: str
    dataset: str
    task_type: str
    question: str
    answers: list[str]
    context: list[tuple[str, str]] | None = None  # (title, paragraph) for multi-hop sets


# ---------------------------------------------------------------- readers


def _read_records(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"benchmark file not found: {path}")
    if path.suffix == ".tsv":
        with path.open(newline="") as fh:
            return list(csv.DictReader(fh, delimiter="\t"))
    text = path.read_text()
    stripped = text.lstrip()
    if stripped.startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _paragraphs(context: Any) -> list[tuple[str, str]]:
    if isinstance(context, dict):  # Hugging Face layout
        return [(t, " ".join(s).strip()) for t, s in zip(context["title"], context["sentences"])]
    out = []
    for title, sents in context or []:
        out.append((title, " ".join(s.strip() for s in sents).strip() if isinstance(sents, list) else str(sents)))
    return out


def _as_list(v: Any) -> list[str]:
    if isinstance(v, list):
        return [str(x) for x in v]
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except ValueError:
            pass
        return [v]
    return [str(v)]


def load_questions(name: str, path: str | Path) -> list[Question]:
    if name not in TASK_TYPES:
        raise ValueError(f"unknown benchmark {name!r}; expected one of {sorted(TASK_TYPES)}")
    task_type = TASK_TYPES[name]
    out: list[Question] = []
    for i, rec in enumerate(_read_records(path)):
        if name in ("hotpotqa", "2wikimultihopqa"):
            qid = str(rec.get("_id") or rec.get("id"))
            out.append(Question(qid, name, task_type, rec["question"], [str(rec["answer"])], _paragraphs(rec["context"])))
        elif name == "popqa":
            qid = str(rec.get("id", i))
            out.append(Question(qid, name, task_type, rec["question"], _as_list(rec["possible_answers"])))
        else:  # gsm8k
            qid = str(rec.get("id", f"gsm8k-{i:05d}"))
            out.append(Question(qid, name, task_type, rec["question"], [rec["answer"]]))
    ids = [q.qid for q in out]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{name}: duplicate question ids in {path}")
    return out


# ---------------------------------------------------------------- sampling


def _file_digest(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def draw_sample(questions: list[Question], n: int, seed: int, name: str) -> list[Question]:
    ordered = sorted(questions, key=lambda q: q.qid)  # invariant to file order
    rng = random.Random(f"camr:{seed}:{name}")
    return rng.sample(ordered, min(n, len(ordered)))


def load_sample(name: str, bcfg: BenchmarkConfig, seed: int, sample_dir: Path, n: int | None = None) -> list[Question]:
    """Return the persisted sample (drawing and persisting it on first use).

    ``n`` smaller than the persisted size returns a prefix, which is itself a
    uniform random sample; a larger ``n`` is refused rather than silently
    re-drawn, because that would break pairing with already-ingested memory.
    """
    questions = load_questions(name, bcfg.path)
    by_id = {q.qid: q for q in questions}
    sample_file = sample_dir / f"{name}.json"
    if sample_file.exists():
        meta = json.loads(sample_file.read_text())
        if meta["seed"] != seed:
            raise ValueError(f"{sample_file} was drawn with seed {meta['seed']}, config has {seed}")
        missing = [q for q in meta["question_ids"] if q not in by_id]
        if missing:
            raise ValueError(f"{name}: {len(missing)} sampled ids are missing from {bcfg.path}")
        sample = [by_id[q] for q in meta["question_ids"]]
    else:
        sample = draw_sample(questions, bcfg.n, seed, name)
        sample_dir.mkdir(parents=True, exist_ok=True)
        sample_file.write_text(json.dumps({
            "benchmark": name,
            "seed": seed,
            "n": len(sample),
            "source": str(bcfg.path),
            "source_sha256": _file_digest(bcfg.path),
            "question_ids": [q.qid for q in sample],
        }, indent=2))
    if n is not None:
        if n > len(sample):
            raise ValueError(f"{name}: requested n={n} but the persisted sample has {len(sample)} questions")
        sample = sample[:n]
    return sample


# ---------------------------------------------------------------- corpus


def build_corpus(name: str, bcfg: BenchmarkConfig, sample: list[Question], seed: int) -> list[Document]:
    """Documents that populate memory: supporting + distractor paragraphs only (DR-03)."""
    docs: dict[str, Document] = {}

    def add(title: str, text: str, doc_id: str | None = None) -> None:
        if not text.strip():
            return
        # Readable provenance: the paragraph title (the entity) is the document id,
        # disambiguated by a content hash only if two different paragraphs share it.
        key = doc_id or title or hashlib.sha1(text.encode()).hexdigest()[:12]
        if key in docs and docs[key].text != text:
            key = f"{key}#{hashlib.sha1(text.encode()).hexdigest()[:8]}"
        docs.setdefault(key, Document(dataset=name, doc_id=key, text=text, title=title))

    if name in ("hotpotqa", "2wikimultihopqa"):
        for q in sample:
            for title, para in q.context or []:
                add(title, para)
        if bcfg.extra_corpus_questions:
            sampled = {q.qid for q in sample}
            rest = [q for q in load_questions(name, bcfg.path) if q.qid not in sampled]
            rest.sort(key=lambda q: q.qid)
            rng = random.Random(f"camr:{seed}:{name}:extra")
            for q in rng.sample(rest, min(bcfg.extra_corpus_questions, len(rest))):
                for title, para in q.context or []:
                    add(title, para)
    elif name == "popqa":
        if not bcfg.corpus:
            raise ValueError(
                "popqa has no accompanying documents; set benchmarks.popqa.corpus to a JSONL of "
                "{doc_id,title,text} (e.g. Wikipedia pages of s_wiki_title)"
            )
        for i, rec in enumerate(_read_records(bcfg.corpus)):
            if "ctxs" in rec:
                for c in rec["ctxs"]:
                    add(c.get("title", ""), c.get("text", ""), c.get("id"))
            else:
                add(rec.get("title", ""), rec["text"], str(rec.get("doc_id", rec.get("id", f"popqa-doc-{i}"))))
    # gsm8k: reasoning control, no corpus of its own.
    return sorted(docs.values(), key=lambda d: d.doc_id)


def check_holdout(docs: Iterable[Document], questions: Iterable[Question], min_words: int = 5) -> None:
    """Refuse to build memory that contains an evaluation question verbatim (DR-04, TC-21).

    Supporting paragraphs legitimately contain answers (that is what memory is
    for); what must never happen is the question-answer *record* itself being
    ingested, which would turn retrieval into lookup.  A verbatim question in the
    corpus is the tell-tale of that.
    """
    qs = [(q.dataset, q.qid, normalise_text(q.question)) for q in questions]
    qs = [x for x in qs if len(x[2].split()) >= min_words]
    for d in docs:
        body = normalise_text(f"{d.title} {d.text}")
        for dataset, qid, qtext in qs:
            if qtext in body:
                raise LeakageError(f"evaluation question {dataset}/{qid} appears in corpus document {d.doc_id}")


def question_dict(q: Question) -> dict[str, Any]:
    d = asdict(q)
    d.pop("context", None)
    return d
