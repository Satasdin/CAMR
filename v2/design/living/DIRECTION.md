# Living: memory as an organism that grows

This is one of the three directions on the table (4 Nov 2026). Its lens is a living system.

There are no mockups in this folder, on purpose. Every screen is described exactly enough to build and to judge on
the engine's real data. The first real render, using his own memory, is the mockup.

## The idea in two sentences

The memory is drawn as one living organism glowing on black:
- a **nucleus** (the core, always lit in RAM);
- a **mycelium of rooms** resting on the SSD;
- a fine **root-mat of vault notes** below them.

It buds each time something is remembered, and the doors it really walks through thicken the way slime-mould tubes
widen with flow. Every light on screen is a real engine event, coloured by where that piece of memory lives at that
moment. So you watch the model think: tensors climb from the SSD into RAM, the words that use them flare white, and
the paths nobody uses slowly thin.

## What it takes from his picks

| He loved (boards 1 and 2) | Where it shows up here |
| --- | --- |
| Glowing structure on black; one green layer; a single neuron close up | The organism itself; the close-up view of a tensor (Memory screen) |
| Green over red (two-channel) | RAM is green and SSD is red, like activity over structure under a microscope |
| Selected cells turn white (suite2p) | White means "used in this answer" and nothing else |
| Only active groups glow inside thin outlines; thousands of dots inside area borders | Rooms are outlined areas with their moments as dots inside; only live ones glow |
| Translucent brain lit inside | The three stores are stacked glass planes, lit from inside |
| Stacked traces on black; a tick per event; labelled rows A1–A8 | The instrument strip under every big view |
| Regions colour-matched to their traces | Each trace row's label takes its node's store colour |
| A glow sweeping through an outlined body | An answer's thread sweeping through the planes |
| FlyWire area graph: line thickness is connection strength | Door thickness is how often a door was walked |

| He rejected | How this direction avoids it |
| --- | --- |
| Murky, blurry footage | Bloom is tight and selective. There is no fog, depth-of-field blur or gradient wash. |
| Dense, cluttered tissue | Structure is drawn as hairlines at 6–18% brightness. Only events are bright. |
| Random colour per item (Brainbow) | Five meaningful hues in the whole app |
| Round-1 directions, "sparse and flat" (tiny dots, thin lines on empty black) | The organism is dense and dim with sparse bright lights, in layered 3D planes that fill 60–100% of the screen |

**Inspiration bank:** `~/Desktop/inspiration-bank` was not on disk tonight. A search of `~` to depth 3 found nothing
either. These picks come from his two board notes and their sources instead (`~/Developer/engram/work/board-step2/`).

## Principles

1. **Every light is a real event.** Nothing glows, moves or pulses unless the engine did something: an event in
   `events.jsonl`, a swap, or a metric tick.
   - When idle, the screen is completely still. Stillness *means* idle.
   - There are no ambient particles, breathing loops or drifting cameras.
2. **Hue is where it lives. Form is what it is. Brightness is how recently it was touched.**
   - Hue: RAM, SSD or vault.
   - Form: core, room, moment, note, door.
   - White is used in this answer. Amber is a false memory. No other hue exists.
3. **Picked up is not used.**
   - A room read onto the desk becomes a green *ring*.
   - Only a node that drew at least 10% of the desk's attention (`events.USED`) gets a white-hot *core*.
   - The gap between ring and core is the honest story.
4. **Use thickens and disuse thins, but nothing dies.** Door width follows the slime-mould rule (Tero et al. 2010):
   - walking a door widens it;
   - sleep thins it by 5% a day;
   - it never drops below a 0.5 px hairline, because sleep never destroys.
5. **Height is distance from attention.** RAM sits on top, the SSD rooms in the middle and the vault at the bottom.
   Going up means faster and closer to the model; going down means bigger, colder and slower. A swap is literally
   vertical motion.
6. **One big picture per screen, with instruments under it.** The picture takes at least 60% of the viewport.
   Numbers live in a thin strip of stacked traces and tick rows, never in walls of text.
7. **Sizes are measured, never styled.**
   - A room's area is proportional to its bytes on the SSD.
   - A streak's width follows the bytes it carries.
   - A segment's label is its measured milliseconds.
   - When motion is slowed so an eye can follow it, the screen says by how much.
8. **Crisp, not murky.** Lines are thin and bright, with a small bloom on lit things only. The background is pure
   black, which suits the XDR screen of the M5 Pro.
9. **Never hue alone.** Every colour meaning is backed up by position (which plane), form (filled or hollow) or a
   label. Colour-blind users lose nothing.

## Colour tokens

Base:

| Token | Hex | Means | Rule |
| --- | --- | --- | --- |
| `--void` | `#000000` | The page: nothing is here | All backgrounds, including behind the 3D view |
| `--deep` | `#06080B` | A surface you type into | Chat input, editor, terminal only |
| `--hair` | `#161C22` | A boundary | Plane outlines, dividers, the reach shell. 1 px. |
| `--dim` | `#76818D` | Secondary words (5.3:1 on black) | Captions, resting labels, axis ticks |
| `--text` | `#D9E1E8` | Words (15.9:1 on black) | Body text. Deliberately not white. |

