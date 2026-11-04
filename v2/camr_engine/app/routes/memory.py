"""Memory's routes: what the stage draws, for every reach the chat reads (or the app's one memory, or a recorded one).

- ``GET /api/brain``: moments, rooms, layout and recent answers (as before);
- ``GET /api/memory/stage``: everything the stage lays out once: each reach's moments, rooms, layout and vault notes,
  what each room has been through (reads, last share), the core, the hot shelf in RAM, the model's weights and the
  desk's header. ``doors=1`` adds the vault's doors, for vault mode;
- ``GET /api/memory/feed?ev=<reach>@<n>,...&mx=<reach>@<n>,...``: new lines of every reach's ``events.jsonl`` and
  ``metrics.jsonl`` after those line numbers, merged in time order, each with its ``reach`` and its line ``i``. A
  reach without a cursor starts at its end, or ``tail=K`` lines before it. The page polls this (no EventSource: it
  cannot send the token header);
- ``GET /api/memory/summary``: medians and 90th percentiles over every answer's record in every reach read;
- ``GET /api/memory/room?reach=&id=``: one room for its sheet: moments with their words, bytes, reads, the last
  answer's share per moment, and doors to other rooms;
- ``GET /api/memory/moment?reach=&id=``: one moment's words, for a hover;
- ``GET /api/memory/note?reach=&id=``: one vault note: its words, properties, doors and backlinks.

Nothing here writes to a memory, except that a live memory's layout is cached beside its rooms (``layout.json``), as
the brain view always did. A recorded memory is laid out in RAM and never written. The routes here only read, so they
open the chat's session only when that needs no waiting (see chat.Talk.poll).
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from camr_engine.app.web import Refused, Request, Routes, part

WATCHED = (12, 16, 20, 24)  # camr_engine.events.LAYERS, without importing MLX
LAYERS = 28  # the 1.7B's; a recorded memory does not say
TEXT = 120  # a moment's words in the stage snapshot are cut here; the rest comes on hover
TSNE_MAX = 600  # above this many moments the layout is a plain projection (exact t-SNE grows as n squared)
TAIL_MAX = 500


@dataclass
class Source:
    """One memory the stage shows: a reach the session reads, or the app's own memory, or a recorded folder."""

    label: str
    folder: Path
    memory: object | None = None  # the open Memory, or None for a recorded folder
    written: bool = False

    @property
    def kind(self) -> str:
        return self.label.partition(":")[0] if self.label else "memory"

    @property
    def name(self) -> str:
        return self.label.partition(":")[2]


# -- which memories


def _talk(app):
    from camr_engine.app.routes.chat import talk

    return talk(app)


def sources(app, *, open_: bool = True) -> list[Source]:
    """The memories to show, in the session's order of reading (the written reach first when it is read first)."""
    t = _talk(app)
    session = t.session if t is not None else None
    if session is None and t is not None and open_:
        session = t.poll()  # never waits for the model, and a failed open is tried again only every 30 s
    if session is not None:
        return [Source(r.label, Path(m.path), m, r == session.home) for r, m in session.memories.items()]
    memory = getattr(app, "memory", None)
    path = getattr(memory, "path", None)
    if memory is not None and path is not None and getattr(memory, "rooms", None) is not None:
        return [Source(getattr(memory, "reach", None) or "memory", Path(path), memory, True)]
    folder = getattr(app, "folder", None)
    if folder is not None:
        return [Source(_recorded_reach(Path(folder)) or "memory", Path(folder), None, True)]
    return []


def unread(app) -> list[Source]:
    """Reaches the session could read but does not, that exist on disk: shown at the far step (the aperture)."""
    from camr_engine.reach import KINDS, Reach

    t = _talk(app)
    if t is None or t.session is None:
        return []
    names = {"session": t.name, "project": t.project, "agent": t.agent, "global": ""}
    have = {r.label for r in t.session.memories}
    out = []
    for k in KINDS:
        if k != "global" and not names[k]:
            continue
        r = Reach(k, names[k])
        folder = r.path(t.root)
        if r.label not in have and (folder / "index.json").exists():
            out.append(Source(r.label, folder, None, False))
    return out


def _recorded_reach(folder: Path) -> str | None:
    try:
        return json.loads((folder / "vault" / ".camr-index.json").read_text()).get("reach")
    except (OSError, ValueError, AttributeError):
        return None


# -- the feed: several JSON-lines logs read as one stream


