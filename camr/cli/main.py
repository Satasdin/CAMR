"""``camr`` command-line interface (IR-05).

    camr ingest    --config C [--corpus FILE] [--write-policy verbatim|structured]
    camr run       --config C --condition floor|ceiling|treatment --benchmark B [--n N] [--budget T]
    camr ablate    --config C [--sweep FILE | --config-dir DIR]
    camr analyse   --run-dir DIR [--by task_type|benchmark] [--bootstrap N]
    camr profile   --config C [--repeats R] [--n N]
    camr reproduce --config C
    camr ask       --config C "question"          (deployment scenario, not part of the study)
    camr inspect   --run-dir DIR                   (read-only Streamlit interface)
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

from camr.config import Config, ConfigError


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="camr", description="CAMR memory engine and evaluation harness")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def with_config(sp: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sp.add_argument("--config", required=True, help="configuration YAML")
        sp.add_argument("--out", default=None, help="results directory (default: results/YYYY-MM-DD)")
        return sp

    s = with_config(sub.add_parser("ingest", help="populate the memory store"))
    s.add_argument("--corpus", help="JSONL of {doc_id,title,text} to ingest instead of the benchmark corpora")
    s.add_argument("--dataset", default="user", help="dataset name recorded as provenance for --corpus")
    s.add_argument("--write-policy", choices=["verbatim", "structured"])

    s = with_config(sub.add_parser("run", help="run one condition over one benchmark"))
    s.add_argument("--condition", required=True, choices=["floor", "ceiling", "treatment"])
    s.add_argument("--benchmark", required=True)
    s.add_argument("--n", type=int)
    s.add_argument("--budget", type=int)
    s.add_argument("--label", default="main")

    s = with_config(sub.add_parser("ablate", help="run the ablation and budget sweep"))
    s.add_argument("--sweep", help="YAML with an ablation plan (defaults to the config's ablation block)")
    s.add_argument("--config-dir", help="directory of per-variant override YAML files")

    s = sub.add_parser("analyse", help="gap closed, confidence intervals, tables and figures")
    s.add_argument("--run-dir", required=True)
    s.add_argument("--by", choices=["task_type", "benchmark"], default="task_type")
    s.add_argument("--bootstrap", type=int)

    s = with_config(sub.add_parser("profile", help="repeated timing runs on this device"))
    s.add_argument("--repeats", type=int)
    s.add_argument("--n", type=int)

    s = with_config(sub.add_parser("reproduce", help="ingest -> run -> ablate -> analyse -> profile"))
    s.add_argument("--skip-profile", action="store_true")

    s = with_config(sub.add_parser("ask", help="answer one question with memory, locally"))
    s.add_argument("question")
    s.add_argument("--task-type", default="single_hop", choices=["single_hop", "multi_hop", "reasoning"])

    s = sub.add_parser("inspect", help="launch the read-only inspection interface")
    s.add_argument("--run-dir", required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    from camr.cli import commands as c  # deferred: keeps `camr --help` fast

    try:
        if args.cmd == "analyse":
            out = c.cmd_analyse(args.run_dir, args.by, args.bootstrap)
            print(json.dumps(out.get("main", []), indent=2, default=str))
            return 0
        if args.cmd == "inspect":
            app = Path(__file__).resolve().parent.parent / "inspect" / "app.py"
            return subprocess.call([sys.executable, "-m", "streamlit", "run", str(app), "--", "--run-dir",
                                    args.run_dir])
        cfg = Config.load(args.config)
        if args.cmd == "ingest":
            out = c.cmd_ingest(cfg, args.out, args.corpus, args.write_policy, args.dataset)
        elif args.cmd == "run":
            out = {"run_id": c.cmd_run(cfg, args.out, args.condition, args.benchmark, args.n, args.budget,
                                       args.label)}
        elif args.cmd == "ablate":
            out = {"run_ids": c.cmd_ablate(cfg, args.out, args.sweep, args.config_dir)}
        elif args.cmd == "profile":
            out = c.cmd_profile(cfg, args.out, args.repeats, args.n)
        elif args.cmd == "reproduce":
            out = {"run_dir": str(c.cmd_reproduce(cfg, args.out, args.skip_profile))}
        elif args.cmd == "ask":
            out = c.cmd_ask(cfg, args.out, args.question, args.task_type)
        else:  # pragma: no cover - argparse enforces choices
            raise AssertionError(args.cmd)
    except (ConfigError, FileNotFoundError, KeyError, ValueError, RuntimeError) as exc:
        logging.getLogger("camr").error("%s", exc)
        return 2
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
