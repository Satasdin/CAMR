"""Download the public benchmarks into data/ in the layouts CAMR's loaders read.

    python scripts/fetch_data.py            # HotpotQA, 2WikiMultiHopQA, GSM8K, PopQA questions

Sources (all public research releases):
* HotpotQA distractor dev  - Hugging Face mirror hotpotqa/hotpot_qa (official JSON layout rebuilt)
* 2WikiMultiHopQA dev      - Hugging Face mirror framolfese/2WikiMultihopQA
* GSM8K test + train       - github.com/openai/grade-school-math
* PopQA questions          - Hugging Face akariasai/PopQA
PopQA ships no documents: build its memory corpus with scripts/build_popqa_corpus.py
(the pilot's corpus is committed at data/popqa/corpus_pilot.jsonl).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent.parent / "data"
HF = "https://huggingface.co/datasets"
FILES = {
    "hotpotqa/validation.parquet": f"{HF}/hotpotqa/hotpot_qa/resolve/main/distractor/validation-00000-of-00001.parquet",
    "2wikimultihopqa/validation.parquet": f"{HF}/framolfese/2WikiMultihopQA/resolve/main/data/validation-00000-of-00001.parquet",
    "gsm8k/test.jsonl": "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl",
    "gsm8k/train.jsonl": "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/train.jsonl",
    "popqa/test.tsv": f"{HF}/akariasai/PopQA/resolve/main/test.tsv",
}


def download(rel: str, url: str) -> Path:
    out = DATA / rel
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with out.open("wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    return out


def to_official(parquet: Path, out: Path, keep_level: bool) -> int:
    import pandas as pd  # noqa: PLC0415 - only needed here

    df = pd.read_parquet(parquet)
    recs = []
    for r in df.itertuples():
        rec = {"_id": r.id, "question": r.question, "answer": r.answer, "type": r.type,
               "supporting_facts": [[str(t), int(i)] for t, i in zip(r.supporting_facts["title"], r.supporting_facts["sent_id"])],
               "context": [[str(t), [str(x) for x in s]] for t, s in zip(r.context["title"], r.context["sentences"])]}
        if keep_level:
            rec["level"] = r.level
        recs.append(rec)
    out.write_text(json.dumps(recs))
    return len(recs)


def main() -> None:
    for rel, url in FILES.items():
        download(rel, url)
    n1 = to_official(DATA / "hotpotqa/validation.parquet", DATA / "hotpotqa/hotpot_dev_distractor_v1.json", True)
    n2 = to_official(DATA / "2wikimultihopqa/validation.parquet", DATA / "2wikimultihopqa/dev.json", False)
    for f in ("hotpotqa/hotpot_dev_distractor_v1.json", "2wikimultihopqa/dev.json", "gsm8k/test.jsonl",
              "gsm8k/train.jsonl", "popqa/test.tsv"):
        print(f, hashlib.sha256((DATA / f).read_bytes()).hexdigest()[:16])
    print({"hotpotqa": n1, "2wikimultihopqa": n2})


if __name__ == "__main__":
    main()
