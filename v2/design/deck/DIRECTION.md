# Direction: Phosphor

One of three proposals for the showcase app. This one is the pro-tool lens: terminal-native, dense but calm, with
a coding agent at its centre. No mockups are drawn here, on purpose. Each screen is described closely enough to
build or to render with real data.

## The idea in two sentences

A quiet, greyscale, keyboard-first console where the only things that glow are memory: amber in RAM, blue on the
SSD, violet in the vault, and green the instant a piece of memory is used in an answer. Every glow is a real event
from the engine, and it fades like phosphor on an oscilloscope. At rest the screen is black and still; at work it
shows exactly what moved, where it moved and how long that took.

## Principles

1. **Colour is memory.** Chrome, text and controls are greyscale. Colour appears only where memory is, so an answer
   given with no memory is grey all the way through. Claude, the yardstick, is always drawn in grey: it has no
   memory here.
2. **Hue says where, brightness says when, shape says what.**
   - Hue is the place: RAM, SSD or vault.
   - Brightness is recency and weight: lit at the event, then fading.
   - Shape is the kind of thing: a cell is a token's notes, a slab is a room, a line is a note, a tick is an event.
   - No colour is ever the only signal. Place is also a position on screen, "used" is also a tick and a flare, and
     "wrong" is also a ✗.
3. **Every light is a real event.** Nothing glows for decoration. Each flare maps to a record in `events.jsonl` or a
   metrics record, with its real timestamp. If an event is too fast to see, it is replayed slower, and the factor is
   printed on screen (for example "×1/20").
4. **Measured or nothing.** Every number on screen comes from a measurement on this Mac. A value that has not been
   measured shows "—". The app never fills it with an estimate.
5. **One hero per screen.** Each screen gives at least half its area to one live render of the engine's real data.
   The big picture is always that render, never a stock photo or an illustration. Text sits in narrow mono margins
   around it.
6. **Calm at rest.** No idle animation, spinners or looping glows. The render loop drops to 0 fps when nothing
   happens and pauses fully while a benchmark is measuring, so the UI never takes GPU or bandwidth from MLX.
7. **Keyboard first, terminal-native.** Every action is in the ⌘K palette. Screens are ⌘1–⌘6. The transcript is made
   of blocks, as in Warp. A status line runs along the bottom, as in Claude Code.