def _tail(app, path: Path):
    from camr_engine.app.tail import Tail

    tails = part(app, "_memory_tails", dict)
    key = str(path)
    if key not in tails:
        tails[key] = Tail(path)
    return tails[key]


def cursors(text: str) -> dict[str, int]:
    """``global@40,session:x@12`` as {reach: line}; anything unreadable is a 400."""
    out: dict[str, int] = {}
    for part_ in (text or "").split(","):
        if not part_:
            continue
        label, at, n = part_.rpartition("@")
        if not at or not n.isdigit() or len(label) > 100:
            raise Refused(400, "cursors read <reach>@<line>,...")
        out[label] = int(n)
    return out


def read_logs(app, srcs: list[Source], name: str, after: dict[str, int], tail: int = 0) -> tuple[list[dict], dict]:
    """New lines of ``name`` in every source after its cursor, merged in time order, and the next cursors."""
    got, nxt = [], {}
    for s in srcs:
        t = _tail(app, s.folder / name)
        c = after.get(s.label)
        r = t.read(None, tail=min(tail, TAIL_MAX)) if c is None else t.read(c, limit=TAIL_MAX)
        nxt[s.label] = r["next"]
        for e in r["events"]:
            e.setdefault("reach", s.label if s.label != "memory" else None)
            e["src"] = s.label
            got.append(e)
    got.sort(key=lambda e: (str(e.get("at") or ""), e["src"], e["i"]))
    return got, nxt


def last_event(app, memory, kinds: tuple[str, ...]) -> dict | None:
    """The newest line of a memory's own event log, if it is one of ``kinds``, with its line ``i``."""
    log = getattr(memory, "log", None)
    if log is None:
        return None
    r = _tail(app, Path(log.path)).read(None, tail=1)
    e = r["events"][-1] if r["events"] else None
    return e if e is not None and e.get("type") in kinds else None


# -- what each room has been through, kept up to date from its log


class History:
    """Reads, last share and uses per room and moment, read once from a log and then only from its new lines."""

    def __init__(self):
        self.next = 0
        self.reads: dict[int, int] = {}  # room -> answers that laid it on the desk
        self.last_share: dict[int, float] = {}  # room -> its moments' share of the last answer that read it
        self.last_answer: dict[int, int] = {}  # room -> the line of that answer
        self.used: dict[int, int] = {}  # moment -> answers it was used in
        self.picked: dict[int, int] = {}  # moment -> answers it was on the desk in
        self.answers = 0
        self.lock = threading.Lock()

    def update(self, tail, members: dict[int, set[int]]) -> History:
        with self.lock:
            while True:
                r = tail.read(self.next, limit=TAIL_MAX)
                for e in r["events"]:
                    if e.get("type") not in ("answer", "agent"):
                        continue
                    self.answers += 1
                    for n in e.get("nodes") or []:
                        self.picked[n] = self.picked.get(n, 0) + 1
                    for n in e.get("used") or []:
                        self.used[n] = self.used.get(n, 0) + 1
                    room = e.get("room")
                    if room is None:
                        continue
                    self.reads[room] = self.reads.get(room, 0) + 1
                    mine = members.get(room, set())
                    share = sum(x for n, x in zip(e.get("nodes") or [], e.get("share") or []) if n in mine)
                    self.last_share[room] = round(float(share), 4)
                    self.last_answer[room] = e["i"]
                done = r["next"] <= self.next or r["next"] >= r["total"]
                self.next = max(self.next, r["next"])
                if done:
                    return self


def history(app, s: Source, members: dict[int, set[int]]) -> History:
    keep = part(app, "_memory_history", dict)
    key = str(s.folder / "events.jsonl")
    tail = _tail(app, s.folder / "events.jsonl")
    if key not in keep or tail.read(None, tail=0)["total"] < keep[key].next:  # the log was started again
        keep[key] = History()
    return keep[key].update(tail, members)


# -- one memory's contents, live or recorded


def _index(folder: Path) -> dict:
    try:
        return json.loads((folder / "index.json").read_text())
    except (OSError, ValueError):
        return {"token_bytes": None, "moments": [], "rooms": []}


def _contents(app, s: Source) -> dict:
    """Moments as (room, day, tokens, start, text), rooms as (id, tokens, members, asleep), the token size, and the
    vault's notes, whether the memory is open here or only recorded on disk. A live memory is read while the session's
    thread may be writing to it, so a read that meets a change is simply taken again."""
    for attempt in range(3):
        try:
            return _read_contents(app, s)
        except RuntimeError:  # "dictionary changed size during iteration"
            if attempt == 2:
                raise
            time.sleep(0.05)
    raise AssertionError("unreachable")


