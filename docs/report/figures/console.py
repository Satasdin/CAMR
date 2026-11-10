#!/usr/bin/env python3
"""Draws saved console output as a dark console picture, so real output can stand in the report as a figure.
usage: console.py <text-file> <png> [title]   The text is shown exactly as saved; long lines are wrapped."""
import sys, textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

source, target = sys.argv[1], sys.argv[2]
title = sys.argv[3] if len(sys.argv) > 3 else ""
WIDTH = 104
lines = []
for raw in open(source).read().rstrip("\n").split("\n"):
    lines += textwrap.wrap(raw, WIDTH, subsequent_indent="    ", replace_whitespace=False, drop_whitespace=False) or [""]
height = 0.4 + 0.172 * (len(lines) + (2 if title else 0))
fig = plt.figure(figsize=(8.2, height), facecolor="#16181d")
ax = fig.add_axes([0, 0, 1, 1])
ax.set_facecolor("#16181d")
ax.axis("off")
y = 1 - 0.2 / height
step = 0.172 / height
if title:
    ax.text(0.5, y, title, color="#8b949e", fontsize=7.5, family="DejaVu Sans", ha="center", va="top")
    y -= 2 * step
for line in lines:
    colour = "#7ee787" if line.startswith("$ ") else ("#79c0ff" if line.startswith(("Decided:", "Skill:", "Read:", "Cited", "Prepared")) else "#e6edf3")
    ax.text(0.022, y, line, color=colour, fontsize=7.4, family="DejaVu Sans Mono", va="top")
    y -= step
fig.savefig(target, dpi=230, facecolor=fig.get_facecolor())