Meaning (each hue has exactly one job):

| Token | Hex | Means | Where | Never |
| --- | --- | --- | --- | --- |
| `--ram` | `#3DF58A` | **Lives in RAM now**: the core, and whatever is on the desk | All screens | Never "success" or "online" |
| `--ssd` | `#FF4F7B` | **Rests on the SSD**: saved KV rooms that are not being read | All screens | Never "error" |
| `--vault` | `#4C8DFF` | **The archive**: plain-text notes, their doors, the user's saved fixes | All screens | Never "link" or "info" |
| `--used` | `#FFFFFF` | **Used in this answer**: attention share ≥ 0.10 | The thread, flares, ticks, gutter marks | Never for text, buttons or "selected" |
| `--alarm` | `#FFB020` | **Said something false**: a false memory or stale value | Bench, answer receipts | Never decoration or warnings in general |
| `--yard` | `#8A94A0` | **A yardstick, not memory**: Claude alone, memory off | Bench, dashed only | Never glows |

Each store hue has three brightness steps. Brightness carries recency, never a new meaning.

| Step | RAM | SSD | Vault | Use |
| --- | --- | --- | --- | --- |
| 1, rest | `#0C3B22` | `#3D1020` | `#0E2045` | Structure: outlines and dots nobody touched recently |
| 2, touched | `#1F9E57` | `#A8304F` | `#2F5BB0` | Touched in the last hour, or in reach |
| 3, live | `#3DF58A` | `#FF4F7B` | `#4C8DFF` | Happening now. Only step 3 and white are bloomed. |

**In flight, colour is location.** A tensor rising from the SSD to RAM starts as `--ssd` and ends as `--ram`,
interpolated by height. A note read as words rises from `--vault` to `--ram`. A fact sleep distils into the core goes
from `--ssd` to `--ram`. The colour changes because where it lives changes.

**A copy and its home.** A room on the desk is a green copy. Its home on the SSD stays red, at step 2, joined to the
copy by the hairline it rose along. Reads are copies (rooms are append-only), so nothing ever "moves away" from the
SSD.

**Colour-blind check** (simulated with Machado 2009):
- With deuteranopia, `--ram` and `--ssd` keep a large brightness gap (0.68 against 0.28) and sit on different planes.
- Amber and RAM green look alike to deutans, so amber always comes with its own glyph (a filled triangle) and only
  appears where green does not (Bench and receipts).
- This is also why `--ssd` leans rose rather than pure red. Microscopy moved from red/green to green/magenta for the
  same reason.

## Form vocabulary

Every shape is one kind of thing. Hue never changes its form.

| Thing | Form | Size from | Rest | Live |
| --- | --- | --- | --- | --- |
| Core (subconscious) | A tight nucleus of dots (one per memory token), with a soft rim | radius ∝ √(core bytes) | Always step 3 green, steady | Its rim flares per written word, scaled by the core's attention share |
| Room (conscious) | An outlined area (SDF blob, 1 px rim) holding its moments as 1.5 px dots | area ∝ bytes on the SSD | Rim and dots at step 1 red | Read: rim to step 3 for 400 ms. On the desk: green ring above it. |
| Moment | A 1.5 px dot inside its room | fixed | step 1 | Used: a white core 3 px across |
| Vault note | A small spore: a 2 px dot with a 6 px halo at 10% | fixed; halo grows with incoming doors, as in Obsidian | step 1 blue | Opened or read: step 3 |
| Door | A curved filament (quadratic Bézier ribbon) | width = 0.6 + 1.4·log2(1 + walks) px, max 4 px, × weight, floor 0.5 px | 18% alpha, colour of the plane it lies in | Walked now: a white pulse runs along it at 1.5 px/ms |
| Streak (swap) | An elongated capsule rising vertically | width = 1 + 1.5·log10(bytes / 1 KB) px; length ∝ GB/s (stretches when fast, contracts on landing) | — | Store colour by height |
| Question | A white point on the RAM plane, at the question's place in the shared layout | 4 px | — | Lit while answering |
| Pen | Where words are written: the front-centre edge of the RAM plane | 6 px white bar | — | Ticks once per written word |
| Thread | An answer's data path: a single 1.25 px white line, bloomed | — | Fades over 8 s to its thickened doors | See the data path section |

## Type

- **Geist Variable** (OFL-1.1) for interface and reading text. It is neutral and crisp at 13–15 px, with tabular
  figures.
- **Martian Mono Variable** (OFL-1.1) for instruments, numbers, labels on the organism, code and the terminal. Its
  width axis (75–112.5%) lets trace labels run condensed at `font-stretch: 80%`. Code runs at 87.5% to fit 100
  columns. It looks engineered without being a gimmick.