def _read_contents(app, s: Source) -> dict:
    m = s.memory
    if m is not None and getattr(m, "rooms", None) is not None:
        r = m.rooms
        moments = [(x.room, x.day, x.tokens, x.start, x.text) for x in list(r.moments)]
        tiers = getattr(m, "tiers", None)
        asleep = set(tiers.sleeping) if tiers is not None else {x.rid for x in r.rooms if x.tokens and
                                                                 not r.file(x.rid).exists()}
        rooms = [(x.rid, x.tokens, list(x.members), x.rid in asleep) for x in list(r.rooms)]
        notes = _live_notes(m)
        return {"moments": moments, "rooms": rooms, "token_bytes": r.token_bytes, "notes": notes,
                "vault_bytes": m.vault.disk_bytes() if getattr(m, "vault", None) is not None else None}
    index = _index(s.folder)
    moments = [(x["room"], x["day"], x["tokens"], x.get("start", 0), x["text"]) for x in index["moments"]]
    rooms = []
    for x in index["rooms"]:
        f = s.folder / f"room-{x['rid']:06d}.notes"
        rooms.append((x["rid"], x["tokens"], list(x["members"]), bool(x["tokens"]) and not f.exists()))
    notes, vault_bytes = _recorded_notes(s.folder)
    return {"moments": moments, "rooms": rooms, "token_bytes": index.get("token_bytes"), "notes": notes,
            "vault_bytes": vault_bytes}


def _live_notes(m) -> list[dict] | None:
    v = getattr(m, "vault", None)
    if v is None:
        return None
    return [{"id": n.id, "moment": n.moment, "day": n.day, "strength": n.strength, "asleep": n.asleep,
             "pinned": n.pinned, "tags": list(n.tags), "links": dict(n.links)} for n in v.notes()]


def _recorded_notes(folder: Path) -> tuple[list[dict] | None, int | None]:
    path = folder / "vault" / ".camr-index.json"
    try:
        saved = json.loads(path.read_text()).get("notes", {})
    except (OSError, ValueError):
        return None, None
    notes = [{"id": nid, "moment": n.get("moment"), "day": n.get("day"), "strength": n.get("strength", 1.0),
              "asleep": bool(n.get("asleep")), "pinned": bool(n.get("pinned")), "tags": list(n.get("tags") or []),
              "links": dict(n.get("links") or {})} for nid, n in sorted(saved.items())]
    size = sum(int((n.get("file") or [0, 0])[1]) for n in saved.values())
    return notes, size


