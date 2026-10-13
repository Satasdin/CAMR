"""Build the knowledge packs bundled with CAMR Personal (camr/app/packs/).

Each pack is harvested from the web (camr.memory.fetch.WebLookup.topic_pages: the topic's article,
related articles, then the articles for the names they mention most) and embedded with the app's
default embedder (nomic-embed-text through Ollama), so installing it in the app copies the vectors
and runs no model. Wikipedia text is CC BY-SA 4.0; each pack names its sources and licence.

    python scripts/build_packs.py --topics "Kenya" "Solar System" "Machine learning" --pages 15
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from camr.config import Config
from camr.memory.embedder import OllamaEmbedder
from camr.memory.engine import MemoryEngine
from camr.memory.fetch import WebLookup
from camr.memory.packs import harvest
from camr.memory.store import SQLiteVectorStore
from camr.models.tokenizer import RegexTokenizer

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", nargs="+", default=["Kenya", "Solar System", "Machine learning"])
    ap.add_argument("--pages", type=int, default=15)
    ap.add_argument("--out", default=str(ROOT / "camr/app/packs"))
    ap.add_argument("--patient", type=float, default=300.0)
    a = ap.parse_args()
    emb = OllamaEmbedder("nomic-embed-text")
    cfg = Config.from_dict({"memory": {"write_policy": "verbatim", "chunk_tokens": 120}})  # the app's write path
    lookup = WebLookup(cache_path=ROOT / "results/packs/web_cache.sqlite", patient_s=a.patient, min_interval_s=1.5)
    log = {}
    for topic in a.topics:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteVectorStore(Path(tmp) / "m.sqlite", dim=emb.dim, embedder_name=emb.name)
            engine = MemoryEngine.from_config(cfg, store=store, embedder=emb, tokenizer=RegexTokenizer())
            man, pages = harvest(engine, lookup, topic, Path(a.out) / f"{topic.lower().replace(' ', '-')}.camrpack",
                                 pages=a.pages)
            store.close()
        log[man.name] = {"title": man.title, "notes": man.notes, "sources": [p.url for p in pages]}
        print(man.name, man.notes, "notes from", len(pages), "articles", flush=True)
    (ROOT / "results/packs").mkdir(parents=True, exist_ok=True)
    (ROOT / "results/packs/build.json").write_text(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
