"""A recorded memory folder served read-only, with no model loaded, for looking at the app without the GPU.

    python -m camr_engine.app --fixture <memory folder>

The folder is what a run leaves: ``index.json``, ``events.jsonl``, ``metrics.jsonl``, ``layout.json`` and the room
files. The top strip shows a FIXTURE badge, telling, asking and errands are refused, and the Models screen works as
usual (it reads this Mac, not the memory).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path


class Fixture:
    fixture = True

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        if not self.folder.is_dir():
            raise FileNotFoundError(f"no memory folder at {self.folder}")

    def paths(self) -> dict[str, Path]:
        return {"events": self.folder / "events.jsonl", "metrics": self.folder / "metrics.jsonl",
                "memory": self.folder}

    def _index(self) -> dict:
        try:
            return json.loads((self.folder / "index.json").read_text())
        except (OSError, ValueError):
            return {"moments": [], "rooms": []}

    def state(self) -> dict:
        index = self._index()
        disk = sum(p.stat().st_size for p in self.folder.glob("room-*.notes"))
        return {"moments": len(index["moments"]), "rooms": len(index["rooms"]), "disk_mb": round(disk / 1e6, 1),
                "today": dt.date.today().isoformat()}

    def brain(self) -> dict:
        from camr_engine.app.server import shown
        from camr_engine.events import EventLog

        index = self._index()
        try:
            layout = json.loads((self.folder / "layout.json").read_text()).get("xy", [])
        except (OSError, ValueError):
            layout = []
        return shown(EventLog(self.folder / "events.jsonl").read(),
                     [{"room": m["room"], "day": m["day"], "text": m["text"]} for m in index["moments"]],
                     [{"id": r["rid"], "members": r["members"]} for r in index["rooms"]], layout)
