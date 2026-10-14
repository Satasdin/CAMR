"""The device governor: what this machine can do, and stopping before it can't.

The engine runs on whatever it is installed on: a laptop with 8 GB and a nearly full
disk, or a workstation. Instead of assuming, it measures:

* ``probe``: total and available RAM, free disk where memory lives, CPU cores and load;
* ``calibrate``: how fast this machine embeds text, searches memory and generates;

and turns that into limits every long-running job respects (``Governor.check``):

* ingestion stops, cleanly and resumably, before the disk falls below a reserve or the
  store passes a size cap, and before available RAM falls below a reserve;
* background work (sleep, harvesting) waits while the CPU is busy;
* the read path chooses how much to read (token budget) and how to search (exact or
  the learned index, and how many clusters) to meet a latency target (``plan``).

Every figure comes from the operating system (``/proc``, ``statvfs``) or a timed run on
this machine; nothing is a guess about hardware.
"""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

MB = 1024 * 1024


def _meminfo() -> dict[str, float]:
    out: dict[str, float] = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, rest = line.partition(":")
                out[key] = float(rest.split()[0]) / 1024  # kB -> MB
    except OSError:
        pass
    return out


def process_rss_mb(pid: int | str = "self") -> float:
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    try:  # macOS / BSD: peak RSS of this process (bytes on macOS, kB elsewhere)
        import resource
        import sys

        r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return r / MB if sys.platform == "darwin" else r / 1024
    except Exception:  # noqa: BLE001
        return 0.0


def _cpu_times() -> tuple[float, float] | None:
    """(busy, total) CPU jiffies of the whole machine."""
    try:
        with open("/proc/stat") as f:
            vals = [float(x) for x in f.readline().split()[1:]]
    except OSError:
        return None
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0.0)
    return sum(vals) - idle, sum(vals)


def _self_jiffies() -> float | None:
    try:
        with open("/proc/self/stat") as f:
            parts = f.read().rsplit(")", 1)[1].split()
        return float(parts[11]) + float(parts[12])  # utime + stime
    except (OSError, IndexError, ValueError):
        return None


def others_cpu_share(window_s: float = 0.5) -> float | None:
    """Share of all CPU capacity used by other processes over a short window (0..1); None without /proc."""
    a, sa = _cpu_times(), _self_jiffies()
    if a is None or sa is None:
        return None
    time.sleep(window_s)
    b, sb = _cpu_times(), _self_jiffies()
    total = b[1] - a[1]
    if total <= 0:
        return 0.0
    return max(0.0, (b[0] - a[0]) - (sb - sa)) / total


def _ram() -> tuple[float, float]:
    info = _meminfo()
    if info:
        return info.get("MemTotal", 0.0), info.get("MemAvailable", info.get("MemFree", 0.0))
    try:  # without /proc (macOS, Windows): psutil when present
        import psutil  # type: ignore

        vm = psutil.virtual_memory()
        return vm.total / MB, vm.available / MB
    except Exception:  # noqa: BLE001
        return 0.0, 0.0


@dataclass
class DeviceProfile:
    ram_total_mb: float
    ram_available_mb: float
    cpu_count: int
    load_1m: float | None
    disk_total_mb: float
    disk_free_mb: float
    path: str
    # measured on this machine by ``calibrate`` (None until then)
    embed_texts_per_s: float | None = None
    search_ms: dict[str, float] = field(default_factory=dict)  # notes -> ms per exact search
    gen_tokens_per_s: float | None = None
    prefill_tokens_per_s: float | None = None
    at: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return asdict(self)


def probe(path: str | Path = ".") -> DeviceProfile:
    """What the operating system says about this machine, now."""
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    du = shutil.disk_usage(p)
    total, avail = _ram()
    try:
        load = os.getloadavg()[0]
    except (OSError, AttributeError):
        load = None
    return DeviceProfile(ram_total_mb=round(total, 1), ram_available_mb=round(avail, 1), cpu_count=os.cpu_count() or 1,
                         load_1m=load, disk_total_mb=round(du.total / MB, 1), disk_free_mb=round(du.free / MB, 1),
                         path=str(p))


