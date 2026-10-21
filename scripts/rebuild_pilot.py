"""Rebuild results/pilot (the 22-model sweep behind F10 and Chapter 5) from the committed machine databases.

The sweep ran on machines B-F; each machine's results database is committed on its own branch
(origin/results/model-sweep-b ... -e) or on main (sweep_results/machine-f.sqlite). The combined
results/pilot/camr.sqlite of the original run was never committed, so a fresh clone could not build Chapter 5.
This merges the machines with `camr merge`'s own code and writes tables/model_sweep.json with sweep_report, which
reproduces F10 model for model.

Kimi K3's reference scores on the same questions (F9) came from the original pilot database's `kimi` runs, which
are not in any committed file. They are written separately, to tables/kimi_ceiling.json, from the numbers F9
records, and marked as such: they are never mixed into the merged runs.

    python scripts/rebuild_pilot.py            # then: python scripts/build_ch5.py --template proposal.docx
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PILOT = ROOT / "results/pilot"
MACHINES = {m: f"origin/results/model-sweep-{m}:sweep_results/machine-{m}.sqlite" for m in "bcde"}
KIMI_K3 = {"popqa": 20 / 30, "hotpotqa": 16 / 30, "gsm8k": 12 / 12}  # docs/FINDINGS.md F9: Kimi K3 closed-book, 20/30, 16/30, 12/12


def main() -> None:
    from camr.cli.commands import cmd_merge
    from camr.config import Config
    from camr.harness.model_sweep import sweep_report

    PILOT.mkdir(parents=True, exist_ok=True)
    for f in PILOT.glob("camr.sqlite*"):
        f.unlink()
    Config.load(ROOT / "configs/pilot.yaml").dump(PILOT / "config.yaml")
    with tempfile.TemporaryDirectory() as tmp:
        sources = []
        for m, ref in MACHINES.items():
            path = Path(tmp) / f"machine-{m}.sqlite"
            path.write_bytes(subprocess.run(["git", "show", ref], cwd=ROOT, check=True, capture_output=True).stdout)
            sources.append((m, path))
        sources.append(("f", ROOT / "sweep_results/machine-f.sqlite"))
        for m, path in sources:
            print(f"machine {m.upper()}:", cmd_merge(str(PILOT), str(path)))
    db = sqlite3.connect(PILOT / "camr.sqlite")
    rows = sweep_report(db, Config.load(PILOT / "config.yaml").primary_metric)
    (PILOT / "tables").mkdir(exist_ok=True)
    (PILOT / "tables/model_sweep.json").write_text(json.dumps(rows, indent=1))
    (PILOT / "tables/kimi_ceiling.json").write_text(json.dumps({
        **KIMI_K3, "source": "docs/FINDINGS.md F9 (Kimi K3 closed-book, same questions); the original runs were in "
                             "results/pilot/camr.sqlite under the label 'kimi', which was never committed"}, indent=1))
    # The pilot's device profile (F8) was measured on machine A, whose results database was not committed; Chapter 5
    # uses only these figures from it, written here as docs/FINDINGS.md records them (setup table and F8).
    (PILOT / "tables/profile.json").write_text(json.dumps({
        "hardware": {"cpu": "Intel(R) Xeon(R) Processor @ 2.10GHz", "logical_cpus": 4, "memory_gb": 16.0},
        "peak_rss_mb_engine_process": 712, "store_file_mb": 47.8,
        "source": "docs/FINDINGS.md (setup table; F8 device profile): machine A's results/pilot was not committed"},
        indent=1))
    print(len({r["model"] for r in rows}), "models ->", PILOT / "tables/model_sweep.json")


if __name__ == "__main__":
    main()