| Role | Face | Size / line | Weight | Notes |
| --- | --- | --- | --- | --- |
| Hero number (one per screen at most) | Geist | 64 / 64 | 300 | `-0.02em`; for example "0.07 s" or "62 / 85" |
| Screen title | Geist | 28 / 32 | 500 | Only on Models and Bench. The others are titled by their picture. |
| Body | Geist | 15 / 24 | 400 | Chat and notes; max 68 characters per line |
| Caption | Geist | 12 / 16 | 400 | `--dim` |
| Instrument | Martian Mono | 11 / 14 | 400 | `font-stretch: 80%`, `font-variant-numeric: tabular-nums`, uppercase row labels (R12, A3, CORE) |
| Code | Martian Mono | 13 / 20 | 400 | `font-stretch: 87.5%` |

Labels on the 3D view are HTML overlays placed by projection. They stay crisp, selectable and readable by a screen
reader. At most 12 show at once: the ones that matter now.

## Motion

Motion runs on the **event clock**. A frame is drawn only while something is happening. Each event maps to one motion:

| Engine event | Motion | Duration |
| --- | --- | --- |
| `remember`, moment joins a room | A dot buds from the room's rim and settles inside; the rim swells by the new bytes | 600 ms, ease-out |
| `remember`, new room | A hypha grows from the nearest room and a new outlined area opens at its tip | 900 ms grow, then 1.2 s of layout relax |
| `choose` | The question point appears; a white hairline drops straight down to the chosen room, which flashes its rim | 240 ms |
| SSD read (burst) | A streak rises from the room to the RAM plane | measured read time, stretched to at least 240 ms (see below) |
| Desk laid | The copy settles as a green ring; the desk meter fills by its tokens | 200 ms |
| Each written word | The used nodes' cores light at brightness = that word's attention share and decay; one white tick lands in the strip | 180 ms decay per word |
| Desk cleared | The green rings dissolve (RAM freed) and the walked doors thicken | 400 ms |
| Sleep, distil to core | Thin red streaks rise into the nucleus, which grows | replayed at 1 day per second |
| Sleep, fade | Doors thin by 0.95 per day | the same replay |
| Sleep, archive | Green or red drips fall into the vault plane as blue notes | the same replay |

- **Time honesty.** A full room's burst read takes about 18 ms (57 MB at 3.1 GB/s), which no eye can follow.
  - When an animation is stretched, a mono chip by the streak reads `18 ms · shown ×13`.
  - The instrument strip underneath always runs in real time.
- **Elongation**, after the Gemini particle rule: things stretch while they travel and contract as they settle. Here
  the stretch is the measured GB/s, so speed is readable at a glance.
- **The camera** moves only for user input, or once per answer: an 800 ms dolly that frames the thread. There is no
  scroll parallax.
- **`prefers-reduced-motion`:** there are no travel animations; state changes snap, and flares become a single 100 ms
  step. The strip's ticks stay, because they are the data.

## Rendering rules

- **Renderer:**
  - three.js WebGL2, `NoToneMapping` with sRGB output, so the six hues stay exact (ACES would wash them out);
  - an orthographic camera pitched 24°: sizes stay honest within a plane, but the planes still read as stacked glass.
- **Glow:** `SelectiveBloomEffect` from pmndrs `postprocessing`.
  - Only step-3 store colours, white and streaks in flight join the selection. Structure is never bloomed.
  - Settings: `luminanceThreshold 0.55`, `intensity 1.3`, `radius 0.35`, `mipmapBlur true`, `resolutionScale 0.5`.
- **Blending:** lit things use additive blending, so overlaps get brighter, which gives the loved "lit inside" depth.
  Structure uses normal blending at low alpha.
- **Instancing:**
  - pods, dots and spores are `InstancedMesh`;
  - doors are instanced ribbon quads with a per-instance width attribute and a 12-segment Bézier in the vertex
    shader;
  - the budget is 60,000 dots and 20,000 doors at 60 fps.
- **The GPU is shared with MLX.** The model generates on the same chip, so:
  - render on demand (no `requestAnimationFrame` loop while idle);
  - cap at 60 fps while animating;
  - run bloom at half resolution;
  - the lead measures the view's cost on tok/s and keeps it under 2%. The attention watcher costs 0.6%; the picture
    must not cost more than the thing it shows.
- **Layout comes from the engine.** All three planes share one semantic layout, so a room, the notes it was archived
  to, and its copy on the desk sit in one vertical column:
  - `view/layout.py` already gives t-SNE positions; x and z on each plane;
  - `d3-force-3d` only relaxes new buds into place.

## The shell (every screen)

- **The rail:** 56 px wide on the left, `--void`, holding six 20 px Lucide glyphs:
  - Models (`cpu`), Chat (`message-circle`), Code (`square-terminal`), Swarm (`share-2`), Memory (`brain`), Bench
    (`gauge`);
  - the active glyph is `--text` with a 2 px `--text` bar at the rail edge, and the rest are `--dim`.
  - There is no logo wordmark until he picks the name. A 6 px green dot (the core) sits at the top of the rail and
    stays lit while a model is loaded.
- **The vital line:**
  - a 2 px trace across the very top of every screen, full width;
  - a green line for RAM in use (height scaled to 24 GB), with red ticks for SSD bursts and white ticks for written
    words;
  - flat and dark when idle. It is the app's heartbeat, and it is real.
