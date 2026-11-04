"""This Mac: its chip, unified RAM, GPU cores, free disk, RAM in use now, and a quick SSD read probe.

Everything is read from the system itself (sysctl, ioreg, vm_stat, statvfs and libproc), so nothing needs installing.
A value that cannot be read is None, never a guess. The GPU limit is MLX's own figure (the largest working set Metal
recommends on this Mac, about three quarters of the RAM), read without loading any model.

The probe writes a temporary file past the Mac's file cache, reads it back the way rooms are read (1 MB pieces,
eight at once, F_NOCACHE), and deletes it. It measures this SSD's burst read, so it runs only when asked.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import datetime as dt
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROBE_BYTES = 256 * 2**20
PRESSURE = {1: "normal", 2: "tight", 4: "critical"}  # kern.memorystatus_vm_pressure_level

_libc = None
_cache: dict[str, object] = {}
_lock = threading.Lock()


def _sh(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _c():
    global _libc
    if _libc is None and sys.platform == "darwin":
        _libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.dylib", use_errno=True)
    return _libc


def sysctl(name: str, *, number: bool = False) -> int | str | None:
    """One sysctl value, as a number or as text; None when this Mac has no such value."""
    libc = _c()
    if libc is not None:
        size = ctypes.c_size_t(0)
        if libc.sysctlbyname(name.encode(), None, ctypes.byref(size), None, 0) != 0 or not size.value:
            return None
        buf = ctypes.create_string_buffer(size.value)
        if libc.sysctlbyname(name.encode(), buf, ctypes.byref(size), None, 0) != 0:
            return None
        raw = buf.raw[:size.value]
        if number:
            return int.from_bytes(raw, sys.byteorder, signed=True) if size.value in (4, 8) else None
        return raw.rstrip(b"\0").decode(errors="replace")
    out = _sh("sysctl", "-n", name)
    if number:
        return int(out) if out.lstrip("-").isdigit() else None
    return out or None


def _int(name: str) -> int | None:
    v = sysctl(name, number=True)
    return v if isinstance(v, int) else None


def chip() -> str | None:
    v = sysctl("machdep.cpu.brand_string")
    return v if isinstance(v, str) else None


def ram_bytes() -> int | None:
    """Unified RAM, in bytes."""
    return _int("hw.memsize")


def cpu_cores() -> dict:
    return {"performance": _int("hw.perflevel0.physicalcpu"), "efficiency": _int("hw.perflevel1.physicalcpu"),
            "total": _int("hw.ncpu")}


def gpu_cores() -> int | None:
    """GPU cores, from the GPU's own entry in the I/O registry."""
    m = re.search(r'"gpu-core-count"\s*=\s*(\d+)', _sh("ioreg", "-rc", "AGXAccelerator", "-d", "1", "-k",
                                                       "gpu-core-count"))
    return int(m.group(1)) if m else None


def gpu_limit() -> tuple[int | None, str]:
    """The most memory a model may hold on the GPU, and where that figure came from: MLX's
    ``max_recommended_working_set_size`` (Metal's own limit) or, without MLX, unknown."""
    try:
        import mlx.core as mx

        info = mx.device_info() if hasattr(mx, "device_info") else mx.metal.device_info()
        return int(info["max_recommended_working_set_size"]), "metal"
    except Exception:
        return None, "unknown"


def disk(path: Path | str = Path.home()) -> dict:
    """The disk holding ``path``: its size and the bytes free to this user."""
    try:
        s = os.statvfs(path)
    except OSError:
        return {"path": str(path), "total_bytes": None, "free_bytes": None}
    return {"path": str(path), "total_bytes": s.f_blocks * s.f_frsize, "free_bytes": s.f_bavail * s.f_frsize}


def _vm_stat() -> dict[str, int]:
    out = _sh("vm_stat")
    page = re.search(r"page size of (\d+) bytes", out)
    pages = {k.strip().strip('"'): int(v) for k, v in re.findall(r"^([^:]+):\s+(\d+)\.", out, re.M)}
    return {"page": int(page.group(1)) if page else 0, **pages}