def _layout(app, s: Source, moments: list[tuple]) -> list[list[float]]:
    """One [x, y] in 0–1 per moment: the brain view's t-SNE (cached beside a live memory's rooms as layout.json), or
    a plain projection for a memory too big for exact t-SNE. A cache a few moments behind is extended in RAM, each
    new moment at its room's mean (the stage keeps positions for the session anyway); a recorded memory is laid out
    in RAM only."""
    import numpy as np

    from camr_engine.view.layout import positions, tsne

    n = len(moments)
    if n == 0:
        return []
    m = s.memory
    live = m is not None and getattr(m, "rooms", None) is not None
    try:
        got = json.loads((s.folder / "layout.json").read_text())
        count, xy = int(got.get("moments", -1)), got.get("xy") or []
    except (OSError, ValueError, TypeError):
        count, xy = -1, []
    if count == n and len(xy) == n:
        return xy
    if 0 < count < n and len(xy) == count and n <= 1.5 * count + 20:
        return _extend(xy, moments)
    if live and n <= TSNE_MAX:
        return positions(m.rooms)[:n]
    keep = part(app, "_memory_layouts", dict)  # one layout per folder, made again when its moments change
    key = str(s.folder)
    got = keep.get(key)
    if got is not None and got[0] == n:
        return got[1]
    try:
        vecs = m.rooms.vectors if live else np.load(s.folder / "vectors.npy")
        vecs = np.asarray(vecs, dtype=np.float32)[:n]
    except (OSError, ValueError, AttributeError):
        vecs = None
    grid = vecs is None or len(vecs) < n
    if grid:
        xy = [[(i % 32) / 31, (i // 32) / max(1, (n - 1) // 32)] for i in range(n)]  # no vectors: a plain grid
    elif n <= TSNE_MAX:
        xy = tsne(vecs).tolist()
    else:
        xy = _projection(vecs)
    xy = [[round(float(a), 4), round(float(b), 4)] for a, b in xy]
    keep[key] = (n, xy)
    if live and not grid:  # cached beside the rooms, so the next snapshots extend it instead of laying out again
        _save_layout(s.folder, n, xy)
    return xy


def _save_layout(folder: Path, n: int, xy: list) -> None:
    tmp = folder / f".layout.json.{os.getpid()}.{threading.get_ident()}"
    try:
        tmp.write_text(json.dumps({"moments": n, "xy": xy}))
        os.replace(tmp, folder / "layout.json")
    except OSError:
        tmp.unlink(missing_ok=True)


def _extend(xy: list, moments: list[tuple]) -> list[list[float]]:
    """A layout for more moments than it was made for: each new moment at its room's mean (a new room at the centre)."""
    out = [list(p) for p in xy]
    by_room: dict[int, list] = {}
    for (room, *_), p in zip(moments, out):
        by_room.setdefault(room, []).append(p)
    for room, *_ in moments[len(out):]:
        pts = by_room.get(room)
        p = [sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts)] if pts else [0.5, 0.5]
        out.append([round(p[0], 4), round(p[1], 4)])
        by_room.setdefault(room, []).append(out[-1])
    return out


def _projection(vecs) -> list[list[float]]:
    import numpy as np

    c = vecs - vecs.mean(0)
    y = np.linalg.svd(c, full_matrices=False)[0][:, :2]
    y = (y - y.min(0)) / np.maximum(y.max(0) - y.min(0), 1e-9)
    return y.tolist()


# -- what sits in RAM


def _weights(app) -> int | None:
    """The memory reader's weights on disk, which is what MLX holds in RAM for them."""
    repo = getattr(getattr(app, "reader", None), "repo", None)
    if not repo:
        return None

    def make():
        from camr_engine.app import hub

        try:
            return {m["repo"]: m["weights_bytes"] for m in hub.local()}
        except Exception:  # noqa: BLE001 (no Hugging Face cache)
            return {}

    box = part(app, "_memory_weights", lambda: {"at": -1e9, "value": {}})
    if time.monotonic() - box["at"] > 60:
        box["value"], box["at"] = make(), time.monotonic()
    return box["value"].get(repo)


def _ram(srcs: list[Source], session) -> dict | None:
    """The hot shelf: the core and the hot rooms in RAM, least recently used first, against the RAM budget."""
    pool = getattr(session, "pool", None)
    label = {id(getattr(s.memory, "tiers", None)): s.label for s in srcs if getattr(s.memory, "tiers", None)}
    if pool is None:
        tiers = [getattr(s.memory, "tiers", None) for s in srcs]
        tiers = [t for t in tiers if t is not None]
        if not tiers:
            return None
        pool = tiers[0].pool
    hot = [{"reach": label.get(id(t)), "room": rid, "bytes": int(pool.sizes.get((t, rid), 0))}
           for (t, rid) in list(pool.hot.keys()) if id(t) in label]
    return {"budget_bytes": int(pool.budget), "used_bytes": int(pool.used_bytes()), "core_bytes": int(pool.core_bytes),
            "hot": hot}


def _core(session) -> dict:
    core = getattr(session, "core", None)
    if core is None:
        return {"on": False, "tokens": 0, "bytes": 0, "notes": []}
    return {"on": True, "tokens": int(core.tokens), "bytes": int(core.bytes), "notes": list(core.members),
            "left_out": list(core.left_out)}


# -- the snapshot


def stage(app, *, doors: bool = False) -> dict:
    srcs = sources(app)
    t = _talk(app)
    session = t.session if t is not None else None
    far = unread(app)
    reaches, token_bytes, header, layers = [], None, None, LAYERS
    first_day, last_day = None, None
    for s in srcs + far:
        c = _contents(app, s)
        token_bytes = token_bytes or c["token_bytes"]
        members = {rid: set(ms) for rid, _, ms, _ in c["rooms"]}
        h = history(app, s, members)
        notebook = getattr(s.memory, "notebook", None)
        if notebook is not None:
            header, layers = int(notebook.p), int(notebook.shape.layers)
        days = [d for _, d, _, _, _ in c["moments"] if d is not None]
        if days:
            first_day = min(days) if first_day is None else min(first_day, min(days))
            last_day = max(days) if last_day is None else max(last_day, max(days))
        hot = set()
        tiers = getattr(s.memory, "tiers", None)
        if tiers is not None:
            hot = set(tiers.hot)
        notes = c["notes"]
        note_rows, door_rows = None, None
        if notes is not None:
            index = {n["id"]: k for k, n in enumerate(notes)}
            into: dict[str, int] = {}
            for n in notes:
                for other in n["links"]:
                    if other in index:
                        into[other] = into.get(other, 0) + 1
            note_rows = [[n["id"], n["moment"], n["day"], round(float(n["strength"]), 4), int(n["asleep"]),
                          into.get(n["id"], 0), int(n["pinned"]), int("core" in n["tags"])] for n in notes]
            if doors:
                door_rows = [[index[n["id"]], index[o], round(float(w), 3)] for n in notes for o, w in n["links"].items()
                             if o in index and index[n["id"]] < index[o]]
        reaches.append({
            "label": s.label, "kind": s.kind, "name": s.name, "written": s.written, "read": s not in far,
            "moments": [[room, day, tokens, start] for room, day, tokens, start, _ in c["moments"]],
            "texts": [text[:TEXT] for *_, text in c["moments"]],
            "rooms": [[rid, tokens, int(asleep), int(rid in hot)] for rid, tokens, _, asleep in c["rooms"]],
            "layout": _layout(app, s, c["moments"]),
            "stats": {"reads": h.reads, "last_share": h.last_share, "used": h.used, "picked": h.picked,
                      "answers": h.answers},
            "room_bytes": sum(tok for _, tok, _, asleep in c["rooms"] if not asleep) * (c["token_bytes"] or 0),
            "history_tokens": sum(tok for _, tok, _, _ in c["rooms"]),
            "notes": note_rows, "doors": door_rows, "vault_bytes": c["vault_bytes"],
        })
    return {"reaches": reaches, "token_bytes": token_bytes, "layers": layers, "watched": list(WATCHED),
            "header_tokens": header, "core": _core(session), "ram": _ram(srcs, session), "weights_bytes": _weights(app),
            "model": getattr(getattr(app, "reader", None), "repo", None), "on": getattr(session, "on", True),
            "fixture": bool(getattr(app, "fixture", False)), "first_day": first_day, "last_day": last_day,
            "session": getattr(session, "name", None)}


def _source(app, label: str) -> Source:
    for s in sources(app, open_=False) + unread(app):
        if s.label == label or (label in ("", "memory") and s.label == "memory"):
            return s
    raise Refused(404, f"no memory {label!r} is shown")


def room(app, label: str, rid: int) -> dict:
    s = _source(app, label)
    c = _contents(app, s)
    rooms = {r[0]: r for r in c["rooms"]}
    if rid not in rooms:
        raise Refused(404, f"{label} has no room {rid}")
    _, tokens, members, asleep = rooms[rid]
    tb = c["token_bytes"] or 0
    f = s.folder / f"room-{rid:06d}.notes"
    h = history(app, s, {r: set(ms) for r, _, ms, _ in c["rooms"]})
    shares: dict[int, float] = {}
    last = h.last_answer.get(rid)
    if last is not None:
        got = _tail(app, s.folder / "events.jsonl").read(last, limit=1)["events"]
        if got:
            e = got[0]
            shares = {n: x for n, x in zip(e.get("nodes") or [], e.get("share") or []) if n in set(members)}
    owner = {}
    notes = c["notes"] or []
    by_moment = {n["moment"]: n for n in notes if n.get("moment") is not None}
    for n in notes:
        if n.get("moment") is not None and n["moment"] < len(c["moments"]):
            owner[n["id"]] = c["moments"][n["moment"]][0]
    doors: dict[int, list[float]] = {}
    for mid in members:
        n = by_moment.get(mid)
        for other, w in (n["links"] if n else {}).items():
            r = owner.get(other)
            if r is not None and r != rid:
                doors.setdefault(r, []).append(float(w))
    tiers = getattr(s.memory, "tiers", None)
    return {"reach": s.label, "id": rid, "tokens": tokens, "bytes": tokens * tb,
            "file_bytes": f.stat().st_size if f.exists() else 0, "asleep": asleep,
            "hot": bool(tiers is not None and rid in tiers.hot), "reads": h.reads.get(rid, 0),
            "last_share": h.last_share.get(rid), "last_answer": last, "shares": shares,
            "moments": [{"id": mid, "day": c["moments"][mid][1], "tokens": c["moments"][mid][2],
                         "text": c["moments"][mid][4], "note": by_moment.get(mid, {}).get("id"),
                         "used": h.used.get(mid, 0)} for mid in members if mid < len(c["moments"])],
            "doors": sorted(({"room": r, "count": len(ws), "weight": round(sum(ws), 3)} for r, ws in doors.items()),
                            key=lambda d: -d["weight"])[:8]}


def moment(app, label: str, mid: int) -> dict:
    s = _source(app, label)
    c = _contents(app, s)
    if not 0 <= mid < len(c["moments"]):
        raise Refused(404, f"{label} has no moment {mid}")
    r, day, tokens, _, text = c["moments"][mid]
    return {"reach": s.label, "id": mid, "room": r, "day": day, "tokens": tokens, "text": text}


def note(app, label: str, nid: str) -> dict:
    from camr_engine.vault import _ok, parse, split

    if not _ok(nid):  # the vault's own rule: a file name a wikilink can point at, never a path
        raise Refused(400, "not a note id")
    s = _source(app, label)
    v = getattr(s.memory, "vault", None)
    folder = Path(v.path) if v is not None else s.folder / "vault"
    path = folder / f"{nid}.md"
    if not path.is_file() or not path.resolve().is_relative_to(folder.resolve()):
        raise Refused(404, f"no note {nid}")
    text = path.read_text(encoding="utf-8")
    n = parse(nid, text)
    _, body = split(text)
    c = _contents(app, s)
    notes = {x["id"]: x for x in c["notes"] or []}
    back = sorted(((o["id"], o["links"][nid]) for o in notes.values() if nid in o["links"]), key=lambda kv: -kv[1])
    def head(other: str) -> str | None:
        x = notes.get(other)
        mid = x.get("moment") if x else None
        return c["moments"][mid][4][:TEXT] if mid is not None and mid < len(c["moments"]) else None
    return {"reach": s.label, "id": nid, "text": body, "day": n.day, "date": n.date, "room": n.room,
            "moment": n.moment, "tags": n.tags, "strength": n.strength, "pinned": n.pinned, "asleep": n.asleep,
            "links": [{"id": o, "weight": w, "head": head(o)} for o, w in sorted(n.links.items(), key=lambda kv: -kv[1])],
            "backlinks": [{"id": o, "weight": w, "head": head(o)} for o, w in back[:40]]}


def register(routes: Routes) -> None:
    @routes.get("/api/brain")
    def brain(req: Request) -> dict:
        fn = getattr(req.app, "brain", None)
        if fn is None:
            raise Refused(409, "this app has no memory to show")
        return fn()

    @routes.get("/api/memory/stage")
    def stage_route(req: Request) -> dict:
        return stage(req.app, doors=req.bool("doors"))

    @routes.get("/api/memory/feed")
    def feed(req: Request) -> dict:
        srcs = sources(req.app)
        tail = req.int("tail", 0, lo=0, hi=TAIL_MAX)
        events, ev = read_logs(req.app, srcs, "events.jsonl", cursors(req.str("ev", limit=4000)), tail)
        metrics, mx = read_logs(req.app, srcs, "metrics.jsonl", cursors(req.str("mx", limit=4000)), tail)
        return {"events": events, "metrics": metrics, "ev": ev, "mx": mx, "reaches": [s.label for s in srcs]}

    @routes.get("/api/memory/summary")
    def summary_route(req: Request) -> dict:
        from camr_engine.metrics import Meter, summary

        rows = [r for src in sources(req.app) for r in Meter.read(src.folder / "metrics.jsonl")]
        return summary(rows)

    @routes.get("/api/memory/room")
    def room_route(req: Request) -> dict:
        return room(req.app, req.str("reach", limit=100), req.int("id", 0, lo=0))

    @routes.get("/api/memory/moment")
    def moment_route(req: Request) -> dict:
        return moment(req.app, req.str("reach", limit=100), req.int("id", 0, lo=0))

    @routes.get("/api/memory/note")
    def note_route(req: Request) -> dict:
        return note(req.app, req.str("reach", limit=100), req.str("id", limit=201))  # past 200 is refused, not cut


def folder_size(folder: Path, pattern: str) -> int:
    """The bytes of the files in ``folder`` matching ``pattern`` (a reach not open here, read from disk)."""
    total = 0
    try:
        with os.scandir(folder) as it:
            for e in it:
                if e.is_file(follow_symlinks=False) and Path(e.name).match(pattern):
                    total += e.stat(follow_symlinks=False).st_size
    except OSError:
        pass
    return total
