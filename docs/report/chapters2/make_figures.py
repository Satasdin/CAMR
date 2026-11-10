#!/usr/bin/env python3
"""Draws the two figures of Chapters 1 to 3 that are the student's own: the conceptual framework (Figure 2.9)
and the incremental development approach (Figure 3.1). Both follow the figures of the June 2026 proposal,
updated to the engine as built. Output goes to figures/related/."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

OUT = Path(__file__).resolve().parent.parent / "figures" / "related"
plt.rcParams["font.family"] = ["Times New Roman", "Times", "DejaVu Serif"]
INK = "#1f2a44"
PALE = "#eef2f8"
MID = "#c5d3ea"


def arrow(ax, a, b, dashed=False, color=INK):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=14, lw=1.2, color=color,
                                 linestyle="--" if dashed else "-", shrinkA=0, shrinkB=0, zorder=5))


def box(ax, x, y, w, h, title, lines, fill="white", head=PALE):
    ax.add_patch(Rectangle((x, y), w, h, fc=fill, ec=INK, lw=1.3, zorder=2))
    ax.add_patch(Rectangle((x, y + h - 0.62), w, 0.62, fc=head, ec=INK, lw=1.3, zorder=3))
    ax.text(x + w / 2, y + h - 0.31, title, ha="center", va="center", fontsize=11.5, weight="bold", color=INK, zorder=4)
    top = y + h - 0.62 - 0.3
    for i, words in enumerate(lines):
        ax.text(x + 0.14, top - i * 0.36, words, ha="left", va="center", fontsize=10, color=INK, zorder=4)


def framework():
    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=220)
    ax.set_xlim(0, 11); ax.set_ylim(0, 5.6); ax.axis("off")
    box(ax, 0.15, 1.1, 3.35, 3.45, "Independent variable", [
        "Configuration of the memory engine",
        "•  Decide: use the vault or not;",
        "    search or follow links",
        "•  Fit: token budget set for the model",
        "•  Check: citations verified, one retry",
        "•  Learn: notes written with consent",
        "•  Skills: method handed to the model"])
    box(ax, 4.25, 1.1, 2.9, 3.45, "Process", [
        "Question answering on the device",
        "•  Engine recalls excerpts",
        "    from the vault",
        "•  Excerpts packed within",
        "    the token budget",
        "•  Frozen model answers from",
        "    the question and the excerpts"])
    box(ax, 7.9, 1.1, 2.95, 3.45, "Dependent variables", [
        "•  Fraction of the capability",
        "    gap closed",
        "•  Accuracy gained per token",
        "    of memory supplied",
        "•  End-to-end latency on the",
        "    target device"])
    arrow(ax, (3.5, 2.85), (4.25, 2.85)); arrow(ax, (7.15, 2.85), (7.9, 2.85))
    ax.add_patch(Rectangle((3.55, 4.75), 4.3, 0.7, fc=MID, ec=INK, lw=1.3))
    ax.text(5.7, 5.1, "Moderator: task type\n(knowledge-bound or reasoning-bound)", ha="center", va="center", fontsize=10.5, color=INK)
    arrow(ax, (7.52, 4.75), (7.52, 2.9), dashed=True)
    ax.add_patch(Rectangle((3.55, 0.15), 4.3, 0.7, fc="white", ec=INK, lw=1.3, linestyle="--"))
    ax.text(5.7, 0.5, "Held constant: the language model\n(weights frozen in every condition)", ha="center", va="center", fontsize=10.5, color=INK)
    arrow(ax, (5.7, 0.85), (5.7, 1.1), dashed=True)
    fig.savefig(OUT / "fig2-9-framework.png", bbox_inches="tight", pad_inches=0.08, facecolor="white")
    plt.close(fig)


def incremental():
    fig, ax = plt.subplots(figsize=(11.5, 6.6), dpi=220)
    ax.set_xlim(0, 11.5); ax.set_ylim(0, 6.6); ax.axis("off")
    arrow(ax, (0.45, 0.55), (11.3, 0.55)); arrow(ax, (0.45, 0.55), (0.45, 6.5))
    ax.text(5.9, 0.2, "Project timeline", ha="center", style="italic", fontsize=11, color=INK)
    ax.text(0.2, 3.5, "System capability (measured)", va="center", rotation=90, style="italic", fontsize=11, color=INK)
    steps = [("Increment 1", "The gap measured", "First prototype, CAMR"),
             ("Increment 2", "Memory in plain files", "Vault, index, search, links"),
             ("Increment 3", "Memory a person can use", "App, terminal chat, MCP server"),
             ("Increment 4", "Retrieval tested", "Real bug fixes, held-back projects"),
             ("Increment 5", "Engine around the model", "Five steps, skills, final evaluation")]
    w, h = 1.55, 1.5
    for i, (name, green, below) in enumerate(steps):
        x = 0.85 + i * 2.12
        y = 0.95 + i * 0.82
        ax.add_patch(Rectangle((x, y), w, h, fc="white", ec=INK, lw=1.4, zorder=2))
        for j, (word, fill) in enumerate([("Analysis", "#f4f6fb"), ("Design", "#e3e9f5"), ("Build", MID), ("Evaluate", "#f4f6fb")]):
            yy = y + h - 0.14 - (j + 1) * 0.31
            ax.add_patch(Rectangle((x + 0.12, yy), w - 0.24, 0.27, fc=fill, ec="#9aa5bd", lw=0.8, zorder=3))
            ax.text(x + w / 2, yy + 0.135, word, ha="center", va="center", fontsize=9.5, color=INK, zorder=4)
        ax.text(x + w / 2, y + h + 0.52, name, ha="center", fontsize=12, weight="bold", style="italic", color=INK)
        ax.text(x + w / 2, y + h + 0.24, green, ha="center", fontsize=9.5, style="italic", color="#2d6a2d")
        arrow(ax, (x + w / 2, y + h), (x + w / 2, y + h + 0.18))
        ax.text(x + w / 2, y - 0.22, below, ha="center", fontsize=9.5, color=INK)
        if i < len(steps) - 1:
            arrow(ax, (x + w, y + h * 0.65), (x + 2.12, y + 0.82 + h * 0.45), color="#6b768f")
    fig.savefig(OUT / "fig3-1-incremental.png", bbox_inches="tight", pad_inches=0.08, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    framework()
    incremental()
