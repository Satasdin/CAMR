#!/usr/bin/env python3
"""The project's work, March to November 2026, on one continuous timeline: overlapping tasks by workstream,
with the course milestones. Dates follow the course milestones and the repositories' commit history."""
from datetime import date as D
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as md

plt.rcParams.update({"font.family": ["Times New Roman", "Times"], "font.size": 9})
INK, SOFT, GRID = "#0F172A", "#475569", "#E2E8F0"
WORK = {"Proposal": "#1D4ED8", "Analysis and design": "#BE185D", "Build": "#0D9488", "Evaluation": "#C2410C", "Writing": "#475569", "Release": "#65A30D"}

GROUPS = [
    ("Milestones", None, [
        ("Topic approved", D(2026,3,27)),
        ("Proposal submitted", D(2026,6,12)),
        ("Proposal oral defence", D(2026,7,13), D(2026,7,16)),
        ("Chapter 4 submitted", D(2026,8,17)),
        ("Sprint II review", D(2026,11,5)),
        ("Final defence", D(2026,11,23))]),
    ("Proposal", "Proposal", [
        ("Topic search and supervisor", D(2026,3,2), D(2026,3,27)),
        ("Background reading", D(2026,3,16), D(2026,5,8)),
        ("Literature review", D(2026,4,13), D(2026,7,10)),
        ("Chapters 1 to 3", D(2026,5,4), D(2026,6,12)),
        ("Proposal revision", D(2026,6,12), D(2026,7,31))]),
    ("Analysis and design", "Analysis and design", [
        ("Requirements and system analysis", D(2026,7,13), D(2026,8,17)),
        ("Design diagrams", D(2026,7,27), D(2026,8,31)),
        ("Design revision for the build", D(2026,8,24), D(2026,10,5)),
        ("Redesign after the review", D(2026,11,5), D(2026,11,10))]),
    ("Build", "Build", [
        ("Early memory experiments", D(2026,4,20), D(2026,6,5)),
        ("Tools, models and data set-up", D(2026,8,31), D(2026,9,29)),
        ("Memory engine prototype", D(2026,9,29), D(2026,11,4)),
        ("Evaluation harness", D(2026,9,29), D(2026,10,14)),
        ("Vault, desktop app and terminal", D(2026,11,6), D(2026,11,11)),
        ("Engine steps, skills and search", D(2026,11,9), D(2026,11,12))]),
    ("Evaluation", "Evaluation", [
        ("Retrieval and gap experiments", D(2026,10,1), D(2026,11,4)),
        ("Final gap and budget evaluation", D(2026,11,9), D(2026,11,14))]),
    ("Release", "Release", [
        ("Landing page and releases", D(2026,11,10), D(2026,11,16))]),
    ("Writing", "Writing", [
        ("Chapter 4 draft", D(2026,7,20), D(2026,8,17)),
        ("Chapter 5 notes", D(2026,10,5), D(2026,11,4)),
        ("Chapters 1 to 5 revised", D(2026,11,9), D(2026,11,17)),
        ("Supervisor corrections", D(2026,11,13), D(2026,11,21)),
        ("Defence preparation", D(2026,11,17), D(2026,11,23))]),
]

rows = sum(len(g[2]) + 1 for g in GROUPS)
fig, ax = plt.subplots(figsize=(6.27, 0.205 * rows + 0.6))
row = 0
for title, key, tasks in GROUPS:
    colour = WORK[key] if key else INK
    ax.text(-0.012, row, title, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=9, fontweight="bold", color=colour)
    ax.axhline(row - 0.5, color=GRID, lw=0.7, zorder=0)
    row += 1
    for task in tasks:
        name, start = task[0], task[1]
        ax.text(-0.012, row, name, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=8.4, color=INK)
        if key is None:
            end = task[2] if len(task) > 2 else None
            if end: ax.plot([md.date2num(start), md.date2num(end)], [row, row], color=INK, lw=2.2, solid_capstyle="round", zorder=3)
            ax.plot(md.date2num(end or start), row, marker="D", ms=5.5, color=INK, zorder=4)
        else:
            ax.barh(row, md.date2num(task[2]) - md.date2num(start) + 1, left=md.date2num(start), height=0.64, color=colour, zorder=3)
        row += 1
ax.set_ylim(row - 0.5, -0.5); ax.set_yticks([]); ax.xaxis_date()
ax.set_xlim(md.date2num(D(2026,3,1)), md.date2num(D(2026,11,30)))
ax.xaxis.set_major_locator(md.MonthLocator()); ax.xaxis.set_major_formatter(md.DateFormatter("%b"))
ax.xaxis.tick_top(); ax.tick_params(axis="x", length=0, labelsize=8.6, colors=SOFT)
ax.grid(axis="x", color=GRID, lw=0.7); ax.set_axisbelow(True)
for s in ax.spines.values(): s.set_visible(False)
fig.subplots_adjust(left=0.37, right=0.97, top=1 - 0.35 / (0.205 * rows + 0.6), bottom=0.01)
fig.savefig(Path(__file__).parent / "gantt.png", dpi=300, facecolor="white")