- There is no top bar, no breadcrumb and no footer.

## Screens

### Models: what fits this Mac

**Layout (1440 px wide as the reference):**
- top 38%: the fit gauge;
- below: a 3-column grid of model tiles;
- right: a 380 px Hugging Face search drawer that slides over the grid, not the gauge.

**Signature, the fit gauge.** The Mac's 24 GB of unified memory is drawn as one long glass bar, 1 px `--hair` rim,
spanning the content width at 96 px tall.
- macOS and other apps fill from the left in `--dim` at 20%, with the measured number.
- The loaded model fills in solid `--ram`, then its desk and core.
- Hovering a model tile projects its footprint as a green outline: weights at 4-bit, plus KV for the chosen context,
  plus the desk.
- If the footprint overruns the bar's right end, the overrun is drawn past the end in `--ssd` and labelled "would
  page to SSD". Red here means SSD, exactly as everywhere else.
- Hero number above the bar: free RAM, for example "17.8 GB free".

**Model tiles (each 1:1.1).** Each tile is a picture of the model's real anatomy, read from its `config.json`:
- one thin horizontal plate per layer, stacked bottom to top;
- plate width ∝ hidden size, so a 27B is visibly wider and taller than a 1.7B;
- **filled** plates are attention layers that keep KV, so they can read tensor memory;
- **hollow** plates are linear-attention layers with no KV to save, which is why the 27B gets memory as words.

So a tile shows at a glance *how* this model can use memory.

Under the plates, in mono:
- disk size;
- RAM at load;
- measured TTFT and tok/s, with a 40 px sparkline if measured on this Mac and nothing if not;
- one verdict: fits / tight / won't fit.

**Download and load:**
- Downloading fills the plates from the bottom in `--ssd`, with bytes/s beside them, because the weights are landing
  on the SSD.
- Loading turns them `--ram`, shard by shard if the loader reports shards. If not, they all turn at once. There is
  never a fake progress animation.

### Chat: a memory switch and a reach picker

**Layout:**
- left 46%: the conversation, a 680 px centred column;
- right 54%: **the lens**, the same organism as the Memory screen seen from the same angle and cropped to the reach;
- under 1100 px wide, the lens folds into a 180 px band above the input.

**The input bar** (bottom of the column, `--deep`, 1 px `--hair`, 14 px radius) holds:
- the text field;
- the **memory switch**, a 36×20 track: on is a green knob with a 6 px glow, off is a hollow `--dim` knob;
- the **reach picker**, a four-stop segmented control: Session · Project · Agent · Global. Its glyph is four
  concentric rings, with the chosen ring at `--text` and the rest at `--hair`.

**What switching does in the lens** (real state changes, 300 ms):
- **Memory off:** every lit layer goes dark. Only the hairline planes stay, so it is plain that nothing is consulted.
  Replies carry a "no memory" receipt in `--yard`, dashed.
- **Reach change:** everything outside the reach drops to 6% (an aperture closing). What remains is brightened to
  step 2.

**Signature, the answer receipt.** Under each reply there is a 64 px strip:
- a tick raster, with x for each written word and one row per node on the desk;
- rows are labelled R12, R40 or N7 in their store colour, and the core's row is labelled CORE;
- a white tick means that word leaned on that node.

One mono line follows: `0.07 s first word · 1.9 s · 57 MB from SSD at 3.1 GB/s · 612 of 41,900 tokens` (example numbers).
- Hovering a tick underlines the word in the reply and lights that node in the lens.
- Clicking the receipt replays the thread in the lens.
- A false memory, when a run is graded, adds an amber ▲ at the start of the line.

### Code: a Claude Code-like workspace

**Layout (three columns):**
- **Loadout**, 260 px on the left;
- **Transcript and terminal** in the centre, flexible;
- **Editor**, 46% on the right, CodeMirror, with the file tabs as a single mono line.

The terminal (xterm) docks under the transcript at 30% height, and its size can be changed by dragging.

**Loadout:** the persona at the top as a name and a single glyph (no stock avatars or fake faces), then Skills, MCP
servers and Plugins as compact rows.
- Status is shown by form, never hue: a filled `--text` dot is connected, a hollow `--dim` ring is off, and a struck
  ring is failing, with the error in words.
- Green stays reserved for RAM.
- When the agent calls a tool, that row's dot ticks once in `--text`.

**Transcript:**
- Agent turns are body text.
- Each tool call is a one-line receipt (glyph, tool, argument, ms) that unfolds to its output.
- Diffs show inline through `@codemirror/merge`.

**Signature, the attention gutter.** The editor gutter has a 6 px lane beside the line numbers.
- For each line the agent wrote, a **white** mark means that line drew on memory: a node used at ≥ 0.10 while those
  tokens were written.
- Hovering shows which node it was, for example "room 12, day 9: `fee_round_up(amount_kes)`".
- The user's own saved fixes (kept as vault notes) show as **blue** marks.

