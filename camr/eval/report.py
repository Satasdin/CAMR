"""Emit results tables (CSV + Markdown) and, when matplotlib is installed,
figures.  Everything here is derived from the logged records alone (NFR-04).
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def _fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else ""
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def write_table(rows: list[dict], path_stem: Path, title: str | None = None) -> None:
    path_stem.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path_stem.with_suffix(".md").write_text(f"# {title or path_stem.name}\n\n_No data._\n")
        return
    cols = list(rows[0].keys())
    with path_stem.with_suffix(".csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    lines = [f"# {title}\n" if title else ""]
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join("---" for _ in cols) + "|")
    for r in rows:
        lines.append("| " + " | ".join(_fmt(r.get(c)) for c in cols) + " |")
    path_stem.with_suffix(".md").write_text("\n".join(lines).lstrip() + "\n")


def write_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str))


def budget_figure(rows: list[dict], optimum: dict[str, dict], out: Path) -> Path | None:
    """Gap closed and gap closed per 1k tokens against budget (Figure 4.11, lower panel)."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        log.info("matplotlib not installed; skipping figures")
        return None
    groups = sorted({r["group"] for r in rows})
    if not groups:
        return None
    fig, axes = plt.subplots(1, len(groups), figsize=(4.2 * len(groups), 3.4), squeeze=False)
    for ax, group in zip(axes[0], groups):
        g = [r for r in rows if r["group"] == group and r["budget"] is not None]
        xs = [r["budget"] for r in g]
        ax.plot(xs, [r["gap_closed"] if r["gap_closed"] is not None else float("nan") for r in g],
                marker="o", color="#1f3a5f", label="gap closed")
        ax.set_xscale("symlog", linthresh=128)
        ax.set_xlabel("token budget")
        ax.set_ylabel("gap closed")
        ax.set_title(group)
        ax2 = ax.twinx()
        ax2.plot(xs, [r["gap_per_1k_tokens"] if r["gap_per_1k_tokens"] is not None else float("nan") for r in g],
                 marker="s", linestyle="--", color="#b5651d", label="per 1k tokens")
        ax2.set_ylabel("gap closed / 1k tokens")
        best = optimum.get(group, {}).get("best_budget_per_token")
        if best is not None:
            ax.axvline(best, color="#b5651d", linewidth=0.8, linestyle=":")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def gap_figure(results: list[dict], out: Path) -> Path | None:
    """Floor / treatment / ceiling per group with bootstrap CI (Figure 4.10)."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    if not results:
        return None
    fig, ax = plt.subplots(figsize=(6.5, 0.9 + 0.7 * len(results)))
    for i, r in enumerate(results):
        ax.plot([0, 1], [i, i], color="#8a94a6", linewidth=1)
        ax.scatter([0, 1], [i, i], facecolors="white", edgecolors="#1f3a5f", zorder=3)
        if r["gap_closed"] is not None:
            ax.scatter([r["gap_closed"]], [i], marker="s", color="#1f3a5f", zorder=4)
        if r["ci_low"] is not None:
            ax.plot([r["ci_low"], r["ci_high"]], [i, i], color="#1f3a5f", linewidth=3, alpha=0.4)
        label = r["group"] + (" (unstable)" if r["unstable"] else "")
        ax.text(-0.05, i, label, ha="right", va="center")
    ax.set_yticks([])
    ax.set_xlim(-0.6, 1.3)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["floor", "ceiling"])
    ax.set_title("Fraction of capability gap closed")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