def calibrate(profile: DeviceProfile, *, embedder=None, runner=None, dim: int | None = None,
              sizes: tuple[int, ...] = (10_000, 100_000), texts: int = 64, seed: int = 0) -> DeviceProfile:
    """Time the three things the engine spends its time on, on this machine."""
    import numpy as np

    if embedder is not None:
        sample = [f"Calibration sentence number {i} about a city, a person and a date in {1900 + i}." for i in
                  range(texts)]
        embedder.encode(sample[:4])  # warm up
        t0 = time.perf_counter()
        embedder.encode(sample)
        profile.embed_texts_per_s = round(texts / (time.perf_counter() - t0), 1)
        dim = dim or getattr(embedder, "dim", None)
    if dim:
        rng = np.random.default_rng(seed)
        for n in sizes:
            mat = rng.standard_normal((n, dim), dtype=np.float32)
            q = rng.standard_normal(dim, dtype=np.float32)
            mat @ q  # warm up
            t0 = time.perf_counter()
            for _ in range(5):
                np.argpartition(-(mat @ q), 20)[:20]
            profile.search_ms[str(n)] = round((time.perf_counter() - t0) / 5 * 1000, 2)
            del mat
    if runner is not None:
        g = runner.generate("Answer with a short phrase only.\n\nQuestion: What is the capital of Kenya?\nAnswer:")
        ev, pe = g.meta.get("eval_ms"), g.meta.get("prompt_eval_ms")
        if g.generated_tokens and ev:
            profile.gen_tokens_per_s = round(g.generated_tokens / (ev / 1000), 1)
        if g.prompt_tokens and pe:
            profile.prefill_tokens_per_s = round(g.prompt_tokens / (pe / 1000), 1)
    return profile


# ---------------------------------------------------------------------- limits
@dataclass
class Limits:
    reserve_disk_mb: float = 1024.0      # never let free disk fall below this
    max_store_mb: float | None = None    # the memory store may not grow past this
    reserve_ram_mb: float = 768.0        # leave this much RAM available to everything else
    max_process_mb: float | None = None  # this process may not grow past this
    max_load_per_core: float = 0.9       # background work waits above this load
    latency_target_ms: float = 2500.0    # one answer: retrieval plus reading


@dataclass
class Status:
    ok: bool
    reason: str | None = None  # "disk", "store size", "memory", "process memory"
    detail: str = ""


class Governor:
    """Checks a job calls between units of work; ``Status.ok`` False means stop now (cleanly, resumably)."""

    def __init__(self, store_path: str | Path, limits: Limits | None = None, *, probe_fn=probe,
                 rss_fn=process_rss_mb):
        self.store_path = Path(store_path)
        self.limits = limits or Limits()
        self._probe = probe_fn
        self._rss = rss_fn

    def store_mb(self) -> float:
        total = 0
        for f in self.store_path.parent.glob(self.store_path.name + "*"):  # the store, its WAL and journal
            if f.is_file():
                total += f.stat().st_size
        ivf = self.store_path.with_suffix(self.store_path.suffix + ".ivf")
        if ivf.is_dir():
            total += sum(f.stat().st_size for f in ivf.iterdir() if f.is_file())
        return total / MB

    def check(self, upcoming_mb: float = 0.0) -> Status:
        """May the next unit of work (expected to add ``upcoming_mb`` to the store) start?"""
        lim = self.limits
        dev = self._probe(self.store_path.parent)
        if dev.disk_free_mb - upcoming_mb < lim.reserve_disk_mb:
            return Status(False, "disk", f"{dev.disk_free_mb:.0f} MB free; keeping {lim.reserve_disk_mb:.0f} MB")
        if lim.max_store_mb is not None and self.store_mb() + upcoming_mb > lim.max_store_mb:
            return Status(False, "store size", f"store {self.store_mb():.0f} MB; cap {lim.max_store_mb:.0f} MB")
        if dev.ram_available_mb and dev.ram_available_mb < lim.reserve_ram_mb:
            return Status(False, "memory", f"{dev.ram_available_mb:.0f} MB available; keeping "
                                           f"{lim.reserve_ram_mb:.0f} MB")
        if lim.max_process_mb is not None and self._rss() > lim.max_process_mb:
            return Status(False, "process memory", f"process {self._rss():.0f} MB; cap {lim.max_process_mb:.0f} MB")
        return Status(True)

    def busy(self) -> bool:
        """True while the CPU is busy with *other* work (background jobs should wait). Measured over a short
        window as the machine's CPU time minus this process's own; the load average where /proc is missing."""
        share = others_cpu_share() if self._probe is probe else None
        if share is not None:
            return share > self.limits.max_load_per_core
        dev = self._probe(self.store_path.parent)
        return dev.load_1m is not None and dev.load_1m / max(1, dev.cpu_count) > self.limits.max_load_per_core

    def wait_until_idle(self, max_wait_s: float = 300.0, step_s: float = 5.0, sleep=time.sleep) -> float:
        waited = 0.0
        while self.busy() and waited < max_wait_s:
            sleep(step_s)
            waited += step_s
        return waited


