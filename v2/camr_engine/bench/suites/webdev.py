"""LMArena's WebDev leaderboard over time (lmarena-ai/leaderboard-dataset, config ``webdev``): every published
rating, for the chart of how models got better at building web pages.

People compare two models' web pages side by side and vote; the ratings are re-fitted at each publication, so a model's
number moves a little as others join. The "overall" board runs from 12 Nov 2025; "webdev", "webdev-html" and
"webdev-react" start in Feb 2026, "image_to_webdev" in Apr 2026. Up to 13 Oct 2026 the dataset names models by
their API slugs ("claude-opus-4-6"); from 16 Oct by display names ("Claude Opus 4.6"). ``model_key`` joins the two:
names with the same words and version numbers in any order are one model, shown by its latest name.

Open weights: the board's licence column says "Proprietary" for closed models and names the licence for open ones
(Apache 2.0, MIT, a community licence, ...). An empty licence leaves the flag blank.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from camr_engine.bench.suites.common import V2, hub_file

NAME = "webdev"
REPO = "lmarena-ai/leaderboard-dataset"
REVISION = "38eef63f8920f9e8a77d903928321ecd74ab8126"
FILE = "webdev/full-00000-of-00001.parquet"
CATEGORY = "overall"
CSV_PATH = V2 / "records" / "bench" / "webdev-arena-history.csv"
SUMMARY_PATH = V2 / "records" / "bench" / "webdev-arena-summary.json"
COLUMNS = ("date", "model", "organisation", "rating", "ci_low", "ci_high", "open_weights", "model_key", "rank",
           "votes", "licence", "category")


def raw(path: Any = None) -> list[dict]:
    """Every row of the published history."""
    import pyarrow.parquet as pq

    return pq.read_table(path or hub_file(REPO, FILE, REVISION, "lmarena")).to_pylist()


def open_weights(licence: str | None) -> bool | None:
    lic = (licence or "").strip()
    if not lic:
        return None
    return lic.lower() != "proprietary"


def name_words(name: str) -> tuple[str, ...]:
    """A name's words, version numbers joined ("claude-opus-4-5" and "Claude Opus 4.5" -> claude opus 4.5), sorted."""
    words = [w for w in re.split(r"[\s\-_.,()/:]+", name.lower()) if w]
    out: list[str] = []
    for w in words:
        if re.fullmatch(r"\d{1,2}", w) and out and re.fullmatch(r"\d{1,2}(\.\d{1,2})*", out[-1]):
            out[-1] += "." + w
        else:
            out.append(w)
    return tuple(sorted(out))


def history(rows: list[dict], category: str | None = CATEGORY) -> list[dict]:
    """Tidy rows (``COLUMNS``), oldest first, best first within a date. ``category`` None keeps every board."""
    keep = [r for r in rows if category is None or r["category"] == category]
    latest: dict[tuple[str, ...], tuple[str, bool, str]] = {}
    for r in sorted(keep, key=lambda r: r["leaderboard_publish_date"]):  # the latest name wins, display names first
        k = name_words(r["model_name"])
        cand = (r["leaderboard_publish_date"], " " in r["model_name"], r["model_name"])
        if k not in latest or cand[:2] >= latest[k][:2]:
            latest[k] = cand
    out = []
    for r in keep:
        out.append({"date": r["leaderboard_publish_date"], "model": r["model_name"],
                    "organisation": r["organization"] or "", "rating": round(r["rating"], 2),
                    "ci_low": round(r["rating_lower"], 2), "ci_high": round(r["rating_upper"], 2),
                    "open_weights": open_weights(r["license"]), "model_key": latest[name_words(r["model_name"])][2],
                    "rank": r["rank"], "votes": r["vote_count"], "licence": r["license"] or "",
                    "category": r["category"]})
    out.sort(key=lambda h: (h["date"], h["category"], -h["rating"]))
    return out


def write_csv(rows: list[dict], path: Path = CSV_PATH) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({**r, "open_weights": "" if r["open_weights"] is None else str(r["open_weights"]).lower()})
    return path


def _brief(r: dict) -> dict:
    return {k: r[k] for k in ("model", "model_key", "organisation", "rating", "ci_low", "ci_high", "open_weights")}


def summary(hist: list[dict]) -> dict:
    """Month by month (each month's last publication): the top model, the best open model and its gap to the top,
    the best Claude model; and each Claude model's first, peak and last rating."""
    by_date: dict[str, list[dict]] = defaultdict(list)
    for r in hist:
        by_date[r["date"]].append(r)
    month_end: dict[str, str] = {}
    for d in sorted(by_date):
        month_end[d[:7]] = d
    top, best_open, claude = [], [], []
    for month, d in month_end.items():
        rows = sorted(by_date[d], key=lambda r: -r["rating"])
        lead = rows[0]
        top.append({"month": month, "date": d, **_brief(lead)})
        opens = [r for r in rows if r["open_weights"]]
        if opens:
            best_open.append({"month": month, "date": d, **_brief(opens[0]),
                              "gap_to_top": round(lead["rating"] - opens[0]["rating"], 2)})
        cl = [r for r in rows if r["organisation"] == "anthropic"]
        if cl:
            claude.append({"month": month, "date": d, **_brief(cl[0]), "rank": cl[0]["rank"], "claude_models": len(cl)})
    lines: dict[str, list[dict]] = defaultdict(list)
    for r in sorted(hist, key=lambda r: r["date"]):
        if r["organisation"] == "anthropic":
            lines[r["model_key"]].append(r)
    models = []
    for key, rs in lines.items():
        peak = max(rs, key=lambda r: r["rating"])
        models.append({"model_key": key, "first_seen": rs[0]["date"], "first_rating": rs[0]["rating"],
                       "peak_date": peak["date"], "peak_rating": peak["rating"], "last_seen": rs[-1]["date"],
                       "last_rating": rs[-1]["rating"], "publications": len({r["date"] for r in rs})})
    models.sort(key=lambda m: (m["first_seen"], m["model_key"]))
    dates = sorted(by_date)
    return {"source": f"{REPO} ({FILE}, revision {REVISION})",
            "category": sorted({r["category"] for r in hist}), "first_date": dates[0] if dates else None,
            "last_date": dates[-1] if dates else None, "publications": len(dates), "rows": len(hist),
            "models": len({r["model_key"] for r in hist}),
            "open_weights_rows": dict(Counter(str(r["open_weights"]).lower() for r in hist)),
            "note": ("Ratings are re-fitted at each publication. A month's entry is its last publication. "
                     "open_weights comes from the board's licence column (Proprietary = closed)."),
            "top_by_month": top, "best_open_by_month": best_open, "claude_by_month": claude,
            "claude_models": models}


def build(csv_path: Path = CSV_PATH, summary_path: Path = SUMMARY_PATH, category: str | None = CATEGORY, *,
          path: Any = None) -> tuple[Path, Path, dict]:
    """Download (once), write the CSV and the summary JSON; return their paths and the summary."""
    hist = history(raw(path), category)
    write_csv(hist, csv_path)
    s = summary(hist if category else [h for h in hist if h["category"] == CATEGORY])  # one board, never mixed
    summary_path = Path(summary_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(s, indent=1, ensure_ascii=False) + "\n")
    return Path(csv_path), summary_path, s
