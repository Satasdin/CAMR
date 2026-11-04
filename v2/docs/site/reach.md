# Reach and the switch

*Reach* is how far a memory goes: one conversation's, a project's, an agent's, or one global memory shared by
everything. The *switch* turns memory off, so the model answers alone.

## The four reaches

Each reach is its own folder under one root, `~/.camr` by default. Each folder holds its own rooms and its own
vault.

| Reach | Label | Folder | For |
| --- | --- | --- | --- |
| session | `session:<id>` | `~/.camr/session/<id>/` | one conversation; a new id each time by default |
| project | `project:<name>` | `~/.camr/project/<name>/` | everything about one project |
| agent | `agent:<name>` | `~/.camr/agent/<name>/` | one agent's own memory |
| global | `global` | `~/.camr/global/` | facts that hold everywhere |

A name is plain: letters, digits, `.`, `_` and `-`, at most 64 characters. A name is never a path.

## Reading several, writing one

A `Session` reads several reaches at once and writes to one.

- `reads` names the reaches to read, in order of preference. The default is `("session", "global")`.
- `writes` is where new moments go. The default is `"session"`. It is always read too.
- A question is embedded once. It picks the best room over every reach read: the room of the closest moment in any
  of them. That reach's own closest moments go on the desk as words. When two reaches are equally close, the one
  named first wins.
- `remember(text, day, to="global")` sends one moment to another reach the session reads.
- A moment kept in a shared reach (project, agent or global) is saved at once, so its index is never behind its
  files.
- With `core=True`, one core is built from the `core` notes of every reach read, and goes on every desk.
- The header is read once and shared by every reach.

```python
from camr_engine.models import Embedder, Reader
from camr_engine.reach import Session

reader, embedder = Reader(), Embedder()
with Session(reader, embedder, project="kitchen", reads=("session", "project", "global")) as s:
    s.remember("[2026-01-05] The fee is 1% rounded up to the next 5 shillings.", 0, to="project")
    s.remember("[2026-01-05] My sister Amina moved to Nakuru.", 0, to="global")
```

A reach can also be given as a label, such as `"project:kitchen"`, or as a `Reach("project", "kitchen")`.

## One open per folder

- In one process, a reach folder is opened once. Every session reading it shares one `Memory`, which closes when the
  last of them closes.
- Another process cannot open the folder meanwhile. A lock on `<reach>/.lock` stops it, and the second process
  gets `ReachBusy`. Two writers of one room file would cut each other's notes.
- Close a session when done (`close()`, or a `with` block). That saves every reach and lets go of them.

## The switch

Memory can be turned off for a whole session.

```python
s = Session(reader, embedder, on=False)   # off from the start
s.switch(True)                             # on
s.switch(False)                            # off again
```

With memory off:
- `answer` is the plain model: the same prompt with no notes, read whole. Pass `plain_system="..."` to `Session`
  to use another system prompt instead.
- `remember` keeps nothing and returns `None`.
- Nothing is read from the SSD.
- The answer still gets a metrics record, with no history and no disk, so on and off compare directly.

The Ollama pairing has its own switches: `--no-memory` starts the proxy as a plain passthrough, and a request with
the header `X-CAMR-Memory: off` is forwarded with no notes. See [Pairing with Ollama](ollama.md).
