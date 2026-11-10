#!/usr/bin/env python3
"""The project's work, March to November 2026, as a landscape swimlane Gantt chart.

Pieced together from the proposal's own schedule (June to September work was done on the laptop before the first
commit, which arrived with the harness and experiments already running), the repositories' commits from 16 September,
and the dates of the submitted files.

Layout: a milestone track along the top, then one tinted lane per workstream. Each bar carries its own label (inside
when it fits, beside it when not), and tasks that do not overlap share a row, so the chart stays compact."""
from datetime import date as D, timedelta
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
from matplotlib.colors import to_rgba

FONT = ["Times New Roman", "Times"]
plt.rcParams.update({"font.family": FONT, "font.size": 9})
INK, SOFT, FAINT, GRID, PAPER = "#0F172A", "#475569", "#94A3B8", "#E2E8F0", "#FFFFFF"

MILESTONES = [
    ("Proposal submitted", D(2026,6,10)),
    ("Proposal marked, 37 of 40", D(2026,6,15)),
    ("Code into the repository", D(2026,9,29)),
    ("Chapter 5 draft and app 0.4", D(2026,10,16)),
    ("Sprint II review", D(2026,11,5)),
    ("Burrow 1.0 released", D(2026,11,10)),
    ("Final defence", D(2026,11,23)),
]
LANES = [
    ("Proposal", "#1D4ED8", [
        ("Topic and supervisor", D(2026,3,2), D(2026,3,27)),
        ("Literature review", D(2026,3,16), D(2026,5,22)),
        ("Chapters 1 to 3", D(2026,4,13), D(2026,6,10))]),
    ("Analysis and design", "#BE185D", [
        ("Requirements and system analysis", D(2026,6,22), D(2026,7,31)),
        ("Design of the engine and its parts", D(2026,7,13), D(2026,9,11)),
        ("Build plan and wireframes", D(2026,9,7), D(2026,9,28)),
        ("Redesign as Burrow", D(2026,11,4), D(2026,11,9))]),
    ("Build", "#0D9488", [
        ("Baseline engine: store and retrieval", D(2026,6,22), D(2026,8,7)),
        ("Engine parts, one increment at a time", D(2026,7,20), D(2026,9,25)),
        ("Graph layer", D(2026,9,14), D(2026,10,12)),
        ("CAMR Personal 0.2 to 0.4", D(2026,10,1), D(2026,10,16)),
        ("Learning, sleep, coding", D(2026,10,13), D(2026,10,22)),
        ("Engram restart", D(2026,10,23), D(2026,11,4)),
        ("Mac app and agents", D(2026,11,2), D(2026,11,9)),
        ("Burrow", D(2026,11,9), D(2026,11,10))]),
    ("Evaluation", "#C2410C", [
        ("Evaluation harness and data sets", D(2026,6,15), D(2026,7,24)),
        ("Ablations and on-device profiling", D(2026,8,10), D(2026,9,28)),
        ("Model sweeps, five machines", D(2026,10,1), D(2026,10,12)),
        ("RAG, agents, cloud", D(2026,10,13), D(2026,10,22)),
        ("Ollama suites", D(2026,11,3), D(2026,11,5)),
        ("Burrow gap runs", D(2026,11,10), D(2026,11,14))]),
    ("Release", "#65A30D", [
        ("CAMR Personal downloads", D(2026,10,1), D(2026,10,16)),
        ("Landing page and install", D(2026,11,10), D(2026,11,12))]),
    ("Writing", "#475569", [
        ("Chapter 4 draft", D(2026,8,3), D(2026,9,11)),
        ("Chapters 5 and 6", D(2026,9,28), D(2026,10,16)),
        ("Chapters 4 to 6 to the guide", D(2026,11,3), D(2026,11,5)),
        ("Report rebuilt", D(2026,11,10), D(2026,11,17)),
        ("Corrections", D(2026,11,13), D(2026,11,21)),
        ("Defence preparation", D(2026,11,17), D(2026,11,23))]),
]

START, END = D(2026,3,1), D(2026,12,1)
ZOOM_FROM, ZOOM = D(2026,11,1), 4          # November, the busiest month, is drawn at four times the scale
FIG_W, LEFT_IN, RIGHT_IN = 9.7, 1.28, 0.12
AX_W = FIG_W - LEFT_IN - RIGHT_IN
def x(d):
    if d <= ZOOM_FROM: return (d - START).days
    return (ZOOM_FROM - START).days + (d - ZOOM_FROM).days * ZOOM
DAYS = x(END)
DAY_PER_PT = DAYS / (AX_W * 72)
ROW_IN, TASK_PT, MILE_PT = 0.168, 7.8, 7.6
BAR_PT = 8.4                      # bar thickness in points
PAD = 1.6                          # days of space around a label

def width_days(text, size, bold=False):
    prop = FontProperties(family=FONT, weight="bold" if bold else "normal")
    return TextPath((0, 0), text, size=size, prop=prop).get_extents().width * DAY_PER_PT

def pack(items):
    """items: (options, payload); options are (from, to, placement) in order of preference.
    Each item goes on the first row where one of its options is clear of everything already there."""
    rows = []
    def clear(row, a, b): return all(b + PAD <= c or d + PAD <= a for c, d, _ in row)
    for options, payload in sorted(items, key=lambda t: t[0][0][0]):
        for row in rows:
            fit = next((o for o in options if clear(row, o[0], o[1])), None)
            if fit: row.append((fit[0], fit[1], (*payload, fit[2]))); break
        else:
            o = options[0]; rows.append([(o[0], o[1], (*payload, o[2]))])
    return rows

