"""Benchmark loaders and condition runners (package camr.harness)."""

from camr.harness.ablation import AblationRunner, load_sweep
from camr.harness.benchmarks import LeakageError, Question, build_corpus, check_holdout, load_questions, load_sample
from camr.harness.experiment import CONDITIONS, ExperimentRunner, Workspace, ingest
from camr.harness.diagnostics import coverage
from camr.harness.profile import DeviceProfiler, hardware_spec

__all__ = [
    "CONDITIONS",
    "AblationRunner",
    "DeviceProfiler",
    "ExperimentRunner",
    "LeakageError",
    "Question",
    "Workspace",
    "build_corpus",
    "check_holdout",
    "coverage",
    "hardware_spec",
    "ingest",
    "load_questions",
    "load_sample",
    "load_sweep",
]