8. **Dense, not cluttered.** Small mono type and many numbers, but only one thing on screen is bright at a time.
   Chrome recedes: dim sidebar, hairlines rather than boxes (Linear's rule). Detail opens on demand in a drawer.
9. **Each screen proves one claim.** A one-line claim sits under each screen's name, with its live figure beside it.
   For example, Chat says "keeps answering without filling its context" with "in view 2.1K / history 1.04M".

## Colour tokens

The background is true black, so a glow reads crisp. Memory colours have three levels:
- **full:** the event itself, bloomed;
- **mid:** resident now, no bloom;
- **lo:** an outline or a mark at rest.

### Memory and signal: the only colours in the app

| Token | Full | Mid | Lo | Means |
| --- | --- | --- | --- | --- |
| `--ram` | `#FF8A3D` | `#B8622B` | `#3A2010` | **In RAM now:** the always-on core, the desk, model weights. Ember, because RAM is the hot, live place. |
| `--ssd` | `#3D8BFF` | `#2B63B8` | `#0F2240` | **On the SSD:** rooms at rest, downloaded model files, bytes read from disk. Cold blue for storage. |
| `--vault` | `#A77DFF` | `#7759B8` | `#251A40` | **In the vault, as words:** plain-text notes and links, and any memory that enters a model as text (Ollama, Qwen 27B). |
| `--used` | `#3DFF8F` | `#2BB866` | `#0F4024` | **Used in this answer:** a moment whose attention share reached ≥ 0.10 at a watched layer. Always bloomed and always with a tick. |
| `--seen` | `#FFFFFF` | `#BFC3C9` | `#3A3D42` | **Picked up, not used:** on the desk but below the share. Drawn as a white ring, never a fill. The keyboard focus ring uses it too. |
| `--wrong` | `#FF3D5A` | `#B82B40` | `#401018` | **Wrong answer or false memory.** Always a ✗ glyph or a stroke, never a filled area. Seen mostly on Bench and in replays. |
| `--transit` | `--ssd` → `--ram` | | | **Bytes moving from the SSD to RAM.** It is the only gradient in the app, and it is used only on moving particles. |

These keep the current Brain view's meanings: green for used, a white ring for picked up. The one change is that a
moment's cell is no longer red at rest. It takes the colour of where it lives (blue on the SSD, ember on the desk),
so red is free to mean wrong. Used-green on an ember desk keeps the green-on-red two-channel look he loved.

### Greyscale: everything else

| Token | Value | Use |
| --- | --- | --- |
| `--void` | `#000000` | The window and every canvas background |
| `--s1` | `#0A0B0D` | Panels: rail, drawers, status line |
| `--s2` | `#111317` | Raised items: hovered rows, the palette, popovers |
| `--line` | `#1C1F24` | Hairlines, stratum outlines, chart grid |
| `--line-hi` | `#2A2E35` | Row separators on hover, active outlines |
| `--fg` | `#E8EAED` | Primary text and the written words of an answer |
| `--fg-mid` | `#9AA0A8` | Labels and metadata |
| `--fg-lo` | `#5C626B` | Units, axis ticks, disabled items |
| `--none` | `#8A8F98` | **No memory:** Claude runs, memory-off runs, file reads in Code |

### Glow

- **In CSS:** `box-shadow: 0 0 0 1px var(--x), 0 0 12px color-mix(in srgb, var(--x) 45%, transparent)`, on marks
  only. Text never glows and is never blurred.
- **In WebGL:** selective bloom applies only to meshes flagged as events. Settings: luminance threshold 0.2,
  intensity 1.4, radius 0.6, mipmap blur.
- **Strength:** glow scales with brightness, which scales with recency (see Motion). A resident room is `mid` with no
  glow; only the event is `full` and bloomed.

## Type

- **Faces:**
  - **Geist Mono** is used for almost everything: labels, numbers, transcripts, code and axes. It is crisp at 11–12 px
    and has tabular figures.
  - **Geist Sans** is used only for the prose of an answer and for vault notes, the two places people read sentences.
  - Both are SIL Open Font License and ship as woff2 in the app.
- **Scale:**

| Token | Size / line height | Face | Use |
| --- | --- | --- | --- |
| `--t-axis` | 10.5 / 14 | Mono 400 | Axis ticks, units, lane labels |
| `--t-ui` | 12 / 16 | Mono 400 | Default UI text, rows, status line |
| `--t-meta` | 12 / 16 | Mono 500, `--fg-mid` | Block metadata row |
| `--t-read` | 14 / 22 | Sans 400 | Answer prose, vault notes |
| `--t-head` | 16 / 22 | Mono 500 | Screen name |
| `--t-figure` | 28 / 32 | Mono 400 | Inspector figures |
| `--t-hero` | 64 / 64 | Mono 300, −0.02 em | The claim figure on each screen (for example "0.07 s") |

- **Rules:**
  - Numbers are always tabular.
  - Units are in `--fg-lo`, with a thin space before them.
  - Sentence case everywhere. Uppercase is used only for lane labels: `RAM`, `SSD`, `VAULT`, `MODEL`.
  - No icon appears without a key hint or a label beside it.

## Motion

The rule is phosphor: an event lights instantly and decays exponentially, like a scope trace.

| Token | Value | Use |
| --- | --- | --- |
| `--attack` | 0 ms | Events appear at full brightness at once: they are sudden |
| `--decay` | τ = 600 ms | A flare fades to `mid` (`used` ticks, burst reads, remember events) |
| `--afterglow` | τ = 4 s | A trail fades to `lo` (a room that just left the desk, particles in transit) |
| `--ui` | 140 ms, `cubic-bezier(0.2, 0, 0, 1)` | Drawers, palette, row expansion. No springs, bounces or overshoot. |
| `--roll` | 60 s window | Instrument strips scroll right to left in roll mode, with now at the right edge |

- **Honest slow motion:** any real event shorter than 100 ms (for example an 18 ms SSD burst) replays at a fixed
  factor. The factor is printed in the corner of the canvas ("×1/20, real 18 ms"). Live view shows the real duration
  as a flash. The slowed motion plays only in replay or when he presses "slow".
- **Reduced motion:** decays become instant steps, particles become one static arrow, and strips stop rolling and
  redraw once a second.
- **Frame budget:** render on demand, up to 60 fps during events, 0 fps at rest, and fully paused in measuring mode.
  A small "measuring · UI paused" note replaces the canvas while a benchmark runs.

## The shell, shared by every screen

- **Window:** designed at 1512 × 982 (the 14-inch MacBook Pro default), minimum 1280 × 800. The title bar is hidden
  and the traffic lights sit over the rail.
- **Rail, left, 52 px, `--s1`:** six Lucide glyphs for Models, Chat, Code, Swarm, Memory and Bench, each with its
  ⌘-number underneath in `--t-axis`. The active one is `--fg`, the rest `--fg-lo`. Like Arc's sidebar it holds
  everything except the work, but it is slim and dim.
- **Status line, bottom, 24 px, `--s1`.** Segments are separated by `│`, and each starts with a 6 px dot in its colour:
  - `qwen3-1.7b-4bit · MLX`
  - `memory on · reach project`
  - `● RAM 1.8 / 24 GB` (ember)
  - `● SSD last read 57 MB in 18 ms` (blue)
  - `● vault 22,410 notes` (violet)
  - `first word 0.07 s`
- **The bus line:** the status line's top edge is a 1 px hairline. Whenever bytes move from the SSD to RAM, anywhere
  in the app, a short pulse runs along it from left to right, blue turning ember, with decay τ = 600 ms. It is the
  one signature element on every screen: memory moving can be felt from Chat, Code or Swarm without opening Memory.
- **⌘K palette:** Raycast-style, 640 px wide, centred, `--s2`, fuzzy search over:
  - actions;
  - models;
  - threads;
  - agents;
  - vault notes (results show their place colour as a dot);
  - settings.

  ↵ runs the item, ⌘↵ runs it in the background, and → opens a sub-action list.
- **Blocks:** every chat turn, agent step and tool call is a block, as in Warp. A block is one hairline-separated unit
  with a metadata row in `--t-meta`, shown on hover or focus:
  - time to the first word;
  - total time;
  - prefill and decode tok/s;
  - context tokens in view;
  - bytes read from the SSD.

  ⌘↑ and ⌘↓ jump between blocks, ⌘C copies one, and ⇧↵ re-runs it.

## Screens

### 1. Models: "the right model for this Mac"

**Signature visual: the Mac as two rails.** This is the top 45% of the screen.
- **The RAM rail:** one full-width rail of 24 cells, one per GB of unified memory (the cell count comes from the
  machine). Cells fill left to right:
  - macOS and other apps (`--none`, live from `vm_stat`);
  - the loaded model's weights (ember `mid`);
  - the engine's fixed allowance for the core and desk (ember outline);
  - free memory (empty `--line` outline).
- **The disk rail:** under it, a thinner rail for the disk:
  - model files (blue `mid`);
  - rooms and vault (blue `lo` with a 1 px hatch);
  - free space.
- **The chip line:** above the rails, in `--t-ui`: `Apple M5 Pro · 24 GB unified · SSD burst read <measured> GB/s`,
  with a "measure" action that runs the speed test from `ruler/` when the GPU is free.
- **The ghost:** hovering or arrowing onto any model in the list ghosts it onto both rails. Its weights appear as an
  ember outline after the current load, and its file as a blue outline on the disk rail. If it does not fit, the
  overflow runs past the right end of the rail as a hollow outline with a red ✗ and "won't run".
- **Loading:** "load" fills the ember cells one by one as real load progress arrives.

**The list:** the lower 55%, with LM Studio's density and Hugging Face's hardware-fit idea.
- **Search:** a search field (⌘F) queries Hugging Face for MLX and GGUF repositories.
- **Columns:**
  - name;
  - parameters;
  - quantisation;
  - runtime (MLX or Ollama);
  - **memory as:** tensors or words. This says whether the engine can lay notes or only pass text, as with the 27B,
    whose linear-attention layers keep no KV.
  - size on disk (blue figure);
  - RAM to run (ember figure);
  - verdict;
  - measured speed on this Mac (decode tok/s and time to the first word from a dated record, or "—").
- **Verdicts:** "fits", "slow" or "won't run", each as a glyph and a word, never as a colour.
- **Downloading:** ↵ on a row downloads it. The row's background fills blue from the left as bytes land, and a
  one-line MB/s trace runs at the row's right edge. When it finishes, the row gets a "load" key hint.

### 2. Chat: "keeps answering without filling its context"

**Layout:**
- **Centre column, 760 px:** blocks.
- **Composer:** pinned at the bottom, with a `›` prompt like a terminal.
- **"In view" drawer:** on the right, 360 px, closed by default, opened with ⌘I.

**The memory switch:** a hardware-style toggle at the composer's left, labelled `memory`.
- On, the composer's top edge carries the context meter (below).
- Off, the composer and every answer it produces are greyscale, and the answer's path shows only the model lane. The
  absence of colour is the message.

**The reach picker:** a four-way segmented control beside the switch: `session · project · agent · global`.
- Each reach is its own vault, so each segment shows that vault's size: a violet note count and a blue figure for
  bytes on the SSD.
- ⌥R cycles through the reaches. A memory pulled from a reach other than the chosen one is cross-talk, and is marked
  with a red ✗ on its path.

**The context meter:** a 2 px line across the composer's top edge.
- An ember segment shows context tokens in view, and a blue segment shows memory fetched for this turn.
- The `--line` remainder is the model's window.
- Text at the right reads `in view 2,148 / window 32,768 · fetched 57 MB · history 1.04M tokens` (example values).
- As the conversation grows, the history number climbs while the ember segment stays short. That is the claim, shown
  live.

**Signature visual: the answer's path.** A band sits above each answer block. It is 28 px tall at rest, and grows to
160 px on click or ⌘P. It is a Perfetto-style trace with lanes by place:

| Lane | Colour | Slices drawn there |
| --- | --- | --- |
| `VAULT` | violet | The 4 closest moments re-read as words: a thin slice, then a violet flow arrow into the model lane |
| `SSD` | blue | The burst read of one room. The slice's length is its duration; its thickness is GB/s. Labelled `57 MB · 18 ms`. |
| `RAM` | ember | Laying the desk, and the core, a constant thin ember bar the full width (always on, never fetched) |
| `MODEL` | white | Choosing (the embed and index look-up, drawn in whichever lane the engine reports for it), prefill, then a white tick per written word |

- **Axis:** shared, in ms from the question at 0, with a break after the first word so decode does not crush the
  start.
- **The first word:** a tall white tick labelled `0.07 s`.
- **Flow arrows:** Perfetto-style, they join the SSD read to the desk, to prefill, to the first word.
- **Hovering a written word** draws green threads from its tick back to the desk rows (the moments) it leaned on, at
  the watched layers 12, 16, 20 and 24. Moments that were picked up but not used get a white ring in the drawer.
  Threads exist only while hovered, so the band is never a hairball.
- **Collapsed state:** a chip with four proportional segments (blue read, ember desk, white prefill, white decode)
  and the first-word time. In a long chat this column of chips becomes a strip of how each answer was made.
- **Memory off or Claude:** the path is one grey model lane.

**The "In view" drawer:** the desk for the selected answer, in the loved trace-strip form.
- One labelled row per moment on the desk (`m01`–`m24`), each with its words in `--t-ui`.
- A green tick in each row at every written word that leaned on it.
- Picked-up rows get a white outline; the selected row turns white (as in suite2p).

### 3. Code: "a local model can do real work with memory"

**Layout:** three columns, like Zed and Conductor.
- **Left, 240 px:**
  - threads at the top, grouped by project; each thread row ends with its last answer's path chip;
  - the file tree below.
- **Centre, flexible:** the agent's transcript as blocks, Claude Code style.
  - The plan and todo list is pinned at the top: monochrome checkboxes, with the current step in `--fg` and the rest
    in `--fg-mid`.
  - Each tool call is one dim line, for example `⏺ read_file  camr_engine/rooms.py  2 ms` or
    `⏺ recall  "fee rule"  room r-0041  18 ms`. File reads are `--none`; memory recalls carry their place colour.
  - Edits show as unified diffs (CodeMirror merge view), with accept or reject per hunk.
  - A change summary sits above the composer: "3 files, +41 −7, review", as in Zed.
- **Right, 560 px:** tabs for Editor (CodeMirror 6), Terminal (xterm.js, WebGL renderer) and Diff.

**The loadout:** a drawer opened with ⌘L, full height, 420 px. It is a rack of 1U strips in four sections:
- MCP servers;
- plugins;
- skills;
- personas and system prompt.

Each strip shows:
- the item's name and its source (a path or a command), and its tool count;
- a status light: `--fg-lo` when off, white when on, and a brief white flash on each call;
- a tick trace of this session's calls along its right half.

Status here uses brightness, not colour, because colour is reserved for memory. A failed call is a red ✗ on its tick.
Choosing a persona sets the system prompt and switches the reach to that agent's vault.

**Signature visual: the memory gutter.** A 3 px column sits between the editor's line numbers and the code.
- A green tick marks each line the agent wrote while leaning on memory at the watched layers.
- Hovering the tick opens a small popover: the moment's words (for example "fee rule: 1% rounded up to the next 5
  shillings, at least 10, a flat 25 on exact multiples of 1,000"), the day it was told, its room, and the path chip of
  that step.
- This is where "Code that must fit" becomes visible: helper names, units and quirks traced back to the day they were
  said.

### 4. Swarm: "memory saves context for many agents at once"

**Signature visual: the lanes.** The top 60% of the screen holds the loved stacked traces with labelled rows.
- **Rows:** one per agent, `A1`–`A8`, each 56 px tall, on one shared clock with now at the right.
- **Row header, left, 200 px:**
  - the label, persona and model;
  - the current task in one line;
  - the agent's own vault size (a violet count and a blue byte figure).
- **Row body:**
  - white ticks for written tokens (their density shows speed);
  - blue bursts where it reads its rooms from the SSD;
  - an ember bar where its room sits on the desk;
  - green ticks where it used memory;
  - a white ◆ at each task done.
- **Selecting a row** turns it white and dims the others to 40% (as in suite2p). The bottom 40% then opens that
  agent's transcript, in the Code screen's blocks.

**The shared desk:** above the lanes, one full-width ember bar is the RAM allowance, sliced over time.
- While an agent's room is on the desk, it holds a labelled segment (`A3`).
- Watching it shows the conscious swapping between agents: rooms arriving in blue, sitting in ember, leaving with an
  afterglow.
- When the allowance is full, the next arrival waits. Its blue burst sits on the SSD lane until a segment frees, which
  makes contention visible.

**Hand-offs** between agents are thin white flow arrows from one lane to another at the moment of hand-off.

**The comparison strip:** at the bottom of the lanes area, three small multiples per agent:
- tokens used;
- tasks done;
- time.

Each shows memory on in its place colour beside memory off in `--none`, when both runs exist.

### 5. Memory: "inspect it when it goes wrong, or admire it"

This is the hero screen. Three modes are switched with `1` `2` `3`: **Live**, **Vault** and **Growth**.

#### Live: the cross-section

**Canvas:** the top 64%, WebGL, true black.
- The camera is orthographic with a slight 12° tilt, so the strata read as a cut-away, like a translucent shell with
  lit parts inside.
- Each stratum sits inside a 1 px `--line` outline. Only active parts glow.

**The RAM chamber:** the top 22% of the canvas. Left to right:
- **The weights slab:** the loaded model's weights, ember `lo`, labelled `weights 1.0 GB`. It is drawn to scale, so
  the desk's small size is honest beside it.
- **The core:** a solid ember block that never pulses, labelled with its memory-token count and bytes. It is always
  there: the subconscious.
- **The desk:** an ember outline, empty at rest.
- **The allowance:** a dashed white line at 30% opacity across the chamber's top. The desk can never cross it.

**The SSD field:** the bottom 64%, split by a vertical hairline into two parts.
- **Tensors, left 82%:** every room is a tile drawn as a tensor.
  - A tile is a grid of cells: 28 rows (one per layer of Qwen3-1.7B) by up to 512 columns (one per token), shown
    downsampled to 64 columns at overview zoom and at full resolution when zoomed.
  - Each moment's span of columns is outlined, so a tile reads as "thousands of dots inside area borders".
  - At rest a tile is a blue `lo` outline with `lo` dots.
  - Tiles flow in append order, left to right then top to bottom like a tape, so the newest is always at the end.
  - Writing a new room is a remember event: a brief blue flare on that tile.
- **Words, right 18%:** the vault, a tall column of violet `lo` lines. Each line is one note, with its length set by
  the note's length, like a code minimap. It scrolls as the vault grows.

**The bus:** the black gap between the chambers, 14% of the canvas, empty at rest.

**One answer, live,** with every step timed from its own event record:
1. **Choose:** a faint white scan line sweeps the tiles and stops on the chosen room, which lifts from `lo` to blue
   `full`.
2. **Burst read:** a column of particles rises from the tile to the desk. There is one particle per 256 KB, so a full
   room (512 tokens × 112 KB ≈ 57 MB) is about 220 particles. The column is as wide as the measured GB/s. Particles
   shift from blue to ember on the way (`--transit`). A label at the column reads `57 MB · 3.2 GB/s · 18 ms` (example
   values, read from the record).
3. **Lay the desk:** the tile appears in the desk as ember `mid` cells, 28 × 512 at full resolution. This is the
   tensor the model actually reads, shown as a tensor.
4. **Words in:** violet threads run from the 4 closest moments' vault lines into the model as words.
5. **Writing:** as each word is written, the cells of the moments it leaned on flare green, but only on rows 12, 16,
   20 and 24, the watched layers. The picture never claims more than is measured. Moments that were picked up but
   never used get a white ring.
6. **Leaving:** when the desk is cleared, the ember tile fades with a 4 s afterglow. Its SSD tile pulses once to show
   it is still there. Leaving RAM writes nothing, so nothing travels down.
7. **Doors:** when a door between rooms fires (related rooms coming in together), a hairline arc joins the two tiles.
   Its thickness is the door's strength. Arcs exist only while they fire.

**Instrument strips:** the bottom 36% of the screen. Rows are labelled at the left, share one time axis, and scroll in
roll mode over 60 s:

| Row | Trace | Colour |
| --- | --- | --- |
| `SSD` | Read rate in GB/s, filled at 20% under the line | blue |
| `RAM` | GB used, with the allowance as a dashed white line | ember |
| `CONTEXT` | Tokens in view (ember) against the history's total tokens (`--none`, log scale) | ember / grey |
| `USED` | Raster: one row per moment on the desk, a tick per word at share ≥ 0.10 | green |
| `WORDS` | A white tick per written token, with a tall tick at the first word | white |

**Controls:**
- space freezes the view;
- `,` and `.` step one event back or forward;
- `s` toggles honest slow motion;
- `r` replays any past answer, picked from a list in the drawer.

**Inspector drawer:** on the right, 320 px, opened by clicking a tile.
- The room's id, the day it was made, its token count and bytes.
- When it was last opened, and how many times.
- Its doors, with their strengths.
- Its moments as words, from the vault, and "open in vault".

#### Vault: the human side

**Signature visual: an Obsidian-like graph** in WebGL (sigma), the full canvas.
- **Notes** are violet dots, sized by times used.
- **Links** are hairlines, thicker for stronger doors (the loved FlyWire area-graph style).
- **Rooms:** a note whose tensors are saved in a room carries a small blue core dot.
- **On the desk now:** a note gets an ember ring.
- **Used in the last answer:** a note flares green.
- **Opening a note:** clicking one opens it in a right pane as Markdown in Geist Sans, with backlinks below.
- **Local graph:** a depth slider (1–3) shows only the notes near the selected one.
- **Fading:** a note faded by sleep (5% a day unless used) is dimmer but never gone, because nothing is destroyed.

#### Growth: how it grows

**Signature visual: a time-lapse over days,** like Obsidian's "animate" but driven by real dated records.
- The SSD field fills tile by tile.
- The core steps up in ember at each sleep.
- Tiles dim with fading and relight when used.

**Strips under it:**
- bytes on disk (blue, rising);
- core size (ember, stepping);
- vault notes (violet, rising);
- time to the first word (white, flat).

Together they are "better, never heavier" in one picture: growth on top, flat weight below.

### 6. Bench: "the evidence, live"

**Layout:**
- **Tabs:** one per question in the plan.
  - Past the window?
  - How far can it grow?
  - Which reach?
  - Do swarms gain?
  - Does sleep keep what matters?
- **Hero chart:** each tab is one full-width chart in the top 60%.
- **Below the chart:**
  - a dense run table in mono;
  - each row's dated record path, opened with ↵.

**The hero charts:**
- **Past the window:**
  - The x-axis is history length on a log scale, with cuts at 64K, 256K, 1M and 2M. The y-axis is % right on the Long
    Haul probes.
  - Lines show a model with tensor memory (ember), with words memory (violet), with memory off (`--none`), and Claude
    alone (`--none`, dashed, with input, cached and output tokens and $ at each point).
  - A white dashed vertical line marks where each model's context window ends. The memory lines keep going past it.
- **How far can it grow:** two stacked panels share the x-axis, from 1,000 to 1,000,000 memories.
  - The top panel shows right answers.
  - The bottom panel shows time to the first word (white) and peak RAM (ember), both meant to stay flat, with disk
    (blue) rising.
- **Which reach:** four small multiples (session, project, agent, global). Each shows help (green, right answers that
  used memory) against cross-talk (red ✗ count).
- **Do swarms gain:** tokens, tasks done and time per agent count, with memory on and off.
- **Does sleep keep:** quiz score before and after distilling, beside memory size (blue bytes shrinking).

**Probe matrix:** on the first tab, a grid of the 8 Long Haul probes (rows) by contenders (columns).
- Each cell is a square whose brightness is the score, in the contender's memory hue, or grey for no memory.
- Each cell also shows counts: ✓ right, ✗ wrong in red, ∅ honest declines in white.
- On "Never said", a guess is a false memory and shows as ✗.

**While a suite runs:**
- each new result lands as a dot that flares and decays;
- the canvas render loop elsewhere is paused;
- the status line reads `measuring`.

## Libraries

Everything is copied into `v2/camr_engine/app/static/vendor/` and served by the local server, so the app runs with no
network.
- **No CDN at runtime.** A `vendor/LOCK.json` lists each file with its package, version, licence and SHA-256.
- **No build step,** except one esbuild run that turns CodeMirror into a single ES module file.
- **How the versions were picked:** each is the newest release at least three weeks old on 4 Nov 2026, checked
  against the npm registry that day. Peer ranges were checked too.

| Purpose | Package and exact version | Licence | Why this one |
| --- | --- | --- | --- |
| Components | `preact@10.29.8`, `htm@3.1.1` | MIT, Apache-2.0 | Components as plain ES modules with no compiler. Mature 10.x rather than the five-week-old 11.0. |
| State | `@preact/signals@2.11.3` (with `@preact/signals-core@1.14.4`) | MIT | Fine-grained updates, so a 60 fps strip never re-renders the page |
| Cross-section and particles | `three@0.186.1` | MIT | InstancedMesh draws hundreds of thousands of cells; Points for particles; OrthographicCamera |
| Selective bloom | `postprocessing@6.39.5` | Zlib | `SelectiveBloomEffect`: only event meshes glow. It requires three `>=0.168 <0.187`, which is why three stays at 0.186.1. |
| Instrument strips | `uplot@1.6.32` | MIT | Canvas time series that roll 10⁵ points at 60 fps in about 50 KB |
| Path band and Bench charts | `d3-scale@4.0.2`, `d3-shape@3.2.0`, `d3-array@3.2.4` | ISC | Scales and shapes only; drawn by our own code to canvas or SVG |
| Vault graph | `sigma@4.0.1`, `graphology@0.26.0`, `graphology-layout-forceatlas2@0.10.1` | MIT | WebGL graph for tens of thousands of notes; the layout runs in a worker |
| Editor and diffs | `codemirror@6.0.2`, `@codemirror/view@6.43.14`, `@codemirror/state@6.7.6`, `@codemirror/language@6.13.1`, `@codemirror/lang-python@6.2.1`, `@codemirror/merge@6.12.2` | MIT | Light, themeable; its highlighter also colours read-only code blocks, so no second highlighter is needed |
| Vendoring tool, not shipped | `esbuild@0.28.2` | MIT | Bundles CodeMirror once into `vendor/codemirror.js` |
| Terminal | `@xterm/xterm@6.0.0`, `@xterm/addon-fit@0.11.0`, `@xterm/addon-webgl@0.19.0` | MIT | The terminal VS Code uses, with a GPU renderer |
| Markdown | `markdown-it@14.3.2`, with `html: false` | MIT | Vault notes and answers, with no raw HTML from model output |
| Palette search | `fuzzysort@4.0.2` | MIT | Fast fuzzy match for ⌘K |
| Icons | `lucide-static@1.56.0`, copying only the SVGs used | ISC | Plain line glyphs that stay monochrome |
| Fonts | `@fontsource/geist-mono@5.3.0`, `@fontsource/geist-sans@5.3.0`, woff2 only | OFL-1.1 | See Type |
| Animation | none: Web Animations API and `requestAnimationFrame` | — | Phosphor decay is one exponential, and a library would add nothing |

## What makes it unlike anything else

1. **No brand colour.** Ollama, LM Studio, Cursor and Warp each have an accent colour. This app has none. Its only
   colours are where memory lives, so from across a room it shows whether an answer used memory.
2. **The answer's path.** No chat app shows where an answer came from in bytes and milliseconds. Here every answer
   carries a band showing what was read from the SSD, what sat in RAM, which words leaned on which moments, and the
   first-word time.
3. **Tensors drawn as tensors.** Memory appears as layers × tokens grids that lift from the SSD into RAM, not as a
   vector-database scatter or abstract dots. It shows in one picture that this is not a vector database.
4. **The bus line.** A hairline on every screen pulses whenever memory moves, so the engine is felt from anywhere in
   the app.
5. **Phosphor honesty.** Every glow is a logged event, fast events replay at a printed slow-motion factor, and
   unmeasured values show "—". The visuals are evidence, not illustration.
6. **The yardstick in grey.** Claude and memory-off runs are drawn without colour throughout. The comparison is built
   into the palette.
7. **It gets out of the way of its own measurements.** The UI renders nothing at rest and pauses while a benchmark
   measures. Few showcase apps consider that the UI itself can skew the numbers.

## References

These were researched on 4 Nov 2026. Most pages were read as text, so I took behaviour and structure from them, not
pixels.

| Reference | URL | What I took |
| --- | --- | --- |
| Warp, modern terminal | https://www.warp.dev/modern-terminal | Blocks (a command, its output and metadata as one unit), ⌘↑/⌘↓ between blocks, an editor-grade prompt, a keyboard-first palette |
| Zed, agentic editing | https://zed.dev/agentic | Following the agent live, and reviewing its edits as an editable unified diff |
| Zed, agent panel docs | https://zed.dev/docs/ai/agent-panel | The change summary above the input, per-hunk accept or reject, the token counter beside the input, the threads sidebar grouped by project |
| Zed, threads sidebar (Apr 2026) | https://alternativeto.net/news/2026/4/zed-launches-parallel-agent-orchestration-with-a-threads-sidebar-to-control-and-monitor-them/ | Parallel threads on the left; project and Git panels on the right |
| Cursor 2.0 agent layout | https://www.codecademy.com/article/cursor-2-0-new-ai-model-explained | An agents-first sidebar showing which agents are running, done or waiting |
| Cursor 2.0 review | https://inkeep.com/blog/cursor-2-review | Agents as the unit of work rather than files |
| Conductor | https://www.conductor.build | Parallel coding agents, each in its own workspace with its own chat, terminal and diff (the Swarm lanes and Code columns) |
| Claude Code status line | https://code.claude.com/docs/en/statusline | A persistent bottom line for model, context and cost, which became the status line and bus line |
| Raycast | https://www.raycast.com/ | The keyboard-first launcher, an action list behind every row, and an agent thread with step status lines |
| Ollama's new app | https://ollama.com/blog/new-app | The chat-first app with a model picker, where the settings mention that context length costs memory |
| LM Studio, downloading a model | https://lmstudio.ai/docs/app/basics/download-model | Search by keyword, `user/model` or a Hugging Face URL; choosing a quantisation |
| LM Studio explained (third-party) | https://www.layer3labs.io/guides/lm-studio-explained | The pre-download "likely fit" check against RAM |
| Hugging Face hardware compatibility | https://huggingface.co/docs/hub/hardware | A per-quantisation estimate of whether a file will run on your saved hardware (MLX and GGUF) |
| Arc browser | https://en.wikipedia.org/wiki/Arc_(web_browser) | A sidebar holding everything but the work |
| Arc design study | https://blakecrosley.com/blog/design-study-arc | Organising by context rather than recency |
| Linear, design refresh | https://linear.app/now/behind-the-latest-design-refresh | Not every element gets equal weight; navigation recedes; fewer borders |
| Linear, 2024 UI | https://linear.app/changelog/2024-03-20-new-linear-ui | Less visual noise in headers, filters and panels |
| Perfetto UI | https://perfetto.dev/docs/visualization/perfetto-ui | Tracks and slices on a shared time axis, the selection drawer, keyboard stepping (`,` `.`), which became the answer's path |
| Obsidian graph view | https://obsidian.md/help/plugins/graph | Groups coloured by query, link thickness, the local graph depth slider, the time-lapse "animate" |
| Open Ephys LFP viewer | https://open-ephys.github.io/gui-docs/User-Manual/Plugins/LFP-Viewer.html | Stacked continuous traces on black with labelled channels (one of his loved picks) |
| btop | https://github.com/aristocratos/btop | Dense, calm, terminal-native resource graphs |
| LLM Visualization (Bycroft) | https://bbycroft.net/llm | A model's tensors drawn as 3D grids of cells; the source of "tensors drawn as tensors" |
| llm-viz source | https://github.com/bbycroft/llm-viz | The same project's code |
| Transformer Explainer | https://poloclub.github.io/transformer-explainer/ | A live model's internals shown while it runs |
| Artificial Analysis leaderboard | https://artificialanalysis.ai/leaderboards/models | Score against speed, and time to the first token as a first-class metric (the Bench hero charts) |
| Digital phosphor oscilloscope | https://www.controleng.com/digital-phosphor-oscilloscope-combines-analog-digital-strengths | Intensity grading and persistence, which became the phosphor motion rule |
| Tektronix persistence-decay patent | https://patents.google.com/patent/US6333732 | Decaying each lit pixel's intensity over time |
| His board: brain view 2 | https://claude.ai/artifact/1TnhhUGodwsLuEKXqrTyt8 | His loved picks: Open Ephys traces, Allen tick per event, labelled rows A1–A8, suite2p's selected-turns-white, green over red, only active groups glowing in thin outlines, a translucent body lit inside |
| His board: directions round 1 | https://claude.ai/artifact/5VUmJC5P4QTAaQm9Axx4XV | What failed: sparse, flat views (tiny dots, thin lines on empty black). This is why the cross-section is full-bleed, tensor-dense and bloomed. |

`~/Desktop/inspiration-bank` was not found on this Mac (nor anywhere under the home folder), so nothing was taken
from it.

## Taste questions for Ibrahim

1. **RAM's colour:** ember (orange) keeps his loved green-on-red look. A yellower amber separates better from "wrong"
   red. Which does he prefer?
2. **Fonts:** Geist Mono everywhere, or stay with IBM Plex, as the current app and thesis figures use?
3. **The Memory canvas:** a flat 2D cross-section, or the slight 12° tilt as a cut-away?