# ---------------------------------------------------------------------- planning the read path
@dataclass
class ReadPlan:
    search: str                # "exact" or "index"
    nprobe: int | None
    token_budget: int
    expected_ms: float
    max_notes_on_disk: int     # how many more notes this disk can hold above the reserve
    exact_ram_mb: float        # RAM exact search would need for the vectors
    why: list[str]


def plan(profile: DeviceProfile, *, notes: int, dim: int, limits: Limits | None = None, answer_tokens: int = 16,
         bytes_per_note: float = 4200.0, index_min_notes: int = 1_000_000, budgets=(512, 256, 128, 64)) -> ReadPlan:
    """How to read memory on this device: exact search or the index, and how much to read, to meet the latency
    target. Needs a calibrated profile (search and generation speeds); falls back to safe defaults without one."""
    lim = limits or Limits()
    why: list[str] = []
    exact_ram = notes * dim * 4 / MB
    search_ms = _search_ms(profile, notes)
    use_index = notes >= index_min_notes or exact_ram > 0.25 * max(1.0, profile.ram_available_mb - lim.reserve_ram_mb)
    nprobe = None
    if use_index:
        why.append(f"{notes} notes: the learned index, vectors read from disk (exact search would hold "
                   f"{exact_ram:.0f} MB of them in RAM)")
        nprobe = max(4, int(round(0.25 * notes ** 0.5)))  # a quarter of its clusters: recall within ~1 point
    gen = profile.gen_tokens_per_s or 20.0
    pre = profile.prefill_tokens_per_s or 200.0
    budget = budgets[-1]
    for b in budgets:  # the largest budget whose reading fits the target
        expected = search_ms + 30 + (b + 60) / pre * 1000 + answer_tokens / gen * 1000
        if expected <= lim.latency_target_ms:
            budget = b
            break
    expected = search_ms + 30 + (budget + 60) / pre * 1000 + answer_tokens / gen * 1000
    why.append(f"token budget {budget}: reading at {pre:.0f} tok/s and answering at {gen:.0f} tok/s "
               f"is ~{expected:.0f} ms (target {lim.latency_target_ms:.0f} ms)")
    room = max(0.0, profile.disk_free_mb - lim.reserve_disk_mb) * MB / bytes_per_note
    return ReadPlan("index" if use_index else "exact", nprobe, budget, round(expected, 1), int(room),
                    round(exact_ram, 1), why)


def _search_ms(profile: DeviceProfile, notes: int) -> float:
    if not profile.search_ms:
        return notes / 100_000 * 40.0  # a conservative default: 40 ms per 100k notes
    pts = sorted((int(k), v) for k, v in profile.search_ms.items())
    n0, t0 = pts[-1]
    return t0 * notes / n0  # exact search is linear in the number of notes


def index_threshold(profile: DeviceProfile, dim: int, limits: Limits | None = None, default: int = 1_000_000,
                    floor: int = 20_000) -> int:
    """How many notes before memory should be searched through the learned index on this device: a million (in RAM
    exact search is as fast at equal recall, results/bulk/scale.json), or sooner when exact search's vectors would
    take over a quarter of the spare RAM (the index reads them from disk)."""
    lim = limits or Limits()
    spare = max(0.0, profile.ram_available_mb - lim.reserve_ram_mb)
    fits = int(0.25 * spare * MB / (dim * 4)) if spare else default
    return max(floor, min(default, fits))