# Lay every task out: where its label goes decides how much room it takes.
laid = []
for name, colour, tasks in LANES:
    items = []
    for label, s, e in tasks:
        a, b = x(s), x(e + timedelta(days=1))
        tw = width_days(label, TASK_PT)
        if tw + 2 * PAD <= b - a: options = [(a, b, "in")]
        else:
            options = []
            if b + PAD + tw <= DAYS: options.append((a, b + PAD + tw, "right"))
            if a - PAD - tw >= 0: options.append((a - PAD - tw, b, "left"))
        items.append((options, (label, a, b)))
    laid.append((name, colour, pack(items)))

marks = []
for label, d in MILESTONES:
    text = f"{label}, {d.day} {d.strftime('%b')}"
    tw = width_days(text, MILE_PT)
    c = (x(d) + x(d + timedelta(days=1))) / 2
    options = []
    if c + 3 + tw <= DAYS: options.append((c - 2, c + 3 + tw, "right"))
    options.append((c - 3 - tw, c + 2, "left"))
    marks.append((options, (text, c)))
mark_rows = pack(marks)

HEAD = 1.0                                     # rows for the month names
mile_rows = len(mark_rows) + 0.45
lane_rows = [len(rows) + 0.35 for _, _, rows in laid]
total = HEAD + mile_rows + sum(lane_rows) + 0.2
fig_h = total * ROW_IN
fig = plt.figure(figsize=(FIG_W, fig_h), facecolor=PAPER)
ax = fig.add_axes([LEFT_IN / FIG_W, 0, AX_W / FIG_W, 1])
ax.set_xlim(0, DAYS); ax.set_ylim(total, 0); ax.axis("off")

def lane_label(y0, height, text, colour, size=9.5):
    ax.text(-0.012, y0 + height / 2, text, transform=ax.get_yaxis_transform(), ha="right", va="center",
            fontsize=size, fontweight="bold", color=colour)

# Months: alternate shading down the whole chart, names along the top.
d, k = START, 0
while d < END:
    nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    if k % 2 == 0: ax.axvspan(x(d), x(nxt), ymin=0, ymax=1 - (HEAD - 0.1) / total, color="#F1F5F9", lw=0, zorder=0)
    ax.text((x(d) + x(nxt)) / 2, HEAD * 0.55, d.strftime("%B") + ("  (four times the scale)" if d == ZOOM_FROM else ""), ha="center", va="center", fontsize=9, color=SOFT)
    ax.plot([x(d), x(d)], [HEAD - 0.1, total], color=GRID, lw=0.6, zorder=0.5)
    d, k = nxt, k + 1
ax.plot([0, DAYS], [HEAD - 0.1, HEAD - 0.1], color=FAINT, lw=0.8, zorder=1)
for day in (9, 16, 23):
    w = x(D(2026, 11, day))
    ax.plot([w, w], [HEAD - 0.1, total], color=GRID, lw=0.5, ls=(0, (2, 2)), zorder=0.5)

# Milestone track.
y = HEAD + 0.2
lane_label(y - 0.1, mile_rows, "Milestones", INK)
track = y + len(mark_rows) - 0.5
for r, row in enumerate(mark_rows):
    for _, _, (text, c, side) in row:
        ly = y + r + 0.15
        ax.plot([c, c], [ly + 0.25, track + 0.05], color=FAINT, lw=0.6, zorder=2)
        ax.text(c + (2.5 if side == "right" else -2.5), ly, text, ha="left" if side == "right" else "right",
                va="center", fontsize=MILE_PT, color=INK)
        ax.plot(c, track + 0.05, marker="D", ms=6, color=INK, mec=PAPER, mew=1.0, zorder=4)
        ax.plot(c, ly, marker="o", ms=2.2, color=INK, zorder=4)
y += mile_rows

# Swimlanes.
cap = BAR_PT / 2 * DAY_PER_PT                      # round caps reach this far past each end
for (name, colour, rows), height in zip(laid, lane_rows):
    ax.add_patch(plt.Rectangle((0, y), DAYS, height - 0.08, color=to_rgba(colour, 0.06), lw=0, zorder=0.6))
    ax.plot([0, DAYS], [y, y], color=to_rgba(colour, 0.35), lw=0.8, zorder=0.7)
    lane_label(y, height - 0.08, name, colour)
    for r, row in enumerate(rows):
        cy = y + 0.65 + r - 0.1
        for _, _, (label, a, b, where) in row:
            a2 = a + cap; b2 = max(a2 + 0.01, b - cap)
            ax.plot([a2, b2], [cy, cy], color=colour, lw=BAR_PT, solid_capstyle="round", zorder=3)
            if where == "in":
                ax.text((a + b) / 2, cy, label, ha="center", va="center", fontsize=TASK_PT, color=PAPER, zorder=4)
            elif where == "right":
                ax.text(b + PAD, cy, label, ha="left", va="center", fontsize=TASK_PT, color=INK, zorder=4)
            else:
                ax.text(a - PAD, cy, label, ha="right", va="center", fontsize=TASK_PT, color=INK, zorder=4)
    y += height

fig.savefig(Path(__file__).parent / "gantt.png", dpi=300, facecolor=PAPER)
print(f"{FIG_W} x {fig_h:.2f} in")