So the "code that must fit" probe becomes something you can see as you work. A small lens (240×160) sits under the
loadout showing the project-reach organism.

### Swarm: agents, each with its own memory

**Layout:** full-bleed picture in the top 70%, instrument strip in the bottom 30%.

**Signature, the colonies.** Each agent is its own small organism: a nucleus, its rooms on a small SSD disc, and a
reach shell (a 1 px `--hair` circle).
- The colonies sit on a ring around the shared task, a white point at the centre.
- Under all of them lies one shared blue root-mat, the global vault.
- Messages between agents are neutral `--text` pulses along hyphae between colonies, because messages are not memory.
- When an agent reads its own memory, its colony lights inside in store colours. When it reads global memory, a blue
  filament rises from the mat into that colony.
- A colony's nucleus size is its measured RAM.

**Strip:** one stacked trace row per agent, labelled **A1–A8** (the loved labelled rows). Each row has:
- a green RAM trace;
- red ticks for SSD reads;
- white ticks for used memory;
- `--text` ticks for messages sent.

Each row's label matches its colony on the ring, by position and label rather than by a new hue.

### Memory: what moves between the SSD and RAM, and the vault

This is the hero screen: full-bleed, with nothing but the rail, the picture and the strip.

**Signature, the terrarium.** Three stacked glass planes, seen from a fixed 3/4 angle (orthographic, pitched 24°; the
user can orbit ±30° by dragging, and it springs back on release):

1. **RAM plane (top):**
   - the **core nucleus** at its centre;
   - the **desk**: green copies of rooms floating directly above their homes;
   - the **pen** at the front edge;
   - plane rim in `--ram` step 1, and a desk meter on the right rim (tokens on the desk / desk budget).
2. **SSD plane (middle):** the mycelium.
   - Every room is an outlined area of moments, sized by bytes, at step 1 red.
   - Rooms are joined by doors.
   - Clusters of rooms are the "thousands of dots inside area borders" picture.
3. **Vault plane (bottom):** the root-mat. Every note is a blue spore and its doors are fine filaments, laid out by the
   same semantic layout, so each room's archived notes lie directly beneath it.

The planes are 1 px `--hair` rims with a 3% fill of their store colour, so they read as glass lit from inside. A depth
scale runs up the left edge in mono, with real numbers (these are examples):
- `RAM 1.71 GB / 24 GB`;
- `SSD 1,204 rooms · 6.8 GB`;
- `VAULT 3,118 notes · 41 MB`.

**How tensors swapping live looks**, during one answer:
1. **Choose.** The question appears as a white point on the RAM plane, at its place in the layout. A white hairline
   drops straight down through the RAM plane to the chosen room on the SSD plane, and the room's rim flashes to step 3.
2. **Burst read.** A capsule rises vertically from the room's centre, the bytes going up.
   - Its colour runs from `--ssd` to `--ram` as it climbs.
   - Its width is set by bytes (a 512-token room at 112 KB/token is about 57 MB and draws thick). Its length is set
     by GB/s.
   - Where it crosses the RAM plane, the plane's rim lights in a 40 px arc.
   - A mono chip rides it: `57 MB · 18 ms · 3.1 GB/s · shown ×13`.
3. **Words from the vault.** The 4 closest moments come as words. Each rises from its spore or moment as a *thin*
   blue-to-green thread (a few KB, so width 1–2 px). Beside the thick tensor streak, the 29,000× size difference
   between notes and text is visible without a single number.
4. **Desk laid.** Copies settle as green rings above their homes. The home rooms stay red at step 2, joined to their
   copies by a hairline.
5. **Writing.** Each word ticks the pen. Nodes whose attention share passes 0.10 over the answer get white-hot
   cores, while picked-but-unused copies stay as plain green rings. The core's rim flares by its share.
6. **Cleared.** The green rings dissolve (RAM freed), the doors that were walked thicken, and the thread fades over
   8 s.

**Strip (bottom 22%, the loved stacked traces):** all rows share one real-time x axis and a playhead.

| Row | Shows |
| --- | --- |
| `RAM` | Green trace of bytes in RAM |
| `SSD` | Red ticks per burst, height = bytes; GB/s under each tick in 9 px mono |
| `VAULT` | Blue ticks per note read |
| One row per desk node (R12, R40, N7…), labels in store colour | White ticks per word where that node was used |

Dragging the playhead scrubs any past answer from `events.jsonl`, and the terrarium replays it.

**Vault mode.** "Open the vault" tilts the camera down over 600 ms until the vault plane fills the screen, viewed from
above. It becomes an Obsidian-like graph of blue spores and filaments, with door width set by walks.
- Hovering a note shows its first lines in a floating 320 px card (body text, `--deep`).
- Clicking opens it in a right reader panel (480 px), as markdown you can edit.
- A depth slider (1–3) shows its local graph, as in Obsidian.
- Pressing Esc or tilting back returns to the terrarium.

