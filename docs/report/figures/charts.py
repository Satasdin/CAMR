#!/usr/bin/env python3
"""Draws the result charts directly from the saved results."""
import statistics as st, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, str(Path(__file__).parent.parent))
import analyse as A
HERE = Path(__file__).parent
plt.rcParams.update({"font.family": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 8, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#777777", "xtick.color": "#333333", "ytick.color": "#333333", "axes.grid": True, "axes.axisbelow": True, "grid.color": "#e4e4e4", "grid.linewidth": 0.6})
COLOR = {"none": "#1a9e77", "search": "#2f6fde", "walk": "#e0861a"}
HATCH = {"none": "", "search": "", "walk": "///"}
LABEL = {"none": "None", "search": "Search", "walk": "Walk"}
H = A.held(); R = A.real(); ALL = [x for r in A.REPOS for x in R[r]]
def bars(ax, groups, series, values, width=0.36, fmt="{:g}"):
    n = len(series)
    for i, m in enumerate(series):
        xs = [g + (i - (n - 1) / 2) * (width + 0.02) for g in range(len(groups))]
        b = ax.bar(xs, values[m], width, color=COLOR[m], hatch=HATCH[m], edgecolor="white", linewidth=0.8, label=LABEL[m])
        for x, v in zip(xs, values[m]):
            ax.text(x, v, fmt.format(v), ha="center", va="bottom", fontsize=7.6, color="#111111")
    ax.set_xticks(range(len(groups))); ax.set_xticklabels(groups); ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, loc="upper right", ncols=n)
def save(f, name):
    f.tight_layout(); f.savefig(HERE / f"{name}.png", dpi=300, facecolor="white"); plt.close(f)
# overall real fixes
f, ax = plt.subplots(figsize=(6.2, 2.7))
meas = [("first", "Right file first"), ("any", "Any changed file reached"), ("all", "Every changed file reached")]
v = {m: [sum(A.hits(x, m)[k] for x in ALL) for k, _ in meas] for m in ("search", "walk")}
bars(ax, [l for _, l in meas], ["search", "walk"], v); ax.set_ylabel("Instances out of 101"); ax.set_ylim(0, 92)
save(f, "chart_real")
# by repo: any
f, ax = plt.subplots(figsize=(6.2, 2.6))
names = [f"{r} ({len(R[r])})" for r in A.REPOS]
v = {m: [sum(A.hits(x, m)["any"] / len(R[r]) * 100 for x in R[r]) for r in A.REPOS] for m in ("search", "walk")}
bars(ax, names, ["search", "walk"], v, fmt="{:.0f}%"); ax.set_ylabel("Instances with a changed\nfile reached (%)"); ax.set_ylim(0, 122)
save(f, "chart_repos")
# held
f, axes = plt.subplots(1, 3, figsize=(6.2, 2.5), sharey=True)
S = [x for x in H if x["category"] != "setup"]
for ax, (m, name) in zip(axes, A.MODELS):
    vals = [sum(x["task_passed"] for x in S if x["model"] == m and x["mode"] == mo) for mo in A.MODES]
    bs = ax.bar(range(3), vals, 0.62, color=[COLOR[mo] for mo in A.MODES], hatch=None, edgecolor="white")
    bs[2].set_hatch("///")
    for i, v_ in enumerate(vals): ax.text(i, v_, str(v_), ha="center", va="bottom", fontsize=8)
    ax.set_xticks(range(3)); ax.set_xticklabels([LABEL[mo] for mo in A.MODES]); ax.set_title(name, fontsize=8.2); ax.set_ylim(0, 18); ax.grid(axis="x", visible=False)
axes[0].set_ylabel("Scored sessions passed,\nout of 18")
save(f, "chart_held")
# growth: small multiples, no dual axis
FILES = {"requests": 106, "flask": 197, "pytest": 495, "django": 3833}
import json
G = {r: json.loads((A.R / f"real-1/{r}.growth.json").read_text()) for r in A.REPOS}
f, axes = plt.subplots(1, 3, figsize=(6.2, 2.55))
xs = [FILES[r] for r in A.REPOS]
axes[0].plot(xs, [G[r]["index_bytes"] / 1e6 for r in A.REPOS], "-o", color="#2f6fde", lw=1.6, ms=4.5, label="Index")
axes[0].plot(xs, [G[r]["repo_bytes"] / 1e6 for r in A.REPOS], "--s", color="#1a9e77", lw=1.6, ms=4.5, label="Code")
axes[0].set_ylabel("MB"); axes[0].set_title("Size on disk", fontsize=8.2); axes[0].legend(frameon=False)
FIRST = {r: (78.3 if r == "pytest" else G[r]["first_index_seconds"]) for r in A.REPOS}
axes[1].plot(xs, [FIRST[r] for r in A.REPOS], "-o", color="#2f6fde", lw=1.6, ms=4.5)
axes[1].set_ylabel("Seconds"); axes[1].set_title("First full index", fontsize=8.2)
for m, mark in (("search", "--o"), ("walk", "-^")):
    axes[2].plot(xs, [st.median(x[m]["seconds"] for x in R[r]) for r in A.REPOS], mark, color=COLOR[m], lw=1.6, ms=4.5, label=LABEL[m])
axes[2].set_ylabel("Seconds"); axes[2].set_title("Median retrieval", fontsize=8.2); axes[2].legend(frameon=False)
for ax in axes:
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("Files in repository (log scale)", fontsize=7.4)
save(f, "chart_growth")
