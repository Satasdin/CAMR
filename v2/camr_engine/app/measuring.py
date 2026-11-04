"""The measuring flag: while a benchmark measures, the app's views pause and the Models screen loads nothing, so the
GPU and the SSD belong to the measurement.

A measuring job says so with a small file, ``~/.camr/measuring.json`` (``CAMR_MEASURING`` names another), holding
its name, process id and start time. It counts only while that process is alive, so a crashed run never leaves the
app paused.

    from camr_engine.app.measuring import measuring
    with measuring("longhaul"):
        ...
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
from pathlib import Path


def path() -> Path:
    return Path(os.environ.get("CAMR_MEASURING") or Path.home() / ".camr" / "measuring.json")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def active() -> dict | None:
    """The job measuring now, or None."""
    p = path()
    try:
        job = json.loads(p.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(job, dict) or not isinstance(job.get("pid"), int) or not _alive(job["pid"]):
        return None
    return {"job": str(job.get("job", "measuring"))[:80], "pid": job["pid"], "started": job.get("started")}


@contextlib.contextmanager
def measuring(job: str):
    """Mark ``job`` as measuring for as long as the block runs."""
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"job": job, "pid": os.getpid(),
                               "started": dt.datetime.now().isoformat(timespec="seconds")}))
    os.replace(tmp, p)
    try:
        yield
    finally:
        try:
            if json.loads(p.read_text()).get("pid") == os.getpid():
                p.unlink()
        except (OSError, ValueError):
            pass
