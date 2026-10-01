"""Implementations behind the CLI verbs.  Every verb takes one configuration file
and writes into one dated results directory (IR-05, Figure 4.9)."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from camr.config import Config
from camr.eval.analysis import GapAnalyzer
from camr.eval.escalation import escalation_curve
from camr.eval.report import budget_figure, gap_figure, write_json, write_table
from camr.harness.ablation import AblationRunner, load_sweep
from camr.harness.benchmarks import _read_records, load_sample
from camr.harness.diagnostics import coverage
from camr.harness.experiment import ExperimentRunner, Workspace, ingest
from camr.harness.profile import DeviceProfiler
from camr.memory.note import Document
from camr.models.prompt import ALL_TEMPLATES, answer_template

log = logging.getLogger("camr")


def cmd_ingest(cfg: Config, out: str | None, corpus: str | None, write_policy: str | None,
               dataset: str = "user") -> list[dict]:
    if write_policy:
        cfg = cfg.with_overrides({"memory": {"write_policy": write_policy}})
    ws = Workspace(cfg, out)
    try:
        if corpus:
            docs = [
                Document(dataset=dataset, doc_id=str(r.get("doc_id", r.get("id", i))), text=r["text"],
                         title=r.get("title", ""))
                for i, r in enumerate(_read_records(corpus))
            ]
            summaries = [ws.engine(cfg).ingest(docs, progress=True)]
        else:
            summaries = ingest(ws, cfg)
        result = [s.as_dict() for s in summaries]
        write_json(result, ws.run_dir / "tables" / f"ingest_{cfg.memory.note_type}.json")
        return result
    finally:
        ws.close()


def cmd_run(cfg: Config, out: str | None, condition: str, benchmark: str, n: int | None, budget: int | None,
            label: str) -> int:
    if budget is not None:
        cfg = cfg.with_overrides({"memory": {"token_budget": budget}})
    ws = Workspace(cfg, out)
    try:
        return ExperimentRunner(ws).run(condition, benchmark, cfg=cfg, n=n, label=label)
    finally:
        ws.close()


def cmd_ablate(cfg: Config, out: str | None, sweep: str | None, config_dir: str | None) -> list[int]:
    plan = load_sweep(sweep, config_dir, cfg.ablation)
    ws = Workspace(cfg, out)
    try:
        return AblationRunner(ws).run(plan)
    finally:
        ws.close()


def cmd_profile(cfg: Config, out: str | None, repeats: int | None, n: int | None) -> dict:
    ws = Workspace(cfg, out)
    try:
        result = DeviceProfiler(ws).profile(repeats, n)
        write_json(result, ws.run_dir / "tables" / "profile.json")
        flat = [{"condition": c, **result[c]} for c in ("floor", "treatment")]
        write_table(flat, ws.run_dir / "tables" / "profile", "Device cost profile (medians)")
        return result
    finally:
        ws.close()


def cmd_analyse(run_dir: str | Path, by: str = "task_type", bootstrap: int | None = None,
                cfg: Config | None = None) -> dict:
    run_dir = Path(run_dir)
    cfg = cfg or Config.load(run_dir / "config.yaml")
    conn = sqlite3.connect(f"file:{run_dir / 'camr.sqlite'}?mode=ro", uri=True)
    try:
        an = GapAnalyzer(
            conn, cfg.primary_metric, bootstrap=bootstrap or cfg.analysis.bootstrap, ci=cfg.analysis.ci,
            min_denominator=cfg.analysis.min_denominator, seed=cfg.seed,
        )
        tables = run_dir / "tables"
        figures = run_dir / "figures"
        summary: dict = {"primary_metric": cfg.primary_metric, "by": by}

        main = [r.as_dict() for r in an.compute("main", by)]
        write_table(main, tables / "gap_main", "Fraction of capability gap closed (default configuration)")
        gap_figure(main, figures / "gap_main.png")
        summary["main"] = main

        labels = an.treatment_labels()
        variant_labels = [v.label for v in cfg.ablation.variants if v.label in labels]
        if variant_labels:
            control = cfg.ablation.variants[0].label
            abl = an.ablation_table(variant_labels, control=control, by=by)
            write_table(abl, tables / "ablation", f"Ablation (deltas against '{control}')")
            summary["ablation"] = abl
        sweep_labels = sorted(lab for lab in labels if lab.startswith("budget-"))
        if sweep_labels:
            rows, optimum = an.budget_sweep(sweep_labels, by=by)
            write_table(rows, tables / "budget_sweep", "Token budget sweep")
            write_json(optimum, tables / "budget_optimum.json")
            budget_figure(rows, optimum, figures / "budget_sweep.png")
            summary["budget_sweep"] = rows
            summary["budget_optimum"] = optimum

        # The practical bridge: local + memory, escalating only the least-confident queries.
        esc = escalation_curve(conn, cfg.primary_metric, by=by)
        write_table(esc, tables / "escalation", "Gap closed vs share of queries escalated to the cloud")
        summary["escalation"] = esc

        # Where knowledge-bound answers are lost: write path, retrieval, budget, or reading.
        samples = {}
        for name, bcfg in cfg.benchmarks.items():
            if (run_dir / "samples" / f"{name}.json").exists():
                samples[name] = load_sample(name, bcfg, cfg.seed, run_dir / "samples")
        cov = coverage(conn, samples, cfg.primary_metric)
        write_table(cov, tables / "coverage", "Failure decomposition: where the gold answer is lost")
        summary["coverage"] = cov

        # DR-09: the exact prompt templates, reported verbatim.
        lines = ["# Prompt templates (verbatim)\n"]
        for t in ALL_TEMPLATES:
            lines += [f"## {t.template_id}\n", "```text", t.body, "```\n"]
        (tables / "templates.md").write_text("\n".join(lines))
        write_json(summary, tables / "summary.json")
        return summary
    finally:
        conn.close()


def cmd_reproduce(cfg: Config, out: str | None, skip_profile: bool = False) -> Path:
    """ingest -> run (floor, ceiling, treatment) -> ablate -> analyse -> profile."""
    ws = Workspace(cfg, out)
    run_dir = ws.run_dir
    try:
        for s in ingest(ws, cfg):
            log.info("ingest: %s", json.dumps(s.as_dict()))
        runner = ExperimentRunner(ws)
        for name in cfg.benchmarks:
            for cond in ("floor", "ceiling", "treatment", *cfg.extra_conditions):
                runner.run(cond, name, label="main")
        if cfg.ablation.variants or cfg.ablation.budget_sweep:
            AblationRunner(ws).run(cfg.ablation)
        if not skip_profile:
            result = DeviceProfiler(ws).profile()
            write_json(result, run_dir / "tables" / "profile.json")
    finally:
        ws.close()
    cmd_analyse(run_dir, cfg=cfg)
    return run_dir


def cmd_ask(cfg: Config, out: str | None, question: str, task_type: str = "single_hop") -> dict:
    """The deployment scenario of section 4.2: one question, memory-augmented, fully local."""
    ws = Workspace(cfg, out)
    try:
        engine = ws.engine(cfg)
        recall = engine.recall(question)
        prompt = answer_template(task_type, True).render(question, recall.context)
        gen = ws.local_runner.generate(prompt)
        return {
            "answer": gen.text.strip(),
            "notes": [{"note_id": c.note.note_id, "text": c.note.text, "score": round(c.composite, 4)}
                      for c in recall.admitted],
            "context_tokens": recall.context_tokens,
            "retrieval_ms": round(recall.retrieval_ms, 1),
            "generation_ms": round(gen.latency_ms, 1),
        }
    finally:
        ws.close()


def cmd_retrieval_eval(cfg: Config, out: str | None) -> list[dict]:
    """Model-free retrieval evaluation on labelled multi-hop benchmarks (verbatim notes)."""
    from camr.harness.retrieval_eval import run_all

    cfg = cfg.with_overrides({"memory": {"write_policy": "verbatim"}})
    ws = Workspace(cfg, out)
    try:
        benches = [b for b in cfg.benchmarks if b in ("hotpotqa", "2wikimultihopqa")]
        summaries = [s.as_dict() for s in ingest(ws, cfg, benches)]
        write_json(summaries, ws.run_dir / "tables" / "ingest_verbatim.json")
        rows = run_all(ws, cfg, benches)
        stats = ws.store.stats("verbatim")
        write_table(rows, ws.run_dir / "tables" / "retrieval_eval", "Retrieval-level evaluation (verbatim notes)")
        write_json({"rows": rows, "store": stats, "ingest": summaries}, ws.run_dir / "tables" / "retrieval_eval.json")
        return rows
    finally:
        ws.close()


def cmd_grow(cfg: Config, out: str | None, stages: list[float]) -> list[dict]:
    """Memory growth over time: same frozen model, knowledge fed in stages."""
    from camr.harness.growth import run_growth

    ws = Workspace(cfg, out)
    try:
        rows = run_growth(ws, cfg, stages)
        write_table(rows, ws.run_dir / "tables" / "growth", "Memory growth: same frozen model, more knowledge")
        write_json(rows, ws.run_dir / "tables" / "growth.json")
        return rows
    finally:
        ws.close()