**Close-up of a tensor.** Clicking a green copy on the desk opens it into its anatomy, after Bycroft's 3D GPT view:
- 28 thin plate pairs (K and V per layer) stacked vertically;
- the four watched layers (12, 16, 20, 24) are lit with their measured attention;
- the other 24 are drawn as outlines labelled "not watched", which is honest about what we measure.

**Last night.** On the first open after sleep, a 10 s replay runs once:
- red streaks rise into the nucleus (facts distilled);
- doors thin;
- drips fall to the vault;
- then one mono line, for example `+14 facts into the core · 3 rooms archived · 0 destroyed`.

### Bench: results

**Layout:**
- the top 55% is the hero chart;
- below it, two rows of four probe tiles;
- a right column (300 px) holds the Claude yardstick costs.

**Signature, the long-haul horizon:**
- x is the history length on a log scale, with cuts at 64K, 256K, 1M and 2M tokens;
- y is the score;
- each model's context window is a vertical `--hair` wall labelled at its foot;
- memory-on runs are bright `--text` lines with bloom (the heroes), memory-off runs are `--dim` lines, and Claude is
  a `--yard` dashed line;
- every line is labelled at its right end (no legend);
- false memories at each cut hang under the line as amber ▲ marks, one per false memory, so a confident liar is
  visible at once.

The story the chart has to tell, that memory-on lines run straight through the walls where the others fall, needs no
caption. The hero number above it shows one headline. Today that is the 27B: `62–68 / 85 with memory · 0 without`.

**Probe tiles:** facts, changed, two-hop, maths, page, code, look-alikes, never-said. Each tile has:
- one big score;
- a small tick raster of its items in the verdict glyphs below;
- the median TTFT in mono.

The "page that grows" tile also shows the generated catering page as a real headless-browser screenshot. That is the
one place where a real image of the output carries the result.

Verdict glyphs (form, not hue):

| Verdict | Glyph |
| --- | --- |
| Right | filled `--text` dot |
| Honest decline | `--text` ring with a gap |
| Wrong | hollow `--dim` ring |
| False memory | filled amber ▲ |
| Stale | half-filled amber ▲ |

**Speed panel** (under the tiles): time to the first word against history size, a single line that stays flat at
0.07 s while the history grows. The flatness *is* the picture. The p50/p90 retrieval ms and the SSD's share of the
wait are in mono beside it.

**Yardstick column:** per Claude model, input, cached and output tokens and $ at list price, with a running total
against the $60 cap as a thin `--yard` bar.

## An answer's data path

The thread is one continuous 1.25 px white line, bloomed. It is drawn as the answer happens and reads bottom to top,
like an attribution graph, except that it is the engine's own path:

```
question point (RAM plane)
  └─ drops to the chosen room (SSD plane)          choose 4 ms
       └─ rises as the burst streak                read 18 ms · 57 MB · 3.1 GB/s
            ├─ the desk copy (green ring)          lay 2 ms
            ├─ thin threads from vault/moments     words 0.3 ms · 6 KB
            └─ into the core nucleus (always on)
                 └─ white filaments from USED nodes only, converging on the pen
                      └─ the pen → the reply in Chat                first word 70 ms · 1.9 s total
```

- Each segment carries its measured duration as a mono label at its midpoint.
- Picked-up nodes that were not used get **no** filament to the pen. They stay green rings, and you can see that they
  were fetched and ignored.
- If the answer is graded false, the pen end of the thread turns amber and gets a ▲.
- In Chat, the thread runs in the lens. In Memory, it runs in the terrarium. In the receipt, it is the tick raster.
  These are one path in three sizes.

## Events the view needs (a proposal for the lead)

The view only draws what the engine reports. `events.jsonl` already has `remember` and `answer`, with per-word
looks. For live swapping, the view needs these small events from `swap.py` and `metrics.py`, streamed from the app
server (Server-Sent Events, JSON):

| kind | fields |
| --- | --- |
| `choose` | `t`, `question_xy`, `rooms`, `ms` |
| `read` | `t`, `room`, `bytes`, `ms`, `gbps`, `from: "ssd"`, `to: "ram"` |
| `words` | `t`, `nodes`, `bytes`, `ms`, `from: "vault" \| "moment"` |
| `lay` | `t`, `desk_tokens`, `budget`, `ms` |
| `look` | `t`, `word_index`, `shares: {node: share}` (the existing per-word looks) |
| `clear` | `t`, `freed_bytes`, `walked_doors` |
| `sleep` | `t`, `distilled`, `archived`, `faded_doors` |
| `ram` | `t`, `bytes` (sampled at 10 Hz while active, never while idle) |

## Libraries

Every library below is vendored into `v2/camr_engine/app/static/vendor/`. There is no CDN at runtime and fonts are
self-hosted woff2, so the app works with Wi-Fi off. Each version is the newest stable release that is at least two
weeks old on 4 Nov 2026, checked on the npm registry.

