"""``camr`` command-line interface (IR-05).

    camr ingest    --config C [--corpus FILE] [--write-policy verbatim|structured]
    camr run       --config C --condition floor|ceiling|treatment --benchmark B [--n N] [--budget T]
    camr ablate    --config C [--sweep FILE | --config-dir DIR]
    camr analyse   --run-dir DIR [--by task_type|benchmark] [--bootstrap N]
    camr profile   --config C [--repeats R] [--n N]
    camr reproduce --config C
    camr ask       --config C "question"          (deployment scenario, not part of the study)
    camr inspect   --run-dir DIR                   (read-only Streamlit interface)
    camr app                                       (CAMR Personal: your model + a growing memory)
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
    s.add_argument("--condition", required=True, choices=["floor", "ceiling", "treatment", "ceiling_rag"])
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

    s = with_config(sub.add_parser("grow", help="memory growth over time: same frozen model, knowledge fed in stages"))
    s.add_argument("--stages", default="0.25,0.5,1.0", help="comma-separated corpus shares")

    s = with_config(sub.add_parser("sweep-models", help="same engine and questions across several small models"))
    s.add_argument("--models", required=True, help="comma-separated Ollama model names")

    s = sub.add_parser("merge", help="merge completed runs from another machine's results database")
    s.add_argument("--run-dir", required=True)
    s.add_argument("--from", dest="source", required=True, help="path to the other camr.sqlite")

    s = with_config(sub.add_parser("learn", help="learn the engine's per-question policy from rewards over runs"))
    s.add_argument("--phase", default="all", choices=["ingest", "cloud", "local", "analyse", "all"])
    s.add_argument("--train-n", default="popqa=60,hotpotqa=60,gsm8k=24", help="training split size per benchmark")

    with_config(sub.add_parser("retrieval-eval", help="model-free retrieval evaluation on labelled multi-hop sets"))

    s = sub.add_parser("inspect", help="launch the read-only inspection interface")
    s.add_argument("--run-dir", required=True)

    s = sub.add_parser("app", help="CAMR Personal: chat with any local Ollama model plus a memory that grows")
    s.add_argument("--home", default=None, help="where your memory is kept (default ~/.camr)")
    s.add_argument("--host", default="http://127.0.0.1:11434", help="Ollama address (must be on this machine)")
    s.add_argument("--port", type=int, default=8502)
    return p


def _streamlit(script: Path, extra: list[str], port: int | None = None) -> int:
    from camr.ui_theme import STREAMLIT_FLAGS

    cmd = [sys.executable, "-m", "streamlit", "run", str(script), *STREAMLIT_FLAGS]
    if port:
        cmd += ["--server.port", str(port)]
    return subprocess.call(cmd + ["--", *extra])


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
        if args.cmd == "merge":
            print(json.dumps(c.cmd_merge(args.run_dir, args.source)))
            return 0
        if args.cmd == "inspect":
            return _streamlit(Path(__file__).resolve().parent.parent / "inspect" / "app.py", ["--run-dir", args.run_dir])
        if args.cmd == "app":
            extra = ["--host", args.host] + (["--home", args.home] if args.home else [])
            return _streamlit(Path(__file__).resolve().parent.parent / "app" / "ui.py", extra, args.port)
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
        elif args.cmd == "sweep-models":
            out = c.cmd_sweep_models(cfg, args.out, [m.strip() for m in args.models.split(",") if m.strip()])
        elif args.cmd == "learn":
            tn = {k: int(v) for k, v in (kv.split("=") for kv in args.train_n.split(",") if kv)}
            out = c.cmd_learn(cfg, args.out, args.phase, tn)
            out = {k: out[k] for k in ("learned_offline", "oracle") if k in out} or {"phase": args.phase, "done": True}
        elif args.cmd == "grow":
            out = c.cmd_grow(cfg, args.out, [float(x) for x in args.stages.split(",")])
        elif args.cmd == "retrieval-eval":
            out = c.cmd_retrieval_eval(cfg, args.out)
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
