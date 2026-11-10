#!/usr/bin/env python3
"""Work plan to the end of November 2026, from the course milestones and the project's own record."""
from datetime import date as D
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as md
plt.rcParams.update({"font.family": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 7.8})
T = [("Supervisor selection, template", D(2026,5,1), D(2026,5,8), 0), ("Topic, abstract, Chapters 1 to 3", D(2026,5,8), D(2026,6,12), 0), ("Proposal marking and revision", D(2026,6,12), D(2026,7,31), 0), ("Proposal oral defence", D(2026,7,13), D(2026,7,16), 0), ("Chapter 4: analysis and design", D(2026,7,31), D(2026,8,17), 0), ("First prototype (CAMR)", D(2026,9,29), D(2026,11,8), 0), ("Sprint II review", D(2026,11,5), D(2026,11,6), 0), ("Burrow: build and test", D(2026,11,9), D(2026,11,10), 0), ("Tuning, freeze, evaluation", D(2026,11,10), D(2026,11,11), 0), ("Burrow: Chapters 1 to 5 rewritten", D(2026,11,9), D(2026,11,11), 0), ("Report revision", D(2026,11,11), D(2026,11,20), 1), ("Supervisor review, approvals", D(2026,11,11), D(2026,11,20), 1), ("Hand checks, second-machine install", D(2026,11,11), D(2026,11,20), 1), ("Final defence preparation", D(2026,11,18), D(2026,11,23), 1), ("Final defence", D(2026,11,23), D(2026,11,24), 1)]
f, ax = plt.subplots(figsize=(6.2, 3.9))
for i, (n, a, b, plan) in enumerate(T):
    w = max((b - a).days, 2)
    ax.barh(i, w, left=md.date2num(a), height=0.56, color="#2f6fde" if not plan else "#e0861a", hatch=None if not plan else "///", edgecolor="white", linewidth=0.5)
ax.set_yticks(range(len(T))); ax.set_yticklabels([t[0] for t in T]); ax.invert_yaxis(); ax.xaxis_date()
ax.xaxis.set_major_locator(md.MonthLocator()); ax.xaxis.set_major_formatter(md.DateFormatter("%b %Y")); ax.set_xlim(md.date2num(D(2026,5,1)), md.date2num(D(2026,11,30)))
ax.grid(axis="x", color="#e4e4e4", linewidth=0.6); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color="#2f6fde", label="Completed"), Patch(facecolor="#e0861a", hatch="///", edgecolor="white", label="Remaining")], frameon=False, loc="lower left")
f.tight_layout(); f.savefig(Path(__file__).parent / "gantt.png", dpi=300, facecolor="white")