| Package | Version | Licence | For |
| --- | --- | --- | --- |
| `three` | 0.186.1 | MIT | WebGL2 renderer, instancing, orthographic camera |
| `postprocessing` | 6.39.5 | Zlib | `SelectiveBloomEffect` (peer: three ≥ 0.168 and < 0.187, so it matches) |
| `d3-force-3d` | 3.0.6 | MIT | Relaxing new buds into place |
| `graphology` | 0.26.0 | MIT | The vault graph: doors, local depth, two-hop |
| `uplot` | 1.6.32 | MIT | Instrument strips: stacked traces and tick rasters on canvas |
| `d3-scale` | 4.0.2 | ISC | Bench log axis |
| `d3-shape` | 3.2.0 | ISC | Bench lines |
| `preact` | 10.29.8 | MIT | Components (the stable 10 line) |
| `@preact/signals` | 2.11.3 | MIT | Binding the live event stream to the UI |
| `htm` | 3.1.1 | Apache-2.0 | JSX-like templates with no build step |
| `codemirror` | 6.0.2 | MIT | Editor, and read-only code blocks in Chat (one highlighter for the whole app) |
| `@codemirror/view` | 6.43.15 | MIT | 〃 |
| `@codemirror/state` | 6.7.6 | MIT | 〃 |
| `@codemirror/language` | 6.13.1 | MIT | 〃 |
| `@codemirror/commands` | 6.11.1 | MIT | 〃 |
| `@lezer/highlight` | 1.2.5 | MIT | A custom highlight theme built on the tokens |
| `@codemirror/lang-python` | 6.2.1 | MIT | 〃 |
| `@codemirror/lang-javascript` | 6.2.5 | MIT | 〃 |
| `@codemirror/lang-markdown` | 6.5.2 | MIT | Vault notes |
| `@codemirror/merge` | 6.12.3 | MIT | Inline diffs in Code |
| `@xterm/xterm` | 6.0.0 | MIT | The terminal in Code |
| `@xterm/addon-fit` | 0.11.0 | MIT | 〃 |
| `marked` | 18.1.1 | MIT | Replies and notes as markdown |
| `dompurify` | 3.4.17 | MPL-2.0 or Apache-2.0 | Sanitising rendered markdown |
| `lucide-static` | 1.61.0 | ISC | Rail glyphs (copy only the six SVGs) |
| `@fontsource-variable/geist` | 5.3.0 | OFL-1.1 | Interface type (latin woff2 only) |
| `@fontsource-variable/martian-mono` | 5.3.0 | OFL-1.1 | Instrument and code type (`wdth.css` and `martian-mono-latin-wdth-normal.woff2`) |
| `esbuild` | 0.28.2 | MIT | Development only: one bundle step that writes `vendor/*.js`, which is then committed |

**How it is vendored:**
- Run `npm pack` for each pinned version into a scratch folder.
- Run esbuild once to make ESM bundles: `vendor/three.js` and `vendor/postprocessing.js` (sharing one three),
  `vendor/codemirror.js`, `vendor/ui.js` (preact, signals, htm), `vendor/uplot.js` and `vendor/xterm.js`.
- Add an import map in `index.html`.
- Record the versions and SHA-256 of each file in `vendor/VERSIONS.txt`.
- The server's Content-Security-Policy stays `default-src 'self'`.

**Considered and left out:**
- `@cosmos.gl/graph` 3.5.1 (MIT, GPU force graph) is held back until a vault passes about 100,000 notes. One renderer
  is simpler.
- `gsap` 3.15.0: its licence is not an open-source one, and WAAPI is enough.
- deck.gl: built for maps.
- Monaco: about 5 MB, and a second editor model.
- Shiki: a second highlighter.
- `troika-three-text`: HTML overlays are crisper and accessible.
- WebGPU: three's `WebGPURenderer` is the upgrade path, once Safari's WebGPU is proven on this Mac.

## What makes it unlike anything else

- **The memory is the hero, and it is real.** Chat apps (ChatGPT, Claude, LM Studio, Ollama) hide memory in a
  settings list. This app shows, word by word, which memory the model read, where it lived and which part it actually
  used. It is drawn from the engine's own event log, not an illustration.
- **Picked up versus used.** No other tool separates "fetched" from "leaned on". The green ring against the white
  core turns the engine's honesty claim into something you can see.
- **Height is latency.** RAM above, SSD rooms in the middle, the vault below, in one shared semantic layout. A swap is
  a vertical streak whose colour changes as its location changes. Nobody else draws the storage hierarchy and the
  meaning map as one picture.
- **Colour as microscope channels.** Three store hues, one white for use and one amber for lies, after the
  fluorescence imaging he loved. Obsidian colours groups for decoration. Refik Anadol's data sculptures are beautiful
  but carry no meaning. Here every pixel is accountable.
- **A living rule, not a metaphor.** Doors thicken by the slime-mould flow rule and thin with sleep's 5% a day, so the
  organism's shape *is* its usage history. Art&Graft avoided neural-network imagery for Gemini because it is a
  cliché. This avoids the cliché by being literal.
- **Stillness means idle.** The app is dark and motionless until the engine works, which also leaves the GPU to MLX.
- **The size gap is drawn.** A thick tensor streak next to a thin text thread shows the 29,000× size gap, and with it
  the reason sleep and the archive exist.

## Risks, and how to check them

