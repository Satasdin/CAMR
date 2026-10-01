"""Rebuild the model-size sweep tables and figure after `camr merge`.

    python scripts/regen_sweep.py --run-dir results/pilot
"""

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from camr.config import Config
from camr.eval.report import write_table
from camr.harness.model_sweep import sweep_report

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--run-dir", default="results/pilot")
a = ap.parse_args()
run = Path(a.run_dir)
cfg = Config.load(run / "config.yaml")
rows = sweep_report(sqlite3.connect(run / "camr.sqlite"), cfg.primary_metric)
write_table(rows, run / "tables" / "model_sweep", "Model-size sweep")
(run / "tables" / "model_sweep.json").write_text(json.dumps(rows, indent=1))
print(len({r["model"] for r in rows}), "models")
subprocess.run([sys.executable, "scripts/make_figures.py", "--pilot", str(run)], check=True)
