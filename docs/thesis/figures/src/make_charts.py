"""Draw the Chapter 5 charts from the benchmark records of 4 November 2026 (v2/records/bench/2026-11-04/).

Every number plotted is read from a record here; nothing is typed in. Colour means one thing each: the engine's
memory is cyan (darker for the larger readers, dotted when the memory is read as words), a model with no memory is
amber, and Claude, the yardstick with no memory, is grey and dashed.

    python docs/thesis/figures/src/make_charts.py   ->  docs/thesis/figures/ch5/*.png
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REC = ROOT / "v2" / "records" / "bench" / "2026-11-04"
OUT = HERE.parent / "ch5"
OUT.mkdir(parents=True, exist_ok=True)

CYAN, CYAN_D, CYAN_L = "#0b8fb8", "#075a78", "#5cc3e0"
AMBER, AMBER_D = "#d98a00", "#9c6300"
GREY, GREY_D, GREY_L = "#6e7781", "#3d444d", "#a3aab2"
INK = "#1b2430"
TOKENS = {"64K": 63_860, "256K": 255_952, "1M": 999_988, "2M": 1_999_743, "3M": 2_999_988, "4M": 4_000_000}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9.5, "axes.edgecolor": "#8a929b", "axes.labelcolor": INK,
    "xtick.color": INK, "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e3e6ea", "grid.linewidth": 0.7, "savefig.dpi": 220,
    "legend.frameon": False,
})


def load(name: str) -> dict:
    return json.loads((REC / name).read_text())


def local_points(*names: str) -> dict[str, dict]:
    """Checkpoint name -> summary 'all' (and footprint), over one or more records of one contender."""
    pts = {}
    for n in names:
        for cp in load(n)["checkpoints"]:
            a = dict(cp["summary"]["all"])
            a["footprint_gb"] = cp.get("footprint_gb")
            a["families"] = {k: v for k, v in cp["summary"].items() if k != "all"}
            a["answers"] = cp.get("answers", [])
            pts[cp["name"]] = a
    return pts


def claude_points(*names: str) -> dict[str, dict]:
    pts = {}
    for n in names:
        for cp in load(n)["checkpoints"]:
            s = dict(cp["summary"])
            s["ttft_s"] = cp["request"]["ttft_s"]
            s["answers"] = cp["answers"]
            pts[cp["checkpoint"]] = s
    return pts


E4 = local_points("071525-longhaul-engine-qwen3-4b.json", "143706-longhaul-engine-qwen3-4b.json")
B4 = local_points("092854-longhaul-bare-qwen3-4b.json", "155141-longhaul-bare-qwen3-4b.json")
E8 = local_points("161208-longhaul-engine-qwen3-8b.json")
W27 = local_points("172930-longhaul-words-qwen-27b.json")
E17 = local_points("062857-longhaul-engine-qwen3-1.7b-own.json")
SON = claude_points("022717-claude-claude-sonnet-5-5-longhaul.json", "094325-claude-claude-sonnet-5-5-longhaul.json")
HAI = claude_points("022518-claude-claude-haiku-5-5-longhaul.json", "094146-claude-claude-haiku-5-5-longhaul.json")
OPU = claude_points("023106-claude-claude-opus-5-5-longhaul.json")


def tok_fmt(x, _):
    return f"{x / 1e6:g}M" if x >= 1e6 else f"{x / 1e3:g}K"


def series(pts, key="right"):
    names = [n for n in TOKENS if n in pts]
    return [TOKENS[n] for n in names], names, [pts[n][key] for n in names]


def longhaul_share():
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    lines = [
        ("CAMR, Qwen3 4B", E4, dict(color=CYAN, lw=2.6, marker="o", ms=5)),
        ("CAMR, Qwen3 8B", E8, dict(color=CYAN_D, lw=1.6, marker="o", ms=4)),
        ("Qwen 27B, CAMR's memory as words", W27, dict(color=CYAN_L, lw=1.6, ls=":", marker="o", ms=4)),
        ("Qwen3 4B alone (newest 64K)", B4, dict(color=AMBER, lw=1.8, marker="s", ms=4)),
        ("Claude Sonnet 5.5 alone", SON, dict(color=GREY_D, lw=1.6, ls="--", marker="D", ms=4, mfc="white")),
        ("Claude Opus 5.5 alone", OPU, dict(color=GREY, lw=1.4, ls="--", marker="^", ms=4, mfc="white")),
        ("Claude Haiku 5.5 alone", HAI, dict(color=GREY_L, lw=1.4, ls="--", marker="v", ms=4, mfc="white")),
    ]
    for label, pts, style in lines:
        xs, names, right = series(pts)
        share = [100 * r / pts[n]["questions"] for r, n in zip(right, names)]
        ax.plot(xs, share, label=label, **style)
    xs, names, right = series(E4)
    for x, n, r in zip(xs, names, right):
        ax.annotate(f"{r}/{E4[n]['questions']}", (x, 100 * r / E4[n]["questions"]), textcoords="offset points",
                    xytext=(0, -13), ha="center", fontsize=7.5, color=CYAN_D)
    ax.axvline(1_000_000, color=GREY_L, lw=1, ls="-", zorder=0)
    ax.text(1_030_000, 95, "Claude's 1M-token window", fontsize=7.5, color=GREY, va="top")
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(tok_fmt))
    ax.set_xticks(list(TOKENS.values()))
    ax.set_xticklabels(list(TOKENS.keys()))
    ax.minorticks_off()
    ax.set_ylim(0, 100)
    ax.set_xlabel("History told (tokens)")
    ax.set_ylabel("Questions answered right (%)")
    ax.legend(loc="lower left", fontsize=7.6, ncol=2)
    fig.tight_layout()
    fig.savefig(OUT / "longhaul_share.png")
    plt.close(fig)


def first_word():
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    for label, pts, style in [
        ("CAMR, Qwen3 4B", E4, dict(color=CYAN, lw=2.4, marker="o", ms=5)),
        ("CAMR, Qwen3 8B", E8, dict(color=CYAN_D, lw=1.4, marker="o", ms=4)),
        ("Qwen3 4B alone", B4, dict(color=AMBER, lw=1.6, marker="s", ms=4)),
    ]:
        xs, names, _ = series(pts)
        ax.plot(xs, [pts[n]["ttft_s"]["p50"] for n in names], label=label + " (median)", **style)
    for label, pts, style in [
        ("Claude Sonnet 5.5", SON, dict(color=GREY_D, lw=1.5, ls="--", marker="D", ms=4, mfc="white")),
        ("Claude Opus 5.5", OPU, dict(color=GREY, lw=1.4, ls="--", marker="^", ms=4, mfc="white")),
        ("Claude Haiku 5.5", HAI, dict(color=GREY_L, lw=1.4, ls="--", marker="v", ms=4, mfc="white")),
    ]:
        xs, names, _ = series(pts)
        ax.plot(xs, [pts[n]["ttft_s"] for n in names], label=label + " (per request)", **style)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks(list(TOKENS.values()))
    ax.set_xticklabels(list(TOKENS.keys()))
    ax.minorticks_off()
    ax.set_yticks([0.1, 0.3, 1, 3, 10, 30, 100])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:g} s"))
    ax.set_xlabel("History told (tokens)")
    ax.set_ylabel("Wait for the first word")
    ax.legend(loc="center right", fontsize=7.4, bbox_to_anchor=(1.0, 0.45))
    fig.tight_layout()
    fig.savefig(OUT / "first_word.png")
    plt.close(fig)


FAMILIES = [("fact", "Facts across the gap"), ("changed", "Changed facts"), ("lookalike", "Look-alikes"),
            ("maths", "Corrected maths"), ("code", "Code that must fit"), ("two_hop", "Two hops"),
            ("never", "Never said (declining is right)"), ("page", "The page that grows (3)")]


def families_2m():
    fam_of = {a["id"]: a["family"] for a in E4["2M"]["answers"]}

    def claude_fam(pts):
        out = {f: 0 for f, _ in FAMILIES}
        for a in pts["2M"]["answers"]:
            if a.get("right"):
                out[fam_of[a["qid"]]] += 1
        return out

    cols = [
        ("CAMR, Qwen3 4B", {f: E4["2M"]["families"][f]["right"] for f, _ in FAMILIES}, CYAN, None),
        ("CAMR, Qwen3 1.7B (its own wording)", {f: E17["2M"]["families"][f]["right"] for f, _ in FAMILIES},
         CYAN_L, None),
        ("Claude Sonnet 5.5 alone", claude_fam(SON), GREY_D, "////"),
        ("Claude Opus 5.5 alone", claude_fam(OPU), GREY, "////"),
        ("Claude Haiku 5.5 alone", claude_fam(HAI), GREY_L, "////"),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    h = 0.15
    for j, (label, vals, color, hatch) in enumerate(cols):
        ys = [i + (j - 2) * h for i in range(len(FAMILIES))]
        ax.barh(ys, [vals[f] for f, _ in FAMILIES], height=h * 0.92, color=color if not hatch else "white",
                edgecolor=color, hatch=hatch, label=label, lw=1)
    ax.set_yticks(range(len(FAMILIES)))
    ax.set_yticklabels([n for _, n in FAMILIES])
    ax.invert_yaxis()
    ax.set_xlim(0, 10)
    ax.set_xticks(range(0, 11, 2))
    ax.set_xlabel("Right answers at 2M tokens (of 10 per family)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.42, -0.13), fontsize=7.4, ncol=3)
    fig.tight_layout()
    fig.savefig(OUT / "families_2m.png")
    plt.close(fig)
    return cols


def ram():
    before = load("100255-longhaul-engine-qwen3-4b.json")
    bars = [
        ("Qwen3 4B alone,\nnewest 64K (3M)", B4["3M"]["footprint_gb"], AMBER),
        ("CAMR 4B, no cap\n(3M; Activity Monitor)", 19.2, CYAN_L),
        ("CAMR 4B, 1 GB cap\n(3M)", E4["3M"]["footprint_gb"], CYAN),
        ("CAMR 4B, 1 GB cap\n(4M)", E4["4M"]["footprint_gb"], CYAN),
        ("Qwen3 8B alone,\nnewest 32K (2M)", load("171043-longhaul-bare-qwen3-8b.json")["checkpoints"][3]["footprint_gb"], AMBER),
        ("CAMR 8B, 1 GB cap\n(2M)", E8["2M"]["footprint_gb"], CYAN_D),
    ]
    _ = before
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    xs = range(len(bars))
    ax.bar(xs, [b[1] for b in bars], color=[b[2] for b in bars], width=0.62)
    for x, b in zip(xs, bars):
        ax.text(x, b[1] + 0.3, f"{b[1]:.1f} GB", ha="center", fontsize=8, color=INK)
    ax.axhline(24, color=GREY_L, lw=1)
    ax.text(len(bars) - 0.5, 24.3, "the Mac's 24 GB", ha="right", fontsize=7.5, color=GREY)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([b[0] for b in bars], fontsize=7.4)
    ax.set_ylim(0, 26)
    ax.set_ylabel("Process footprint (GB)")
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(OUT / "ram.png")
    plt.close(fig)


def speed():
    pts = load("055344-speed-engine-qwen3-1.7b.json")["points"]
    hist = [0, 1, 2]
    labels = [f"{p['moments']:,} moments\n{p['history_tokens'] / 1e6:.2f}M tokens" if p['history_tokens'] >= 1e6
              else f"{p['moments']:,} moments\n{p['history_tokens'] / 1e3:.0f}K tokens" for p in pts]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.2, 6.4))  # stacked, for a portrait page
    a1.plot(hist, [p["summary"]["ttft_s"]["p50"] * 1000 for p in pts], color=CYAN, marker="o", lw=2,
            label="first word (median)")
    rms = []
    for p in pts:
        r = p["summary"].get("retrieval_ms") or {}
        rms.append(r.get("p50") if isinstance(r, dict) else None)
    if all(v is not None for v in rms):
        a1.plot(hist, rms, color=CYAN_D, marker="s", lw=1.4, ls="-", label="retrieval (median)")
    a1.set_ylim(0, 200)
    a1.set_ylabel("milliseconds")
    a1.set_xlabel("Memory kept")
    a1.set_xticks(hist)
    a1.set_xticklabels(labels, fontsize=7.4)
    a1.set_xlim(-0.3, 2.3)
    a1.legend(fontsize=7.4, loc="upper left")
    ram_gb = [p["summary"].get("peak_ram_gb") for p in pts]
    disk = [p["disk_gb"] for p in pts]
    a2.plot(hist, disk, color=GREY_D, marker="o", lw=1.4, label="memory on the SSD (GB)")
    if all(v is not None for v in ram_gb):
        a2.plot(hist, ram_gb, color=CYAN, marker="o", lw=2, label="peak RAM (GB)")
    a2.axhline(40, color=GREY_L, lw=1, ls="--")
    a2.text(-0.2, 41, "disk budget 40 GB", fontsize=7.2, color=GREY)
    a2.set_xticks(hist)
    a2.set_xticklabels(labels, fontsize=7.4)
    a2.set_xlim(-0.3, 2.3)
    a2.set_ylim(0, 46)
    a2.set_xlabel("Memory kept")
    a2.legend(fontsize=7.4, loc="center right")
    fig.tight_layout()
    fig.savefig(OUT / "speed.png")
    plt.close(fig)
    return rms, ram_gb


def reach():
    sets = [("Session\n(each week its own)", "195128-reach-engine-qwen3-4b-session.json"),
            ("Project\n(every week, one memory)", "195633-reach-engine-qwen3-4b-project.json"),
            ("Global\n(two projects, one memory)", "200137-reach-engine-qwen3-4b-global.json"),
            ("Project + global\n(both read)", "201043-reach-engine-qwen3-4b-project-global.json")]
    vals = [load(f)["checkpoints"][0]["summary"]["all"]["right"] for _, f in sets]
    facts = [load(f)["checkpoints"][0]["summary"]["fact"]["right"] for _, f in sets]
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    xs = range(len(sets))
    ax.bar(xs, vals, color=[CYAN_L, CYAN, CYAN_D, CYAN_D], width=0.6)
    for x, v, f in zip(xs, vals, facts):
        ax.text(x, v + 0.6, f"{v} of 40\n({f} of 10 facts)", ha="center", fontsize=8, color=INK)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([s for s, _ in sets], fontsize=8)
    ax.set_ylim(0, 40)
    ax.set_ylabel("Right answers (of 40)")
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(OUT / "reach.png")
    plt.close(fig)
    return vals, facts


def media():
    """Multimodal memory: right answers of 37, by contender, on both draws of files (seed 1 and 2)."""
    import glob
    rows = {}
    for f in sorted(glob.glob(str(ROOT / "v2" / "records" / "bench" / "2026-11-0*" / "*media*.json"))):
        d = json.loads(Path(f).read_text())
        name = d["contender"]["name"] if isinstance(d["contender"], dict) else d["contender"]
        seed = d["media"]["dir"].rstrip("/").split("/")[-1]
        cp = d["checkpoints"][-1]["summary"]["all"]
        rows.setdefault(name, {})[seed] = cp["right"]
    order = [("engine:qwen3-4b", "Qwen3 4B + CAMR", CYAN_D), ("engine:qwen2.5-vl-3b", "Qwen2.5-VL-3B + CAMR", CYAN),
             ("ollama:qwen2.5vl:3b", "Ollama VL-3B + pairing", CYAN_L),
             ("file:qwen2.5-vl-3b", "VL-3B, file in the prompt", GREY),
             ("bare:qwen3-4b", "Qwen3 4B alone", AMBER), ("bare:qwen2.5-vl-3b", "VL-3B alone", AMBER_D),
             ("ollama-bare:qwen2.5vl:3b", "Ollama VL-3B alone", AMBER)]
    order = [o for o in order if o[0] in rows]
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    w = 0.38
    for i, (key, label, color) in enumerate(order):
        for j, seed in enumerate(("s1", "s2")):
            v = rows[key].get(seed)
            if v is None:
                continue
            x = i + (j - 0.5) * w
            ax.bar(x, v, width=w * 0.92, color=color, alpha=1.0 if j == 0 else 0.6, edgecolor=color)
            ax.text(x, v + 0.6, str(v), ha="center", fontsize=7.5, color=INK)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([o[1] for o in order], fontsize=7.4, rotation=18, ha="right")
    ax.set_ylim(0, 40)
    ax.axhline(37, color=GREY_L, lw=1, ls="--")
    ax.text(len(order) - 0.6, 37.6, "37 questions", fontsize=7.4, color=GREY, ha="right")
    ax.set_ylabel("Right answers (of 37)")
    ax.grid(axis="x", visible=False)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=GREY_D, label="seed 1"), Patch(color=GREY_D, alpha=0.6, label="seed 2")],
              fontsize=7.4, loc="upper right", bbox_to_anchor=(1.0, 0.93))
    fig.tight_layout()
    fig.savefig(OUT / "media.png")
    plt.close(fig)
    return rows


if __name__ == "__main__":
    longhaul_share()
    first_word()
    cols = families_2m()
    ram()
    print("speed", speed())
    print("reach", reach())
    print("media", media())
    for label, vals, *_ in cols:
        print(label, vals)
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))
