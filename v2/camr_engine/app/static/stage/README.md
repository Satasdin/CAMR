# The stage: shared by Chat and Memory

`design/DIRECTION.md` ("The live memory visual") is the spec. These modules implement it; screens import them from
`/static/stage/`.

| File | What it is |
| --- | --- |
| `stage.js` | `Stage`: the specimen. SSD plate (rooms as layer-by-token tiles, one band per reach), the bus (0–8 GB/s), the RAM plate (24 GB ruler, then the magnified core, hot shelf and desk), the vault drawer. Plays answers step by step. Also `index(snapshot)`, `ramFromState`, `fmtBytes`, `fmtRam`, `fmtTok` |
| `gl.js` | The renderer: plain WebGL 1 + `ANGLE_instanced_arrays`, instanced rects, dots and segments, a quarter-resolution halo of the lit part only, and a Canvas 2D fallback (`no WebGL · flat view`) |
| `palette.js` | Channels and steps read from `tokens.css` at start; half-lives |
| `place.js` | Bands (height ∝ √bytes, at least 64 px), tile sizes (40% cover), 60 passes of separation, cells |
| `feed.js` | `memoryFeed(api)`: the merged events and metrics of every reach being read, polled from `/api/memory/feed` while a screen that draws memory is on show |
| `trace.js` | `Trace`: the stacked 28 px rows (SSD R, SSD W, RAM, HOT, DESK, USED, WORDS, TTFT), roll and answer modes, cursors |
| `parts.js` | `makeParts(api)`: `Toggle`, `ReachPicker`, `PathStrip`, `Lanes`, `Readouts`, `Sheet` |
| `stage.css`, `chat.css` | Styles for the stage, its parts, the Memory screen and the Chat screen |

regl is vendored, but it builds its draw commands with `new Function`, which the page's `script-src 'self'` policy
refuses. The renderer makes the same few WebGL calls by hand.

## Using a Stage

```js
import { Stage } from "/static/stage/stage.js";
import { memoryFeed } from "/static/stage/feed.js";

const stage = new Stage(hostDiv, api, { mode: "live", onSelect, onNote, onVault, onWord });
stage.setSnapshot(await api.get("/api/memory/stage"));   // lay everything out
const feed = memoryFeed(api);
feed.on("answer", (rec) => stage.playAnswer(rec));       // rec = {e: answer event, m: its metrics record or null}
feed.on("event", (e) => { if (e.live) stage.event(e); }); // remember, sleep, wake
// in the screen's handle:
show() { stage.show(); feed.start(); }
hide() { stage.hide(); feed.stop(); }
```

- The host is any positioned element; the stage fills it and follows its size.
- Modes: `live` (with the vault drawer), `compact` (smaller labels, no drawer, no halo), `path` (one answer: call
  `setPath({e, m})` or `share(otherStage)` first). `setVault(true)` draws notes and doors at the same positions.
- `setRam(ram)` updates the hot shelf (`ramFromState(api.state.value, stage.data, tokenBytes)` reads it from
  `/api/state`); `setRead(labels)` closes the aperture on other reaches; `setOn(false)` shows `memory off`.
- `nodeFlare(reach, moment, used)` flares one moment (a word hovered in the chat). `select(key)` outlines a room in
  white.
- The frame loop runs only while a mark is within six half-lives of its event; `?debug=1` shows 0 fps at rest.

## Not done yet

- The vault mode's local-graph depth slider and the growth scrub (P2/P3).