class _RUsage(ctypes.Structure):  # rusage_info_v2, up to the fields read here
    _fields_ = [("uuid", ctypes.c_uint8 * 16), ("user_time", ctypes.c_uint64), ("system_time", ctypes.c_uint64),
                ("pkg_idle_wkups", ctypes.c_uint64), ("interrupt_wkups", ctypes.c_uint64),
                ("pageins", ctypes.c_uint64), ("wired_size", ctypes.c_uint64), ("resident_size", ctypes.c_uint64),
                ("phys_footprint", ctypes.c_uint64), ("_rest", ctypes.c_uint64 * 32)]


def process_bytes(pid: int | None = None) -> int | None:
    """This process's memory as Activity Monitor counts it (its physical footprint, which includes what MLX holds
    on the GPU), else its resident size."""
    pid = os.getpid() if pid is None else pid
    if sys.platform == "darwin":
        try:
            lib = ctypes.CDLL(ctypes.util.find_library("proc") or "libproc.dylib")
            info = _RUsage()
            if lib.proc_pid_rusage(pid, 2, ctypes.byref(info)) == 0:
                return int(info.phys_footprint or info.resident_size)
        except (OSError, AttributeError):
            pass
    out = _sh("ps", "-o", "rss=", "-p", str(pid))
    return int(out) * 1024 if out.isdigit() else None


def memory_now() -> dict:
    """RAM in use now: in total (app memory, wired and compressed, as Activity Monitor's "Memory Used"), by this
    process, and the system's pressure level."""
    total = ram_bytes()
    vm = _vm_stat()
    used = None
    if vm.get("page"):
        p = vm["page"]
        anon = vm.get("Anonymous pages", vm.get("Pages active", 0))
        used = (anon - vm.get("Pages purgeable", 0) + vm.get("Pages wired down", 0)
                + vm.get("Pages occupied by compressor", 0)) * p
    level = _int("kern.memorystatus_vm_pressure_level")
    return {"total_bytes": total, "used_bytes": used,
            "free_bytes": total - used if total is not None and used is not None else None,
            "process_bytes": process_bytes(), "pressure_level": level, "pressure": PRESSURE.get(level)}


def detect(*, fresh: bool = False) -> dict:
    """What this Mac is, read once per process (the probe is kept separately, see ``probe``)."""
    with _lock:
        if fresh or "detect" not in _cache:
            limit, source = gpu_limit()
            _cache["detect"] = {"chip": chip(), "model": sysctl("hw.model"), "ram_bytes": ram_bytes(),
                                "cpu_cores": cpu_cores(), "gpu_cores": gpu_cores(), "gpu_limit_bytes": limit,
                                "gpu_limit_source": source, "os": _sh("sw_vers", "-productVersion") or None}
        out = dict(_cache["detect"])
    out["disk"] = disk()
    out["probe"] = _cache.get("probe")
    return out


def _read(fd: int, size: int, chunk: int, threads: int) -> int:
    from engram.rooms import CHUNK, THREADS

    chunk, threads = chunk or CHUNK, threads or THREADS

    def piece(off: int) -> int:
        return len(os.pread(fd, min(chunk, size - off), off))

    with ThreadPoolExecutor(threads) as pool:
        return sum(pool.map(piece, range(0, size, chunk)))


def probe(folder: Path | str | None = None, size: int = PROBE_BYTES, *, chunk: int = 0, threads: int = 0) -> dict:
    """Write ``size`` bytes past the file cache, read them back in one burst as rooms are read, and delete the file.
    Returns the bytes, seconds and GB/s of the read."""
    from engram.rooms import _open

    folder = Path(folder) if folder is not None else Path(tempfile.gettempdir())
    path = folder / f".engram-probe-{os.getpid()}-{time.monotonic_ns()}.bin"
    block = os.urandom(1 << 20)
    try:
        fd = _open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        try:
            for off in range(0, size, len(block)):
                os.write(fd, block[:min(len(block), size - off)])
            os.fsync(fd)
        finally:
            os.close(fd)
        fd = _open(path, os.O_RDONLY)
        try:
            t = time.perf_counter()
            got = _read(fd, size, chunk, threads)
            seconds = time.perf_counter() - t
        finally:
            os.close(fd)
    finally:
        path.unlink(missing_ok=True)
    out = {"bytes": got, "seconds": round(seconds, 5), "gbps": round(got / seconds / 1e9, 2) if seconds > 0 else None,
           "folder": str(folder), "at": dt.datetime.now().isoformat(timespec="seconds")}
    with _lock:
        _cache["probe"] = out
    return out
