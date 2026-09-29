"""AblationRunner (FR-14): a named sequence of configurations, run unsupervised.

Floor and ceiling are run once per benchmark (label ``main``) and shared by
every variant, so each ablation row differs from the control in exactly one
configuration change.  Variants whose note population has not been ingested
are ingested first.  Completed runs with an identical configuration hash are
skipped, so an interrupted sweep resumes where it stopped.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from camr.config import AblationConfig, AblationVariant, Config, ConfigError, _build
from camr.harness.experiment import ExperimentRunner, Workspace, ingest

log = logging.getLogger(__name__)


def load_sweep(path: str | Path | None = None, config_dir: str | Path | None = None,
               base: AblationConfig | None = None) -> AblationConfig:
    """Ablation plan from a sweep YAML (``ablation:`` block or bare), a directory
    of per-variant override files, or the main configuration."""
    if path:
        raw = yaml.safe_load(Path(path).read_text()) or {}
        return _build(AblationConfig, raw.get("ablation", raw), "sweep")
    if config_dir:
        variants = [
            AblationVariant(label=p.stem, overrides=yaml.safe_load(p.read_text()) or {})
            for p in sorted(Path(config_dir).glob("*.y*ml"))
        ]
        plan = AblationConfig(**{**(base.__dict__ if base else {}), "variants": variants})
        return plan
    if base is None:
        raise ConfigError("no ablation plan given")
    return base


class AblationRunner:
    def __init__(self, ws: Workspace):
        self.ws = ws
        self.runner = ExperimentRunner(ws)

    def plan(self, sweep: AblationConfig) -> list[tuple[str, Config]]:
        cfg = self.ws.cfg
        steps: list[tuple[str, Config]] = []
        by_label = {}
        for v in sweep.variants:
            vcfg = cfg.with_overrides(v.overrides)
            by_label[v.label] = vcfg
            steps.append((v.label, vcfg))
        if sweep.budget_sweep:
            base = by_label.get(sweep.sweep_base, cfg)
            for b in sweep.budget_sweep:
                steps.append((f"budget-{b:04d}", base.with_overrides({"memory": {"token_budget": int(b)}})))
        return steps

    def run(self, sweep: AblationConfig, benchmarks: list[str] | None = None) -> list[int]:
        names = benchmarks or sweep.benchmarks or list(self.ws.cfg.benchmarks)
        steps = self.plan(sweep)
        run_ids: list[int] = []
        for name in names:
            for cond in ("floor", "ceiling"):
                run_ids.append(self.runner.run(cond, name, label="main"))
        ingested = {self.ws.cfg.memory.note_type} if self.ws.store.count(self.ws.cfg.memory.note_type) else set()
        for label, vcfg in steps:
            nt = vcfg.memory.note_type
            if nt not in ingested:
                if self.ws.store.count(nt) == 0:
                    log.info("ablation %s needs note population %s; ingesting", label, nt)
                    ingest(self.ws, vcfg)
                ingested.add(nt)
            for name in names:
                run_ids.append(self.runner.run("treatment", name, cfg=vcfg, label=label))
        return run_ids
