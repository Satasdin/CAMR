"""Build a PopQA memory corpus from Wikipedia (PopQA ships no documents).

For every question in the run's persisted PopQA sample, the lead section of the
subject's Wikipedia page (``s_wiki_title``) is fetched through the Wikimedia
REST summary endpoint.  ``--distractors N`` adds the pages of N *unsampled*
PopQA subjects, so retrieval has to discriminate rather than fetch.

Only page text enters the corpus, never the question or answer record; the
engine's holdout guard re-checks this at ingestion.

    python scripts/build_popqa_corpus.py --config configs/pilot.yaml --distractors 90
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import time
import urllib.parse
from pathlib import Path

import requests

from camr.config import Config
from camr.harness.benchmarks import load_sample

API = "https://en.wikipedia.org/api/rest_v1/page/summary/"
HEADERS = {"User-Agent": "CAMR-research/0.1 (Strathmore University student project; non-commercial)"}


def fetch(title: str, session: requests.Session) -> dict | None:
    url = API + urllib.parse.quote(title.replace(" ", "_"), safe="")
    for attempt in range(6):
        try:
            r = session.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 404:
                return None
            if r.status_code == 429:  # rate limited: honour Retry-After, as the API asks
                time.sleep(min(int(r.headers.get("retry-after", "30") or 30), 90) + 1)
                continue
            r.raise_for_status()
            d = r.json()
            text = (d.get("extract") or "").strip()
            return {"doc_id": d.get("title", title), "title": d.get("title", title), "text": text} if text else None
        except (requests.RequestException, ValueError):
            time.sleep(2 ** attempt)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--distractors", type=int, default=90)
    ap.add_argument("--split", default="eval", choices=["eval", "train"])
    ap.add_argument("--train-n", type=int, default=None)
    ap.add_argument("--run-dir", default=None, help="results directory whose samples/ define the split")
    ap.add_argument("--out", default=None, help="output JSONL (default: the config's popqa corpus path)")
    args = ap.parse_args()
    cfg = Config.load(args.config)
    b = cfg.benchmarks["popqa"]
    run_dir = Path(args.run_dir) if args.run_dir else cfg.resolve_run_dir()
    sample = load_sample("popqa", b, cfg.seed, run_dir / "samples", split=args.split, train_n=args.train_n)
    rows = {r["id"]: r for r in csv.DictReader(open(b.path, newline=""), delimiter="\t")}
    targets = [rows[q.qid]["s_wiki_title"] for q in sample]
    sampled = {q.qid for q in sample} | {q.qid for q in load_sample("popqa", b, cfg.seed, run_dir / "samples")}
    pool = sorted({r["s_wiki_title"] for i, r in rows.items() if i not in sampled} - set(targets))
    distract = random.Random(f"camr:{cfg.seed}:popqa-distractors").sample(pool, args.distractors)

    out = Path(args.out or b.corpus)
    out.parent.mkdir(parents=True, exist_ok=True)
    have: dict[str, dict] = {}
    if out.exists():  # resume: keep pages already fetched
        for line in out.read_text().splitlines():
            d = json.loads(line)
            have[d.pop("_query", d["title"])] = d
    session = requests.Session()
    missing = []
    for title in targets + distract:
        if title in have:
            continue
        d = fetch(title, session)
        if d:
            have[title] = d
            with out.open("a") as fh:
                fh.write(json.dumps({**d, "_query": title}) + "\n")
        else:
            missing.append(title)
        time.sleep(1.0)  # be polite to the API
    # Rewrite without the bookkeeping field, de-duplicated by page title.
    seen, lines = set(), []
    for d in have.values():
        if d["doc_id"] not in seen:
            seen.add(d["doc_id"])
            lines.append(json.dumps({k: d[k] for k in ("doc_id", "title", "text")}))
    out.write_text("\n".join(lines) + "\n")
    covered = sum(1 for t in targets if t in have)
    print(json.dumps({"targets": len(targets), "targets_covered": covered, "distractors": len(distract),
                      "written": len(seen), "missing": missing}, indent=1))


if __name__ == "__main__":
    main()
