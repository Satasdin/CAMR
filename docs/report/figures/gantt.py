#!/usr/bin/env python3
"""The project's work, May to November 2026: overlapping tasks by workstream, with the course milestones.
Dates follow the course milestones and the repositories' commit history. November is drawn at its own scale,
because several pieces of work ran at once after the Sprint II review."""
from datetime import date as D, timedelta
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as md

plt.rcParams.update({"font.family": ["Times New Roman", "Times"], "font.size": 9})
INK, SOFT, GRID = "#0F172A", "#475569", "#E2E8F0"
WORK = {"Proposal": "#1D4ED8", "Analysis and design": "#BE185D", "Build": "#0D9488", "Evaluation": "#C2410C", "Writing": "#475569", "Release": "#65A30D"}

BEFORE = [
    ("Milestones", None, [
        ("Proposal submitted", D(2026,6,12)), ("Oral defence", D(2026,7,13), D(2026,7,16)),
        ("Proposal marked", D(2026,7,31)), ("Chapter 4 submitted", D(2026,8,17))]),
    ("Proposal", "Proposal", [
        ("Topic, supervisor and template", D(2026,5,1), D(2026,5,10)),
        ("Literature review", D(2026,5,8), D(2026,7,10)),
        ("Chapters 1 to 3", D(2026,5,18), D(2026,6,12)),
        ("Proposal revision", D(2026,6,12), D(2026,7,31))]),
    ("Analysis and design", "Analysis and design", [
        ("Requirements and system analysis", D(2026,7,13), D(2026,8,17)),
        ("Design diagrams", D(2026,7,27), D(2026,8,31)),
        ("Design revision for the build", D(2026,8,24), D(2026,10,5))]),
    ("Build", "Build", [
        ("Tools, models and data set-up", D(2026,8,31), D(2026,9,29)),
        ("Evaluation harness", D(2026,9,29), D(2026,10,14)),
        ("Memory engine prototype", D(2026,9,29), D(2026,11,4))]),
    ("Evaluation", "Evaluation", [
        ("Retrieval and gap experiments", D(2026,10,1), D(2026,11,4))]),
    ("Writing", "Writing", [
        ("Chapter 4 draft", D(2026,7,20), D(2026,8,17)),
        ("Chapter 5 notes from the prototype", D(2026,10,5), D(2026,11,4))]),
]
AFTER = [
    ("Milestones", None, [("Sprint II review", D(2026,11,5)), ("Final defence", D(2026,11,23))]),
    ("Analysis and design", "Analysis and design", [
        ("Redesign after the review", D(2026,11,5), D(2026,11,10))]),
    ("Build", "Build", [
        ("Vault, index, search and links", D(2026,11,6), D(2026,11,10)),
        ("Desktop app, terminal chat and MCP", D(2026,11,7), D(2026,11,11)),
        ("Engine steps, skills and fast search", D(2026,11,9), D(2026,11,12))]),
    ("Evaluation", "Evaluation", [
        ("Retrieval evaluation", D(2026,11,9), D(2026,11,11)),
        ("Gap, ablation and budget evaluation", D(2026,11,10), D(2026,11,14))]),
    ("Release", "Release", [
        ("Landing page and published releases", D(2026,11,12), D(2026,11,18))]),
    ("Writing", "Writing", [
        ("Chapters 1 to 5 revised", D(2026,11,9), D(2026,11,17)),
        ("Supervisor review and corrections", D(2026,11,13), D(2026,11,21)),
        ("Defence preparation", D(2026,11,17), D(2026,11,23))]),
]

def panel(ax, groups, left, right, months):
    row, ticks, names = 0, [], []
    for title, key, tasks in groups:
        colour = WORK[key] if key else INK
        ax.text(-0.015, row, title, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=9, fontweight="bold", color=colour)
        ax.axhline(row - 0.5, color=GRID, lw=0.7, zorder=0)
        row += 1
        for task in tasks:
            name, start = task[0], task[1]
            ax.text(-0.015, row, name, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=8.6, color=INK)
            if key is None:
                end = task[2] if len(task) > 2 else None
                if end: ax.plot([md.date2num(start), md.date2num(end)], [row, row], color=INK, lw=2.2, solid_capstyle="round", zorder=3)
                ax.plot(md.date2num(end or start), row, marker="D", ms=6, color=INK, zorder=4)
            else:
                end = task[2]
                ax.barh(row, md.date2num(end) - md.date2num(start) + 1, left=md.date2num(start), height=0.62, color=colour, zorder=3)
            row += 1
    ax.set_ylim(row - 0.5, -0.5); ax.set_yticks([]); ax.xaxis_date()
    ax.set_xlim(md.date2num(left), md.date2num(right))
    if months:
        ax.xaxis.set_major_locator(md.MonthLocator()); ax.xaxis.set_major_formatter(md.DateFormatter("%b"))
    else:
        ax.xaxis.set_major_locator(md.DayLocator(bymonthday=[1,5,10,15,20,25,30])); ax.xaxis.set_major_formatter(md.DateFormatter("%-d Nov"))
    ax.xaxis.tick_top(); ax.tick_params(axis="x", length=0, labelsize=8.6, colors=SOFT)
    ax.grid(axis="x", color=GRID, lw=0.7); ax.set_axisbelow(True)
    for s in ax.spines.values(): s.set_visible(False)
    return row

rows_a = sum(len(g[2]) + 1 for g in BEFORE); rows_b = sum(len(g[2]) + 1 for g in AFTER)
fig, (a, b) = plt.subplots(2, 1, figsize=(6.27, 7.6), gridspec_kw={"height_ratios": [rows_a, rows_b], "hspace": 0.13})
panel(a, BEFORE, D(2026,5,1), D(2026,11,5), True)
panel(b, AFTER, D(2026,11,1), D(2026,11,30), False)
a.set_title("May to October 2026", loc="left", fontsize=10, fontweight="bold", color=INK, pad=20)
b.set_title("November 2026", loc="left", fontsize=10, fontweight="bold", color=INK, pad=20)
fig.subplots_adjust(left=0.40, right=0.955, top=0.93, bottom=0.01)
fig.savefig(Path(__file__).parent / "gantt.png", dpi=300, facecolor="white")
