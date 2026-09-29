"""DeviceProfiler (FR-16, NFR-01, NFR-02): repeated timing runs on the target device.

Peak memory is reported for two processes: this one (engine, embedder, store,
harness) and the local model runtime.  The proposal's "peak process memory"
would otherwise miss the model entirely, because Ollama serves it from a
separate process, and the model is the bulk of the device's memory budget.
"""

from __future__ import annotations

import os
import platform
import resource
import statistics
import sys
from pathlib import Path

from camr.harness.experiment import ExperimentRunner, Workspace


def _meminfo_total_gb() -> float | None:
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1]) / 1024 / 1024, 2)
    except OSError:
        pass
    try:
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3, 2)
    except (ValueError, OSError, AttributeError):
        return None


def _cpu_model() -> str:
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def hardware_spec() -> dict:
    return {
        "platform": platform.platform(),
        "cpu": _cpu_model(),
        "logical_cpus": os.cpu_count(),
        "memory_gb": _meminfo_total_gb(),
        "python": sys.version.split()[0],
    }


def self_peak_rss_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(peak / 1024 if sys.platform != "darwin" else peak / 1024 / 1024, 1)


def runtime_rss_mb(names: tuple[str, ...] = ("ollama", "ollama_llama_se", "llama-server")) -> float | None:
    """Resident memory of the local model runtime (Linux /proc; best effort elsewhere)."""
    proc = Path("/proc")
    if not proc.exists():
        return None
    total_kb = 0
    found = False
    for pid_dir in proc.iterdir():
        if not pid_dir.name.isdigit():
            continue
        try:
            comm = (pid_dir / "comm").read_text().strip()
            if not comm.startswith(names):
                continue
            for line in (pid_dir / "status").read_text().splitlines():
                if line.startswith("VmHWM:"):  # peak resident set
                    total_kb += int(line.split()[1])
                    found = True
        except OSError:
            continue
    return round(total_kb / 1024, 1) if found else None


class DeviceProfiler:
    def __init__(self, ws: Workspace):
        self.ws = ws
        self.runner = ExperimentRunner(ws)

    def profile(self, repeats: int | None = None, n: int | None = None, benchmark: str | None = None) -> dict:
        p = self.ws.cfg.profile
        repeats = repeats or p.repeats
        n = n or p.n
        benchmark = benchmark or p.benchmark
        if benchmark not in self.ws.cfg.benchmarks:
            benchmark = next(iter(self.ws.cfg.benchmarks))
        # Warm-up: load model weights and embedder so the first timed query is not a cold start.
        for q in self.ws.sample(benchmark, min(p.warmup, n)):
            try:
                self.ws.local_runner.generate(q.question)
            except Exception:  # noqa: BLE001 - warm-up is best effort
                pass
            self.ws.embedder.encode_one(q.question, is_query=True)

        run_ids = {"floor": [], "treatment": []}
        for r in range(repeats):
            for cond in ("floor", "treatment"):
                run_ids[cond].append(
                    self.runner.run(cond, benchmark, n=n, label=f"profile-r{r}", resume=False)
                )
        out = {"hardware": hardware_spec(), "benchmark": benchmark, "repeats": repeats, "n": n,
               "config_hash": self.ws.cfg.fingerprint()}
        for cond, ids in run_ids.items():
            marks = ",".join("?" * len(ids))
            rows = self.ws.conn.execute(
                "SELECT retrieval_latency_ms, generation_latency_ms, e2e_latency_ms, context_tokens,"
                f" prompt_tokens, generated_tokens FROM query_log WHERE status='ok' AND run_id IN ({marks})",
                ids,
            ).fetchall()
            cols = list(zip(*rows)) if rows else [[]] * 6
            med = lambda xs: float(statistics.median([x for x in xs if x is not None])) if any(x is not None for x in xs) else None  # noqa: E731
            out[cond] = {
                "queries": len(rows),
                "median_retrieval_ms": med(cols[0]),
                "median_generation_ms": med(cols[1]),
                "median_e2e_ms": med(cols[2]),
                "median_context_tokens": med(cols[3]),
                "median_prompt_tokens": med(cols[4]),
                "median_generated_tokens": med(cols[5]),
            }
        t = out["treatment"]
        share = (t["median_retrieval_ms"] / t["median_e2e_ms"]) if t["median_retrieval_ms"] and t["median_e2e_ms"] else None
        out["retrieval_share_of_e2e"] = share
        out["nfr02_target_met"] = None if share is None else bool(share <= 0.10)
        f = out["floor"]
        out["added_latency_ms"] = (
            t["median_e2e_ms"] - f["median_e2e_ms"] if t["median_e2e_ms"] and f["median_e2e_ms"] else None
        )
        out["peak_rss_mb_engine_process"] = self_peak_rss_mb()
        out["peak_rss_mb_model_runtime"] = runtime_rss_mb()
        out["store"] = self.ws.store.stats(self.ws.cfg.memory.note_type)
        out["store_file_mb"] = round(self.ws.db_path.stat().st_size / 1024 / 1024, 2)
        return out
