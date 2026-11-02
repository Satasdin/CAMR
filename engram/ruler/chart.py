"""The growth chart, drawn from test records as a standalone SVG: what it knows, how long you wait, how much RAM.

For each contender the newest record of a life is used. Colour means contender, and engram's green is reserved.
"""

from __future__ import annotations

import json
from pathlib import Path

from engram.ruler.harness import RECORDS

BG, FG, MUTED, RULE = "#070a09", "#e4ebe7", "#93a49c", "#1f2b27"
COLOURS = {"engram": "#5ee08a", "perfect": "#e4ebe7", "camr": "#e25a7e", "camr-4b": "#e2b04a", "bare": "#7d8a84"}
LABELS = {"engram": "engram", "perfect": "perfect reader (everything pasted in)", "camr": "old CAMR, 1.7B",
          "camr-4b": "old CAMR, 4B", "bare": "1.7B alone"}


def newest(persona: str, seed: int, records: Path = RECORDS) -> dict[str, dict]:
    out: dict[str, tuple[str, dict]] = {}
    for p in sorted(records.glob(f"*/*-{persona}-s{seed}-*.json")):
        r = json.loads(p.read_text())
        if r.get("kind") != "life" or not r.get("weeks"):
            continue
        name = r["contender"]["name"]
        key = (len(r["weeks"]), p.name)
        if name not in out or key >= out[name][0]:
            out[name] = (key, r)
    return {k: v[1] for k, v in out.items()}


def _panel(x0, y0, w, h, title, series, ymax, unit, ceiling=None):
    weeks = 12
    X = lambda wk: x0 + (wk - 1) / (weeks - 1) * w
    Y = lambda v: y0 + h - (v / ymax) * h
    s = [f'<text x="{x0}" y="{y0 - 14}" fill="{FG}" font-size="15" font-weight="600">{title}</text>']
    for i in range(5):
        v = ymax * i / 4
        s.append(f'<line x1="{x0}" x2="{x0 + w}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{RULE}"/>')
        label = f"{v:.0f}" if ymax >= 10 else f"{v:.1f}"
        s.append(f'<text x="{x0 - 8}" y="{Y(v) + 4:.1f}" fill="{MUTED}" font-size="11" text-anchor="end">{label}{unit}</text>')
    for wk in range(1, weeks + 1):
        s.append(f'<text x="{X(wk):.1f}" y="{y0 + h + 18}" fill="{MUTED}" font-size="11" text-anchor="middle">{wk}</text>')
    if ceiling:
        pts = " ".join(f"{X(wk):.1f},{Y(v):.1f}" for wk, v in ceiling)
        s.append(f'<polyline points="{pts}" fill="none" stroke="{MUTED}" stroke-width="1.5" stroke-dasharray="4 4"/>')
        wk, v = ceiling[-1]
        s.append(f'<text x="{X(wk) - 4:.1f}" y="{Y(v) - 8:.1f}" fill="{MUTED}" font-size="11" text-anchor="end">told so far</text>')
    for name, pts in series:
        if not pts:
            continue
        c = COLOURS.get(name, FG)
        line = " ".join(f"{X(wk):.1f},{Y(min(v, ymax)):.1f}" for wk, v in pts)
        s.append(f'<polyline points="{line}" fill="none" stroke="{c}" stroke-width="2.5" stroke-linejoin="round"/>')
        wk, v = pts[-1]
        s.append(f'<circle cx="{X(wk):.1f}" cy="{Y(min(v, ymax)):.1f}" r="4" fill="{c}"/>')
    return s


def draw(persona: str, seed: int, records: Path = RECORDS, out: Path | None = None) -> Path:
    runs = newest(persona, seed, records)
    order = [n for n in COLOURS if n in runs] + [n for n in runs if n not in COLOURS]
    W, H, L, R = 960, 860, 70, 30
    w = W - L - R
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="IBM Plex Sans, -apple-system, '
         f'Helvetica, sans-serif"><rect width="{W}" height="{H}" fill="{BG}"/>',
         f'<text x="{L}" y="40" fill="{FG}" font-size="22" font-weight="700">Better, never heavier · {persona}, seed {seed}</text>']
    for i, n in enumerate(order):
        x = L + (i % 3) * 290
        y = 70 + (i // 3) * 22
        s.append(f'<rect x="{x}" y="{y - 10}" width="14" height="4" fill="{COLOURS.get(n, FG)}"/>'
                 f'<text x="{x + 22}" y="{y - 5}" fill="{MUTED}" font-size="12">{LABELS.get(n, n)}</text>')
    knows = [(n, [(wk["week"], wk["summary"]["knows"]) for wk in runs[n]["weeks"]]) for n in order]
    told = max((r["weeks"] for r in runs.values()), key=len, default=[])
    ceiling = [(wk["week"], wk["summary"]["told"]) for wk in told]
    s += _panel(L, 140, w, 260, "Facts it answers right (of 100 questions)", knows, 100, "", ceiling)
    waits = [(n, [(wk["week"], wk["summary"]["wait_median_s"] or 0) for wk in runs[n]["weeks"]]) for n in order]
    top = max([v for _, pts in waits for _, v in pts] + [1.0])
    s += _panel(L, 470, w, 140, "Wait for the first word (median, seconds)", waits, round(top * 1.15 + 0.5), "")
    ram = [(n, [(wk["week"], wk["peak_ram_gb"] or 0) for wk in runs[n]["weeks"]]) for n in order]
    s += _panel(L, 680, w, 120, "Peak memory while answering (GB)", ram, max(4.0, round(max(
        [v for _, pts in ram for _, v in pts] + [0]) * 1.2 + 0.5)), "")
    s.append(f'<text x="{L + w / 2}" y="{H - 14}" fill="{MUTED}" font-size="12" text-anchor="middle">week</text></svg>')
    out = out or records / "charts" / f"growth-{persona}-s{seed}.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(s))
    return out