- **"Neural-net cliché."** Tested on the first real render of his own memory, not on a mockup. If it reads as a
  stock brain, the fix is to show less: fewer structure hairlines and more darkness.
- **Too sparse again, as in round 1.** The structure layer (step 1, normal blending) exists to give density without
  clutter. Its alpha is tuned on a real vault of 1,000 or more rooms, never on a toy one.
- **GPU contention.** The lead measures tok/s with the Memory screen open and animating. Over 2% means cutting bloom
  first, then the dot count.
- **Readability of red against green.** Check with macOS Accessibility colour filters (deuteranopia and protanopia)
  on the terrarium and the strip before the pick.

## References

Each one was found on the web tonight and its URL checked.

Living networks and growth:
- Physarum flow rule, Tero et al., "Rules for biologically inspired adaptive network design", *Science* 2010:
  https://ir.lib.hiroshima-u.ac.jp/00029243, with a plain account at
  https://www.nationalgeographic.com/science/article/slime-mould-attacks-simulates-tokyo-rail-network
- Sage Jenson, Physarum (agents plus a fading trail map, millions of particles on the GPU):
  https://cargocollective.com/sagejenson/physarum
- Michael Fogleman, Physarum: https://michaelfogleman.com/projects/physarum/
- Nervous System, Hyphae (venation-style growth): https://n-e-r-v-o-u-s.com/projects/sets/hyphae/
- Andy Lomas, Cellular Forms: https://www.andylomas.com/cellularForms.html
- SPUN, Underground Atlas (mycorrhizal networks on a dark map): https://www.spun.earth/underground-atlas

Brains and connectomes:
- FlyWire Codex (whole fly brain, connection strength as line weight): https://codex.flywire.ai/, and the paper
  https://www.nature.com/articles/s41586-024-07558-y
- His loved board sources (suite2p, Open Ephys, eLife figures):
  - https://suite2p.readthedocs.io/en/latest/gui/
  - https://open-ephys.github.io/gui-docs/User-Manual/Plugins/LFP-Viewer.html
  - https://elifesciences.org/articles/32353
  - https://elifesciences.org/articles/83139
  - https://elifesciences.org/articles/65751
  - https://www.nature.com/articles/ncomms8924

Graph views:
- Obsidian graph view (node size grows with links; link thickness; local graph depth; animate by creation time):
  https://obsidian.md/help/plugins/graph
- cosmos.gl, GPU force graph (OpenJS): https://openjsf.org/blog/cosmos-gl-v3 and https://github.com/cosmosgl/graph
- 3d-force-graph: https://github.com/vasturiano/3d-force-graph

Data art and studios:
- Refik Anadol, Unsupervised (MoMA latent-space data sculpture): https://refikanadol.com/works/unsupervised/
- Refik Anadol, Coral Dreams: https://refikanadol.com/works/coraldreams/
- Igloo Inc., Awwwards Site of the Year 2024 (three.js, WebGL UI text, particles that glow as they move):
  https://www.igloo.inc/, with the case study at https://www.awwwards.com/igloo-inc-case-study.html
- Lusion (dark WebGL studio site): https://lusion.co/

Visual identities:
- Google DeepMind identity, someform Studio (3D forms as metaphors for AGI ideas):
  https://www.stashmedia.tv/deep-inside-the-deepmind-rebrand-with-someform-studio/
- Google DeepMind, Visualising AI (commissioned open imagery): https://deepmind.google/discover/visualising-ai/ and
  https://unsplash.com/blog/visualizing-ai-with-google-deepmind
- Gemini identity by Art&Graft (particles stretch in travel and contract at rest; they avoided neural-network
  imagery): https://abduzeedo.com/art-graft-gemini-identity-system
- Neuralink identity by Play (science-textbook grounding, colour used to tell navigation paths apart):
  https://www.itsnicethat.com/news/play-neuralink-visual-identity-graphic-design-220121 and https://neuralink.com/

Inside models, and the data path:
- Brendan Bycroft, LLM Visualization (tensors as 3D blocks; weights and activations in two colours):
  https://bbycroft.net/llm
- Anthropic, attribution graphs (input at the bottom, output at the top, pruned to the paths that matter):
  https://transformer-circuits.pub/2025/attribution-graphs/methods.html
- Neuronpedia (an interactive circuit viewer): https://neuronpedia.org/

Rendering and instruments:
- three.js selective bloom example: https://threejs.org/examples/webgl_postprocessing_unreal_bloom_selective.html
- pmndrs postprocessing (`SelectiveBloomEffect`): https://github.com/pmndrs/postprocessing
- uPlot demos (fast stacked time series): https://leeoniya.github.io/uPlot/demos/index.html
- NVIDIA Nsight Systems (host-to-device copies as rows on a timeline, the model for the SSD row):
  https://docs.nvidia.com/nsight-systems/UserGuide/index.html
- Perfetto trace viewer: https://ui.perfetto.dev/
- deck.gl TripsLayer (fading trails along paths): https://deck.gl/docs/api-reference/geo-layers/trips-layer
