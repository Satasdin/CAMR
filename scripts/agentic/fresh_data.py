"""Scenario data: real news the models cannot have been trained on (Wikipedia's Current events, the last 30 days).

The daily pages are fetched, each bullet becomes one plain sentence, and Kimi K3 writes one question per sampled
item whose answer is a short phrase copied from that item (an item whose answer is not in its text is discarded).
The questions are fixed here; the n8n workflow fetches the same pages live, teaches them and answers.

    python scripts/agentic/fresh_data.py      # writes data/agentic/fresh.json
"""

from __future__ import annotations

import datetime as dt
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import systems  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
END = dt.date(2026, 10, 14)
DAYS = 30
N_QUESTIONS = 50
QGEN = ("Here is one news item from {date}:\n\n{item}\n\nWrite one quiz question about this item whose answer is a "
        "short phrase (a name, place, number or date) copied exactly from the item. The question must name enough "
        "context (who, where, what) to be answerable from the item alone, without saying 'this item'. Reply with "
        "two lines:\nQuestion: ...\nAnswer: ...")


def page_title(d: dt.date) -> str:
    return f"Portal:Current_events/{d.year}_{d.strftime('%B')}_{d.day}"


def parse(wikitext: str) -> list[str]:
    """Bullets of a Current events page as plain sentences (links unwrapped, references and templates dropped)."""
    out = []
    for line in wikitext.splitlines():
        if not line.startswith("*"):
            continue
        text = line.lstrip("*").strip()
        text = re.sub(r"\[https?://\S+(?: [^\]]*)?\]", "", text)              # external references
        text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)         # [[target|label]] -> label
        text = re.sub(r"\{\{[^}]*\}\}", "", text)
        text = re.sub(r"'{2,}", "", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = " ".join(text.split())
        if len(text.split()) >= 12 and text.endswith("."):  # a full news sentence, not a topic heading
            out.append(text)
    return out


def fetch(d: dt.date) -> str:
    """The page's wikitext, kept under data/agentic/fresh_pages/ (fetched once, politely: Wikimedia rate-limits)."""
    import time

    import requests

    from camr.memory.fetch import USER_AGENT

    # a file name every platform accepts (Windows refuses ':' and the other reserved characters)
    cache = ROOT / "data/agentic/fresh_pages" / (re.sub(r'[\\/:*?"<>|]', "_", page_title(d)) + ".wiki")
    if cache.exists():
        return cache.read_text()
    for attempt in range(6):
        r = requests.get("https://en.wikipedia.org/w/index.php", params={"title": page_title(d), "action": "raw"},
                         headers={"User-Agent": USER_AGENT}, timeout=30)
        if r.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(r.text)
        time.sleep(2.0)
        return r.text
    raise RuntimeError(f"{page_title(d)}: still rate limited")


def main() -> None:
    days = [END - dt.timedelta(days=i) for i in range(DAYS)][::-1]
    items = []
    for d in days:
        for s in parse(fetch(d)):
            items.append({"date": d.isoformat(), "page": page_title(d), "item": s})
    rng = random.Random(7)
    pool = rng.sample(items, min(len(items), N_QUESTIONS * 2))
    kimi = systems.Meter(systems.runner("kimi-k3"), "kimi-k3")
    questions = []
    for it in pool:
        if len(questions) >= N_QUESTIONS:
            break
        text = kimi.generate(QGEN.format(date=it["date"], item=it["item"])).text
        q = re.search(r"Question:\s*(.+)", text)
        a = re.search(r"Answer:\s*(.+)", text)
        if not q or not a:
            continue
        ans = a.group(1).strip().strip(".")
        if ans.lower() not in it["item"].lower() or len(ans) > 60:
            continue  # the answer must be copied from the item
        questions.append({"id": f"F{len(questions) + 1:03d}", "date": it["date"], "question": q.group(1).strip(),
                          "gold": [ans], "item": it["item"]})
    out = {"source": "Wikipedia Portal:Current events", "days": [d.isoformat() for d in days],
           "pages": [page_title(d) for d in days], "items": len(items), "questions": questions,
           "generation_cost_usd": kimi.usage()["cost_usd"], "generation_calls": kimi.calls}
    path = ROOT / "data/agentic/fresh.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(path, len(items), "items", len(questions), "questions", kimi.usage())


if __name__ == "__main__":
    main()
